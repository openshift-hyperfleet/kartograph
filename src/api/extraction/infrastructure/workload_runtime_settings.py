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
    sticky_image: str = Field(default="docker.io/library/busybox:1.36")
    worker_image: str = Field(default="docker.io/library/busybox:1.36")
    sticky_command: tuple[str, ...] = Field(default=("sleep", "3600"))
    worker_command: tuple[str, ...] = Field(default=("sleep", "3600"))
    session_ttl_minutes: int = Field(default=30, ge=1, le=24 * 60)

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
