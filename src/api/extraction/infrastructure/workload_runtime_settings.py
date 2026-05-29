"""Settings for extraction workload runtime execution."""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class ExtractionWorkloadRuntimeSettings(BaseSettings):
    """Container and in-memory extraction runtime configuration."""

    model_config = SettingsConfigDict(
        env_prefix="KARTOGRAPH_EXTRACTION_RUNTIME_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    backend: Literal["memory", "container"] = Field(default="memory")
    container_engine: Literal["auto", "docker", "podman"] = Field(default="auto")
    container_network: str | None = Field(default=None)
    sticky_image: str = Field(default="kartograph-agent-runtime:dev")
    worker_image: str = Field(default="docker.io/library/busybox:1.36")
    sticky_command: tuple[str, ...] = Field(default=("python", "-m", "kartograph_agent_runtime"))
    worker_command: tuple[str, ...] = Field(default=("sleep", "3600"))
    sticky_service_port: int = Field(default=8787, ge=1024, le=65535)
    container_skills_mount: str = Field(default="/app/skills")
    container_work_mount: str = Field(default="/workspace")
    session_ttl_minutes: int = Field(default=30, ge=1, le=24 * 60)
    job_package_work_dir: str = Field(default="/tmp/kartograph/job_packages")
    skills_dir: str = Field(default="/app/skills")
    api_base_url: str = Field(default="http://api:8000")

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
