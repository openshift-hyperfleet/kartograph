#!/usr/bin/env bash
# Validate kartograph manifests in hp-fleet-gitops (canonical: what ArgoCD
# deploys, per hp-gitops-tenants PR #9, 2026-07-01) and flag drift against the
# now-historical GitLab fleet-apps mirror, in case ArgoCD's source ever moves
# back. Run on a machine with VPN access to gitlab.cee.redhat.com.
set -euo pipefail

HP_FLEET_REPO="${HP_FLEET_REPO:-https://github.com/openshift-online/hp-fleet-gitops.git}"
FLEET_APPS_REPO="${FLEET_APPS_REPO:-https://gitlab.cee.redhat.com/hybrid-platforms-gitops/tenant-apps/fleet-apps.git}"
# Default to a freshly created, unpredictable temp dir (mktemp) rather than a
# fixed shared /tmp path, which would let another local user/process pre-plant
# a symlink there and redirect our git clone/reset writes (CWE-377). Callers
# that explicitly set WORKDIR are opting into that path themselves.
WORKDIR="${WORKDIR:-$(mktemp -d -t kartograph-gitops-verify.XXXXXX)}"

mkdir -p "$WORKDIR"
cd "$WORKDIR"

clone_or_pull() {
  local url="$1" dir="$2"
  if [[ -d "$dir/.git" ]]; then
    git -C "$dir" fetch --depth 1 origin main
    git -C "$dir" checkout main
    git -C "$dir" reset --hard origin/main
  else
    git clone --depth 1 --branch main "$url" "$dir"
  fi
}

echo "==> Cloning/updating repos..."
clone_or_pull "$HP_FLEET_REPO" hp-fleet-gitops
clone_or_pull "$FLEET_APPS_REPO" fleet-apps

KARTOGRAPH_PATH="apps/kartograph"
echo
echo "==> Diff: hp-fleet-gitops (canonical) vs fleet-apps (historical mirror, $KARTOGRAPH_PATH)"
if diff -ruN "hp-fleet-gitops/$KARTOGRAPH_PATH" "fleet-apps/$KARTOGRAPH_PATH" > "$WORKDIR/kartograph.diff"; then
  echo "OK: No differences — fleet-apps still matches hp-fleet-gitops."
  rm -f "$WORKDIR/kartograph.diff"
else
  echo "DIFF FOUND (informational only — fleet-apps is not read by ArgoCD)."
  echo "Review $WORKDIR/kartograph.diff if you need fleet-apps kept current for historical reasons."
  echo
  diff --stat "hp-fleet-gitops/$KARTOGRAPH_PATH" "fleet-apps/$KARTOGRAPH_PATH" || true
fi

echo
echo "==> Required OpenShell / stage files in hp-fleet-gitops:"
REQUIRED=(
  "base/openshell-gateway-configmap.yaml"
  "base/openshell-policies-configmap.yaml"
  "base/openshell-rbac.yaml"
  "overlays/stage/api-openshell-sidecar-patch.yaml"
)
missing=0
for rel in "${REQUIRED[@]}"; do
  if [[ -f "hp-fleet-gitops/$KARTOGRAPH_PATH/$rel" ]]; then
    echo "  OK  $rel"
  else
    echo "  MISSING  $rel"
    missing=$((missing + 1))
  fi
done

# networkpolicy-sticky-runtime.yaml is intentionally absent: its podSelector is
# only used by the container-backend runtime, which this deployment (openshell-
# only) never applies. Flag it as a problem if it ever comes back.
if [[ -f "hp-fleet-gitops/$KARTOGRAPH_PATH/base/networkpolicy-sticky-runtime.yaml" ]]; then
  echo "  UNEXPECTED  base/networkpolicy-sticky-runtime.yaml (dead code for openshell-only stage)"
  missing=$((missing + 1))
fi

echo
echo "==> kustomization.yaml must list OpenShell base resources:"
rg -n "openshell" "hp-fleet-gitops/$KARTOGRAPH_PATH/base/kustomization.yaml" || {
  echo "  MISSING openshell entries in base/kustomization.yaml"
  missing=$((missing + 1))
}
echo "    (openshell-rbac.yaml is expected to be commented out until the Agent Sandbox"
echo "     CRD/controller and ArgoCD SA RBAC escalation are both granted by platform)"

echo
echo "==> Validate hp-fleet-gitops stage overlay renders:"
if command -v kubectl >/dev/null 2>&1; then
  kubectl kustomize "hp-fleet-gitops/$KARTOGRAPH_PATH/overlays/stage" >/dev/null
  echo "  OK  kubectl kustomize succeeded"
  kubectl kustomize "hp-fleet-gitops/$KARTOGRAPH_PATH/overlays/stage" | rg -c "kartograph-openshell-gateway|kartograph-openshell-policies|kartograph-openshell-sandbox" || true
else
  echo "  SKIP kubectl not installed"
fi

if [[ "$missing" -gt 0 ]]; then
  exit 1
fi

echo
echo "If manifests are correct but ArgoCD still fails, escalate to platform:"
echo "  - SecretStore vault-backend in kartograph-stage"
echo "  - ArgoCD project RBAC for Role/RoleBinding in tenant namespace (Blocker B)"
echo "  - Agent Sandbox CRD + controller installed cluster-wide (Blocker A)"
