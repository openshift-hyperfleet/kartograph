"""Agent runtime settings loaded from container environment."""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from kartograph_agent_runtime.vertex import vertex_enabled_from_env


class AgentRuntimeSettings(BaseSettings):
    """Runtime configuration for sticky session agent containers."""

    model_config = SettingsConfigDict(extra="ignore")

    host: str = Field(default="0.0.0.0")
    port: int = Field(default=8787)
    api_base_url: str = Field(default="http://api:8000", alias="KARTOGRAPH_API_BASE_URL")
    workload_token: str = Field(default="", alias="KARTOGRAPH_WORKLOAD_TOKEN")
    runtime_auth_token: str = Field(default="", alias="KARTOGRAPH_RUNTIME_AUTH_TOKEN")
    tenant_id: str = Field(default="", alias="KARTOGRAPH_TENANT_ID")
    knowledge_graph_id: str = Field(default="", alias="KARTOGRAPH_KNOWLEDGE_GRAPH_ID")
    session_id: str = Field(default="", alias="KARTOGRAPH_SESSION_ID")
    workspace_dir: str = Field(default="/workspace", alias="KARTOGRAPH_WORKSPACE_DIR")
    anthropic_api_key: str = Field(default="", alias="ANTHROPIC_API_KEY")
    anthropic_base_url: str = Field(default="", alias="ANTHROPIC_BASE_URL")
    claude_code_disable_experimental_betas: str = Field(
        default="",
        alias="CLAUDE_CODE_DISABLE_EXPERIMENTAL_BETAS",
    )
    vertex_project_id: str = Field(default="", alias="ANTHROPIC_VERTEX_PROJECT_ID")
    vertex_region: str = Field(default="us-east5", alias="CLOUD_ML_REGION")
    gcloud_config_dir: str = Field(default="", alias="CLOUDSDK_CONFIG")
    google_application_credentials: str = Field(default="", alias="GOOGLE_APPLICATION_CREDENTIALS")
    home_dir: str = Field(default="/tmp", alias="HOME")
    turn_timeout_seconds: float = Field(default=1000.0, ge=30.0, le=3600.0, alias="KARTOGRAPH_AGENT_TURN_TIMEOUT_SECONDS")
    max_turns: int = Field(default=500, ge=1, le=1000, alias="KARTOGRAPH_AGENT_MAX_TURNS")

    def vertex_enabled(self) -> bool:
        return vertex_enabled_from_env()

    def openshell_inference_enabled(self) -> bool:
        return self.anthropic_base_url.strip().rstrip("/") == "https://inference.local"

    def model_configured(self) -> bool:
        if self.openshell_inference_enabled():
            return True
        if self.vertex_enabled():
            return bool(self.vertex_project_id.strip())
        return bool(self.anthropic_api_key.strip())
