"""OpenShell binary version pin tests.

Kartograph vendors the OpenShell CLI and gateway as pinned third-party
binaries from GitHub releases, pulled in two separate Dockerfiles:

- src/api/Dockerfile (the `openshell` CLI, used by kartograph-api to talk
  to the gateway sidecar)
- deploy/container/openshell-gateway/Dockerfile (the `openshell-gateway`
  sidecar itself, which runs the Kubernetes compute driver)

Both must be pinned to the same OPENSHELL_VERSION (CLI/gateway protocol
compatibility), and that version must be new enough for the Kubernetes
compute driver to detect the Agent Sandbox CRD's served API version at
runtime instead of assuming `v1alpha1`. Versions before v0.0.72
(NVIDIA/OpenShell#2009) hardcode `v1alpha1` with no fallback, so a
cluster that only serves `v1beta1` sandboxes causes every sandbox
list/watch call to fail with a raw "404 page not found" — which is
exactly the failure the Graph Management Assistant's "Start session"
hit in kartograph-stage.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[6]
API_DOCKERFILE = REPO_ROOT / "src" / "api" / "Dockerfile"
GATEWAY_DOCKERFILE = REPO_ROOT / "deploy" / "container" / "openshell-gateway" / "Dockerfile"

# First release with Kubernetes Sandbox API version auto-detection
# (v1beta1 with fallback to v1alpha1); see NVIDIA/OpenShell#2009.
MIN_OPENSHELL_VERSION = (0, 0, 72)


def _extract_openshell_version(dockerfile: Path) -> tuple[int, int, int]:
    match = re.search(
        r"^ARG OPENSHELL_VERSION=(\d+)\.(\d+)\.(\d+)$",
        dockerfile.read_text(encoding="utf-8"),
        re.MULTILINE,
    )
    assert match, f"no ARG OPENSHELL_VERSION=X.Y.Z found in {dockerfile}"
    return (int(match.group(1)), int(match.group(2)), int(match.group(3)))


class TestOpenShellVersionPin:
    def test_cli_and_gateway_dockerfiles_pin_the_same_version(self) -> None:
        cli_version = _extract_openshell_version(API_DOCKERFILE)
        gateway_version = _extract_openshell_version(GATEWAY_DOCKERFILE)

        assert cli_version == gateway_version, (
            "src/api/Dockerfile and deploy/container/openshell-gateway/Dockerfile "
            f"must pin the same OPENSHELL_VERSION, got CLI={cli_version} "
            f"gateway={gateway_version}"
        )

    def test_gateway_version_supports_sandbox_api_version_detection(self) -> None:
        gateway_version = _extract_openshell_version(GATEWAY_DOCKERFILE)

        assert gateway_version >= MIN_OPENSHELL_VERSION, (
            f"openshell-gateway is pinned to v{'.'.join(map(str, gateway_version))}, "
            f"which predates v{'.'.join(map(str, MIN_OPENSHELL_VERSION))}'s Kubernetes "
            "driver Sandbox API version auto-detection. Older versions hardcode "
            "agents.x-k8s.io/v1alpha1 with no fallback, so a cluster serving only "
            "v1beta1 Sandboxes makes every sandbox list/watch call fail with a "
            "raw 404, breaking Graph Management Assistant session start."
        )
