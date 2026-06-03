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
    tenant_id: str = Field(default="", alias="KARTOGRAPH_TENANT_ID")
    knowledge_graph_id: str = Field(default="", alias="KARTOGRAPH_KNOWLEDGE_GRAPH_ID")
    session_id: str = Field(default="", alias="KARTOGRAPH_SESSION_ID")
    skills_dir: str = Field(default="/app/skills", alias="KARTOGRAPH_SKILLS_DIR")
    workspace_dir: str = Field(default="/workspace", alias="KARTOGRAPH_WORKSPACE_DIR")
    anthropic_api_key: str = Field(default="", alias="ANTHROPIC_API_KEY")
    vertex_project_id: str = Field(default="", alias="ANTHROPIC_VERTEX_PROJECT_ID")
    vertex_region: str = Field(default="us-east5", alias="CLOUD_ML_REGION")
    gcloud_config_dir: str = Field(default="", alias="CLOUDSDK_CONFIG")
    google_application_credentials: str = Field(default="", alias="GOOGLE_APPLICATION_CREDENTIALS")
    home_dir: str = Field(default="/tmp", alias="HOME")
    turn_timeout_seconds: float = Field(default=600.0, ge=30.0, le=900.0, alias="KARTOGRAPH_AGENT_TURN_TIMEOUT_SECONDS")

    def vertex_enabled(self) -> bool:
        return vertex_enabled_from_env()

    def model_configured(self) -> bool:
        if self.vertex_enabled():
            return bool(self.vertex_project_id.strip())
        return bool(self.anthropic_api_key.strip())
