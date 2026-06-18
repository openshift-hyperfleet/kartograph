"""Settings for extraction workload runtime execution."""

from __future__ import annotations

import os
from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from extraction.infrastructure.vertex_runtime_env import (
    OPENSHELL_GCLOUD_CONTAINER_PATH,
    vertex_enabled_from_env,
)


class ExtractionWorkloadRuntimeSettings(BaseSettings):
    """Container and in-memory extraction runtime configuration."""

    model_config = SettingsConfigDict(
        env_prefix="KARTOGRAPH_EXTRACTION_RUNTIME_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    backend: Literal["memory", "container", "openshell"] = Field(default="memory")
    job_runner: Literal["stub", "agentic_ci", "openshell"] | None = Field(default=None)
    container_engine: Literal["auto", "docker", "podman"] = Field(default="auto")
    container_network: str | None = Field(default=None)
    sticky_image: str = Field(default="kartograph-agent-runtime:dev")
    worker_image: str = Field(default="docker.io/library/busybox:1.36")
    agentic_ci_image: str = Field(default="ghcr.io/opendatahub-io/ai-helpers:latest")
    agentic_ci_harness: str = Field(default="claude-code")
    agentic_ci_model: str = Field(default="")
    agentic_ci_api_base_url: str = Field(
        default="http://127.0.0.1:8000",
        description=(
            "API base URL reachable from agentic-ci job containers. "
            "Jobs use --network host, so docker service names like api:8000 will not resolve."
        ),
    )
    agentic_ci_timeout_seconds: int = Field(default=1200, ge=60, le=7200)
    extraction_job_work_dir: str = Field(default="/tmp/kartograph/extraction_jobs")
    sticky_command: tuple[str, ...] = Field(
        default=(),
        description=(
            "Optional container entrypoint override. Empty uses the image CMD "
            "(kartograph-agent-runtime invokes the venv interpreter)."
        ),
    )
    worker_command: tuple[str, ...] = Field(default=("sleep", "3600"))
    sticky_service_port: int = Field(default=8787, ge=1024, le=65535)
    container_work_mount: str = Field(default="/workspace")
    openshell_container_work_mount: str = Field(
        default="/sandbox",
        description=(
            "In-sandbox workspace path for OpenShell backends. "
            "Must be writable under OpenShell Landlock defaults (/sandbox, /tmp)."
        ),
    )
    openshell_gcloud_container_path: str = Field(
        default=OPENSHELL_GCLOUD_CONTAINER_PATH,
        description=(
            "In-sandbox path for uploaded gcloud ADC when using OpenShell backends."
        ),
    )
    session_ttl_minutes: int = Field(default=60, ge=1, le=24 * 60)
    job_package_work_dir: str = Field(default="/tmp/kartograph/job_packages")
    api_base_url: str = Field(default="http://api:8000")
    openshell_api_base_url: str = Field(
        default="http://host.docker.internal:8000",
        description=(
            "API base URL reachable from OpenShell sandboxes on the host. "
            "Docker service names like api:8000 do not resolve outside the compose network."
        ),
    )
    workload_token_signing_key: str = Field(
        default="",
        description=(
            "HMAC secret for signing extraction workload JWTs. Must be stable across "
            "API reloads so sticky containers can authenticate after hot reload."
        ),
    )
    sticky_health_timeout_seconds: float = Field(default=90.0, ge=5.0, le=600.0)
    sticky_turn_timeout_seconds: float = Field(default=1000.0, ge=30.0, le=3600.0)
    sticky_max_turns: int = Field(default=500, ge=1, le=1000)
    worker_poll_seconds: float = Field(default=1.0, ge=0.1, le=60.0)
    vertex_project_id: str = Field(default="")
    vertex_region: str = Field(default="us-east5")
    gcloud_config_mount: str | None = Field(default=None)
    gcloud_config_container_path: str = Field(default="/gcloud/config")
    container_run_uid: int | None = Field(default=None)
    container_run_gid: int | None = Field(default=None)
    container_hardening_enabled: bool = Field(default=True)
    container_cap_drop_all: bool = Field(default=True)
    container_read_only_rootfs: bool = Field(default=True)
    container_no_new_privileges: bool = Field(default=True)
    container_pids_limit: int | None = Field(default=256, ge=32, le=4096)
    container_memory_limit: str | None = Field(default="2g")
    container_tmpfs_mounts: tuple[str, ...] = Field(
        default=("/tmp:rw,noexec,nosuid,size=512m",),
    )
    openshell_gateway_name: str = Field(default="openshell")
    openshell_xdg_config_home: str = Field(
        default="",
        description=(
            "XDG config root for openshell CLI (compose dev: /root/.config when "
            "host ~/.config/openshell is mounted there)."
        ),
    )
    openshell_gateway_url: str = Field(
        default="https://127.0.0.1:17670",
        description=(
            "OpenShell gateway endpoint for CLI registration. "
            "Use https://host.docker.internal:17670 when the API runs inside compose."
        ),
    )
    openshell_provider_name: str = Field(
        default="kartograph-gma",
        description=(
            "OpenShell google-vertex-ai provider shared by GMA sticky sessions and "
            "batch extraction jobs. Injects Vertex credentials into sandboxes."
        ),
    )
    openshell_extraction_image: str = Field(
        default="quay.io/aipcc/agentic-ci/claude-sandbox:latest",
        description=(
            "OpenShell sandbox image for batch extraction jobs. "
            "Must include the sandbox user and /usr/local/bin/claude (agentic-ci claude-sandbox)."
        ),
    )
    openshell_runtime_host: str = Field(
        default="127.0.0.1",
        description=(
            "Host reachable from the API process for OpenShell port forwards. "
            "Use 127.0.0.1 when the OpenShell CLI runs in the same process/container as the API."
        ),
    )
    openshell_forward_port_base: int = Field(default=18787, ge=1024, le=65000)
    openshell_policy_dir: str = Field(
        default="",
        description="Directory containing OpenShell policy YAML files. Empty uses bundled defaults.",
    )
    openshell_policy_enforcement: Literal["soft", "hard_requirement"] = Field(
        default="soft",
        description="Landlock enforcement mode for OpenShell policies (hard_requirement in prod).",
    )

    def vertex_enabled(self) -> bool:
        return vertex_enabled_from_env()

    def sandbox_reachable_api_base_url(self) -> str:
        """API URL workload sandboxes use for Kartograph workload endpoints."""
        if self.backend == "openshell" or self.job_runner == "openshell":
            return self.openshell_api_base_url.rstrip("/")
        return self.api_base_url.rstrip("/")

    def openshell_extraction_sandbox_image(self) -> str:
        """Container image for OpenShell batch extraction sandboxes (agentic-ci claude-sandbox)."""
        return self.openshell_extraction_image

    @model_validator(mode="after")
    def _apply_vertex_env_aliases(self) -> "ExtractionWorkloadRuntimeSettings":
        if self.job_runner is None:
            if self.backend == "openshell":
                object.__setattr__(self, "job_runner", "openshell")
            elif self.backend == "container":
                object.__setattr__(self, "job_runner", "agentic_ci")
            else:
                object.__setattr__(self, "job_runner", "stub")
        if not self.vertex_project_id:
            object.__setattr__(
                self,
                "vertex_project_id",
                os.getenv("ANTHROPIC_VERTEX_PROJECT_ID", "").strip(),
            )
        if self.vertex_region == "us-east5":
            region = (
                os.getenv("CLOUD_ML_REGION", "").strip()
                or os.getenv("VERTEXAI_LOCATION", "").strip()
            )
            if region:
                object.__setattr__(self, "vertex_region", region)
        if self.gcloud_config_mount is None:
            gcloud = os.getenv("KARTOGRAPH_GCLOUD_CONFIG_MOUNT", "").strip()
            if gcloud:
                object.__setattr__(self, "gcloud_config_mount", gcloud)
        if self.container_run_uid is None:
            for key in (
                "KARTOGRAPH_EXTRACTION_RUNTIME_CONTAINER_RUN_UID",
                "HOST_UID",
                "UID",
            ):
                raw = os.getenv(key, "").strip()
                if raw.isdigit():
                    object.__setattr__(self, "container_run_uid", int(raw))
                    break
        if self.container_run_gid is None:
            for key in (
                "KARTOGRAPH_EXTRACTION_RUNTIME_CONTAINER_RUN_GID",
                "HOST_GID",
                "GID",
            ):
                raw = os.getenv(key, "").strip()
                if raw.isdigit():
                    object.__setattr__(self, "container_run_gid", int(raw))
                    break
        return self

    @field_validator("container_run_uid", "container_run_gid", mode="before")
    @classmethod
    def _empty_container_run_id_to_none(cls, value: object) -> object:
        if value == "":
            return None
        return value

    @field_validator("sticky_command", "worker_command", "container_tmpfs_mounts", mode="before")
    @classmethod
    def _parse_command(cls, value: object) -> tuple[str, ...]:
        if isinstance(value, tuple):
            return value
        if isinstance(value, list):
            return tuple(str(part) for part in value)
        if isinstance(value, str):
            parts = value.split()
            if not parts:
                raise ValueError("command must not be empty")
            return tuple(parts)
        raise TypeError("command must be a string or sequence")


@lru_cache
def get_extraction_workload_runtime_settings() -> ExtractionWorkloadRuntimeSettings:
    """Get cached extraction workload runtime settings."""
    return ExtractionWorkloadRuntimeSettings()
