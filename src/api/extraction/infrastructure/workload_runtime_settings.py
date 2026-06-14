"""Settings for extraction workload runtime execution."""

from __future__ import annotations

import os
from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from extraction.infrastructure.vertex_runtime_env import vertex_enabled_from_env


class ExtractionWorkloadRuntimeSettings(BaseSettings):
    """Container and in-memory extraction runtime configuration."""

    model_config = SettingsConfigDict(
        env_prefix="KARTOGRAPH_EXTRACTION_RUNTIME_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    backend: Literal["memory", "container"] = Field(default="memory")
    job_runner: Literal["stub", "agentic_ci"] | None = Field(default=None)
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
    session_ttl_minutes: int = Field(default=60, ge=1, le=24 * 60)
    job_package_work_dir: str = Field(default="/tmp/kartograph/job_packages")
    api_base_url: str = Field(default="http://api:8000")
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

    def vertex_enabled(self) -> bool:
        return vertex_enabled_from_env()

    @model_validator(mode="after")
    def _apply_vertex_env_aliases(self) -> "ExtractionWorkloadRuntimeSettings":
        if self.job_runner is None:
            object.__setattr__(
                self,
                "job_runner",
                "agentic_ci" if self.backend == "container" else "stub",
            )
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

    @field_validator("sticky_command", "worker_command", mode="before")
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
