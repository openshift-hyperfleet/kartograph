"""Agent runtime settings loaded from container environment."""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


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
