#!/usr/bin/env bash
# Compare kartograph manifests in GitLab fleet-apps vs GitHub hp-fleet-gitops.
# Run on a machine with VPN access to gitlab.cee.redhat.com.
set -euo pipefail

FLEET_APPS_REPO="${FLEET_APPS_REPO:-https://gitlab.cee.redhat.com/hybrid-platforms-gitops/tenant-apps/fleet-apps.git}"
HP_FLEET_REPO="${HP_FLEET_REPO:-https://github.com/openshift-online/hp-fleet-gitops.git}"
WORKDIR="${WORKDIR:-/tmp/kartograph-gitops-verify}"

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
clone_or_pull "$FLEET_APPS_REPO" fleet-apps
clone_or_pull "$HP_FLEET_REPO" hp-fleet-gitops

KARTOGRAPH_PATH="apps/kartograph"
echo
echo "==> Diff: fleet-apps vs hp-fleet-gitops ($KARTOGRAPH_PATH)"
if diff -ruN "hp-fleet-gitops/$KARTOGRAPH_PATH" "fleet-apps/$KARTOGRAPH_PATH" > "$WORKDIR/kartograph.diff"; then
  echo "OK: No differences — fleet-apps matches hp-fleet-gitops."
  rm -f "$WORKDIR/kartograph.diff"
else
  echo "DIFF FOUND — review $WORKDIR/kartograph.diff"
  echo
  diff --stat "hp-fleet-gitops/$KARTOGRAPH_PATH" "fleet-apps/$KARTOGRAPH_PATH" || true
fi

echo
echo "==> Required OpenShell / stage files in fleet-apps:"
REQUIRED=(
  "base/openshell-gateway-configmap.yaml"
  "base/openshell-policies-configmap.yaml"
  "base/openshell-rbac.yaml"
  "base/networkpolicy-sticky-runtime.yaml"
  "overlays/stage/api-openshell-sidecar-patch.yaml"
)
missing=0
for rel in "${REQUIRED[@]}"; do
  if [[ -f "fleet-apps/$KARTOGRAPH_PATH/$rel" ]]; then
    echo "  OK  $rel"
  else
    echo "  MISSING  $rel"
    missing=$((missing + 1))
  fi
done

echo
echo "==> kustomization.yaml must list OpenShell base resources:"
rg -n "openshell|networkpolicy-sticky" "fleet-apps/$KARTOGRAPH_PATH/base/kustomization.yaml" || {
  echo "  MISSING openshell entries in base/kustomization.yaml"
  missing=$((missing + 1))
}

echo
echo "==> Validate fleet-apps stage overlay renders:"
if command -v kubectl >/dev/null 2>&1; then
  kubectl kustomize "fleet-apps/$KARTOGRAPH_PATH/overlays/stage" >/dev/null
  echo "  OK  kubectl kustomize succeeded"
  kubectl kustomize "fleet-apps/$KARTOGRAPH_PATH/overlays/stage" | rg -c "kartograph-openshell-gateway|kartograph-openshell-policies|kartograph-openshell-sandbox" || true
else
  echo "  SKIP kubectl not installed"
fi

if [[ "$missing" -gt 0 ]]; then
  echo
  echo "ACTION: Open an MR on fleet-apps to sync apps/kartograph from hp-fleet-gitops."
  echo "  cp -a hp-fleet-gitops/apps/kartograph/. fleet-apps/apps/kartograph/"
  exit 1
fi

echo
echo "If manifests match but ArgoCD still fails, escalate to platform:"
echo "  - SecretStore vault-backend in kartograph-stage"
echo "  - ArgoCD project RBAC for Role/RoleBinding in tenant namespace"
