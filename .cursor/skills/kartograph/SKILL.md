---
name: kartograph
description: >-
  Orients the agent in the Kartograph project: where the code and GitOps
  manifests live, how a merge to main turns into a stage deployment, and how
  to check ArgoCD for stage deployment status and live pod logs. Use when
  asked about the kartograph repo layout, release/deploy flow, checking
  whether stage is healthy/synced, or when asked to fetch pod logs from
  kartograph-stage.
---

# Kartograph

## Repos

- **Main repo (this one):** https://github.com/openshift-hyperfleet/kartograph
  — API source (`src/api`), specs, this skill, etc.
- **GitOps repo:** https://github.com/openshift-online/hp-fleet-gitops —
  canonical source of truth for stage/prod manifests, at
  `apps/kartograph/overlays/stage` (and `overlays/prod` if it exists). This is
  what ArgoCD actually deploys from. `deploy/apps/kartograph` in *this* repo
  is deprecated/historical — don't edit it expecting it to affect anything.
  There is also a now-historical GitLab mirror
  (`gitlab.cee.redhat.com/hybrid-platforms-gitops/tenant-apps/fleet-apps`)
  that ArgoCD stopped reading from 2026-07-01; `scripts/verify-fleet-apps-kartograph.sh`
  only exists to spot future drift if that ever changes back.

## Release flow: merge to main → stage image bump

Full diagram in `deploy/README.md`; summary:

1. Merge a `feat:`/`fix:` PR → release-please opens a release PR (version bump).
2. Merge the release PR → tag + push to main → Konflux builds
   `kartograph-api` (path-filtered to `src/api/**`) → pushes image to
   `quay.io/redhat-user-workloads/kartograph-tenant/kartograph-api:<commit-sha>`.
3. A Konflux pipeline `finally` task (`update-deploy-tag`) opens a PR against
   **hp-fleet-gitops** bumping `newTag` in
   `apps/kartograph/overlays/stage/kustomization.yaml`.
4. Merging that PR is what triggers the actual stage deployment — ArgoCD
   detects the kustomization change and syncs. There is no second repo/step
   to sync manually.

Changes under `deploy/`, docs, or anything outside `src/api/` do **not**
trigger a rebuild (PaC path filtering).

## Checking stage deployment status / pod logs (ArgoCD)

The stage ArgoCD instance is:

```
argocd-server-argocd-tenant-control-plane.apps.rosa.appsres09ue1.24ep.p3.openshiftapps.com
```

(Application name: `kartograph-stage`, destination namespace: `kartograph-stage`.
A second instance, `argocd-server-konflux-tenants-config-stage.apps.rosa...`,
exists for Konflux tenant config and is unrelated to kartograph's own deployment
— use the one above.)

**Important:** the `argocd` CLI's gRPC(-web) transport does not work from this
environment (`argocd login --sso` fails with `gRPC connection not ready:
context deadline exceeded`, even though the server is reachable). There is
also no direct cluster access (`oc`/`kubectl` are installed but not logged
in). The plain HTTPS REST API works fine, so use that with a bearer token
instead of the CLI.

### 1. Get a bearer token

Run the login script (requires a local browser on the same machine as the
agent — it opens the SSO URL via `xdg-open` and listens on
`localhost:8085` for the OAuth callback):

```bash
python3 .cursor/skills/kartograph/scripts/argocd_pkce_login.py \
  argocd-server-argocd-tenant-control-plane.apps.rosa.appsres09ue1.24ep.p3.openshiftapps.com
```

It does a standard OAuth2 Authorization Code + PKCE flow against ArgoCD's Dex
(`client_id=argo-cd-cli`, scopes `openid profile email groups offline_access`).
If the user already has an active OpenShift SSO session in their browser it
completes almost instantly without any prompt; otherwise the user needs to
approve the login in the browser tab that opens. It prints an `id_token` JWT
valid for 24 hours — use it as `Authorization: Bearer <token>` below. Re-run
the script if you start getting `401`s.

### 2. Query the REST API

```bash
HOST=argocd-server-argocd-tenant-control-plane.apps.rosa.appsres09ue1.24ep.p3.openshiftapps.com
TOKEN=<id_token from step 1>

# App-level sync/health status
curl -sS -H "Authorization: Bearer $TOKEN" \
  "https://$HOST/api/v1/applications/kartograph-stage" | python3 -m json.tool

# Full resource tree (includes live Pod names — Deployments/ReplicaSets don't
# show pods directly on the app object above)
curl -sS -H "Authorization: Bearer $TOKEN" \
  "https://$HOST/api/v1/applications/kartograph-stage/resource-tree"

# Pod logs — container is required; if you guess wrong the error message
# lists the valid container names for that pod (e.g. api, openshell-gateway,
# openshell-bootstrap, wait-for-db-migrate, wait-for-spicedb-schema)
curl -sS -H "Authorization: Bearer $TOKEN" --get \
  --data-urlencode "namespace=kartograph-stage" \
  --data-urlencode "podName=<pod-name>" \
  --data-urlencode "resourceName=<pod-name>" \
  --data-urlencode "kind=Pod" \
  --data-urlencode "container=api" \
  --data-urlencode "tailLines=100" \
  --data-urlencode "follow=false" \
  "https://$HOST/api/v1/applications/kartograph-stage/logs"
```

Each log line comes back as one JSON object per line (not a JSON array) —
parse line-by-line, e.g. `{"result":{"content":"...","timeStamp":"...","podName":"..."}}`.
A line with `"last":true` and empty `content` marks end of stream.
