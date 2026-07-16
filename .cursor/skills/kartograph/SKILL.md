---
name: kartograph
description: >-
  Orients an agent working on the Kartograph project on how to get ArgoCD
  log/API access, how PRs and CI work in the kartograph and hp-fleet-gitops
  repos, what cluster access is (and isn't) available, and when to ask the
  human to use Vault UI or Konflux UI instead of hunting for a CLI
  workaround. Use at the start of any session that involves debugging
  stage/prod, deploying via GitOps, or asking the human for infra access.
disable-model-invocation: true
---

# Working on Kartograph

## Repos and PR workflow

**`openshift-hyperfleet/kartograph`** (this repo, app source):
- `main` is branch-protected — always work on a branch and open a PR, even for urgent fixes.
- Required checks: `Test Python 3.12`, `Test Python 3.13`, `Validate PR title` (conventional-commit style titles enforced), `Validate Documentation Sync`, `CodeQL` (x3 analyze jobs), and a Konflux `kartograph-*-on-pull-request` build check.
- Follow AGENTS.md: TDD, DDD bounded contexts, domain-oriented observability (probes, not `logger.*`/`print`).

**`openshift-online/hp-fleet-gitops`** (GitOps deploy manifests, separate repo/clone):
- `main` is **not** branch-protected — direct pushes work and are fine for urgent deploy fixes.
- Key paths: `apps/kartograph/overlays/stage/kustomization.yaml` (image tags per component), `apps/kartograph/base/*.yaml` (RBAC, `openshell-gateway-configmap.yaml`, etc).
- Normal path is automated: after a kartograph PR merges and its push-pipeline image build succeeds, Konflux's `update-deploy-tag` finally task (see `.tekton/kartograph-*-push.yaml`) clones this repo, bumps the `newTag` for that component in the stage kustomization, pushes a `konflux/deploy-tag-<component>-<sha>` branch, opens a PR, and tries to enable auto-merge. If that's slow or flaky, editing `kustomization.yaml` and pushing directly to `main` is a legitimate faster path since the branch is unprotected.
- ArgoCD (`kartograph-stage` Application) auto-syncs from this repo's `main`.

## ArgoCD access (logs, sync status, manifests)

`argocd login --sso` is broken against this cluster — it hangs/times out on the gRPC handshake even with `--grpc-web`. Don't spend time retrying CLI login flags.

**Workaround:** do a manual OAuth2/PKCE login against Dex and then call ArgoCD's REST API directly with the resulting token:

```bash
/usr/bin/python3 .cursor/skills/kartograph/scripts/argocd_pkce_login.py
# opens a URL for the human to complete SSO in a browser, then writes
# the id_token to /tmp/argocd_token.txt
```

Gotchas already worked out for you:
- The Dex client is `argo-cd-cli`; the redirect URI **must** be `http://localhost:8085/auth/callback` (not `/callback`) or Dex rejects it as unregistered.
- Some shells have a wrapped/aliased `python3` that fails silently — always invoke `/usr/bin/python3` explicitly for this kind of script.

Once you have the token, useful endpoints (server: `argocd-server-argocd-tenant-control-plane.apps.rosa.appsres09ue1.24ep.p3.openshiftapps.com`):

```bash
TOKEN=$(cat /tmp/argocd_token.txt)
SERVER="argocd-server-argocd-tenant-control-plane.apps.rosa.appsres09ue1.24ep.p3.openshiftapps.com"
# app list / sync+health status
curl -s -H "Authorization: Bearer $TOKEN" "https://$SERVER/api/v1/applications?fields=items.metadata.name,items.status.sync.status,items.status.health.status"
# single app detail (sync revision, operationState)
curl -s -H "Authorization: Bearer $TOKEN" "https://$SERVER/api/v1/applications/kartograph-stage"
# pod logs - container is the plain container name (e.g. "api", "openshell-gateway"),
# not the component/image name
curl -s -H "Authorization: Bearer $TOKEN" "https://$SERVER/api/v1/applications/kartograph-stage/logs?namespace=kartograph-stage&podName=<pod>&container=api&tailLines=500&follow=false"
```

The raw resource-manifest endpoint (`/resource`) has been 403'd for this token's RBAC even though `/applications` and `/logs` work — don't be surprised if manifest access is more restricted than logs.

More gotchas:
- The id_token is short-lived (observed expiring well under 24h, possibly under a couple hours) — a 401 on any of the above just means re-run the login script, don't debug the token itself. Quick liveness check: `curl -s -o /dev/null -w "%{http_code}" -H "Authorization: Bearer $TOKEN" "https://$SERVER/api/v1/applications?fields=items.metadata.name"` (200 = good, 401 = re-login).
- Run the script with `/usr/bin/python3 -u` when backgrounding it — without `-u` the "Open this URL..." line can sit buffered and never reach the terminal file before you need it.
- If a prior login attempt is still holding `127.0.0.1:8085` (e.g. you backgrounded it and moved on), a fresh run fails with `OSError: [Errno 98] Address already in use`. `pkill -9 -f argocd_pkce_login.py` first.
- The `tenant-hp-fleet` AppProject's `clusterResourceWhitelist` only permits `Namespace` (`GET /api/v1/projects/tenant-hp-fleet`) — cluster-scoped resources like `CustomResourceDefinition` can never be synced from `hp-fleet-gitops` even with perfect RBAC. Anything cluster-scoped is a platform/SRE ask, not a GitOps PR from this side.

## Cluster (`oc`/`kubectl`) access

There is a logged-in `oc` session (`oc whoami` succeeds), but it's the human's own account and has **no useful RBAC** in `kartograph-stage`/`kartograph-tenant` (`oc auth can-i get secrets` / `list pods` both return `no`). Don't rely on `oc`/`kubectl` for cluster debugging in this environment — use the ArgoCD REST API above instead. If direct cluster access ever becomes necessary, ask the human rather than assuming a token can be escalated.

## Agent Sandbox CRD (`agents.x-k8s.io`) — cluster-side dependency, not ours to fix

kartograph-api's `openshell-gateway` sidecar runs OpenShell's Kubernetes compute
driver, which watches `Sandbox` custom resources (`agents.x-k8s.io`) to run the
Graph Management Assistant's sessions. That CRD + its controller are
**cluster-scoped infrastructure that no repo we have access to installs or
owns** — not `hp-fleet-gitops`, not `hybrid-platforms-gitops/infrastructure`
(which *does* install other cluster-wide CRDs via its `components/` catalog,
e.g. `gateway-api`, just not this one), not `ambient-code-gitops` (which runs
its own agent-sandbox-adjacent workload on `hcmais01ue1` but has zero
CRD/controller manifests checked in either). If it's missing, this is a
platform/SRE ask, full stop — don't go looking for a GitOps fix on our side.

**Symptom** (repeats every ~2s in the `openshell-gateway` container, not `api`):
```
WARN openshell_server::compute: Compute driver watch stream failed to start error=code: 'Internal error', message: "no supported Agent Sandbox API version is available; tried v1beta1, v1alpha1"
WARN kube_client::client: Unsuccessful data error parse: 404 page not found
```
(`openshell-gateway` needs to be pinned to OpenShell ≥ v0.0.72 for that "tried
v1beta1, v1alpha1" fallback message to even appear — see
`test_openshell_version_pin.py`. Older pins hardcode `v1alpha1` with no
fallback and fail differently.)

**Key trap:** `hp-fleet-gitops`'s `openshell-rbac.yaml` (namespaced `Role`
granting `kartograph-api`'s SA verbs on `sandboxes.agents.x-k8s.io`) syncing
"Healthy" in ArgoCD is **not evidence the CRD exists** — Kubernetes RBAC never
validates that a `Role`'s referenced resource type is actually registered.
The only reliable live check is ArgoCD's own cluster API-discovery cache:

```bash
curl -s -H "Authorization: Bearer $TOKEN" "https://$SERVER/api/v1/clusters" -o /tmp/argocd_clusters.json
/usr/bin/python3 -c "
import json
d = json.load(open('/tmp/argocd_clusters.json'))
for c in d['items']:
    matches = [a for a in c.get('info', {}).get('apiVersions', []) if 'agents.x-k8s.io' in a]
    print(c.get('name'), c.get('server'), '->', matches or 'NOT PRESENT')
"
```
As of 2026-07, `appsres09ue1` (kartograph-stage's cluster, addressed by this
ArgoCD instance as `in-cluster` / `https://kubernetes.default.svc` since the
ArgoCD control plane itself runs there) has had it flap present→absent at
least once (403 on 07-06, gone again by 07-15); `hcmais01ue1` (a different
managed cluster, `agents.x-k8s.io/v1alpha1` only, no `v1beta1`) has had it the
whole time. Escalation contact who's fixed Sandbox-related issues here before:
Jon Mosco (committed the `hybrid-platforms-gitops/infrastructure` RBAC fix in
`a9ed33a1`).

## Vault UI / Konflux UI — ask the human

The human has direct access to both the **Vault UI** and the **Konflux UI** and can read or edit secrets/config there, or watch/retrigger builds — things the agent cannot do itself. When a Vault secret's contents need inspecting (or editing) or a Konflux build/pipeline needs checking, ask the human to do it and report back rather than trying to find a CLI/API workaround. Known relevant Vault path: `hp-fleet/kartograph/stage/extraction-runtime` (holds `application_default_credentials.json` and `KARTOGRAPH_EXTRACTION_RUNTIME_WORKLOAD_TOKEN_SIGNING_KEY`).
