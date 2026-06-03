"""Unit tests for agent system prompt assembly."""

from __future__ import annotations

from kartograph_agent_runtime.agent_prompt import build_agent_system_prompt
from kartograph_agent_runtime.settings import AgentRuntimeSettings


def test_build_agent_system_prompt_includes_skills_tools_and_session_scope() -> None:
    prompt = build_agent_system_prompt(
        {
            "system_prompt": "You are the Graph Management Assistant.",
            "prompt_hierarchy": ["platform_security_constraints", "mode_specific_skill_pack"],
            "guardrails": ["Use Kartograph schema tools only."],
            "skills": {
                "schema_modeling": "Read ontology before save.",
                "schema_tools": "Five kartograph_* tools available.",
            },
            "graph_management_ui_mode": "initial-schema-design",
        },
        settings=AgentRuntimeSettings(
            KARTOGRAPH_WORKLOAD_TOKEN="token",
            KARTOGRAPH_KNOWLEDGE_GRAPH_ID="kg-123",
            KARTOGRAPH_TENANT_ID="tenant-456",
        ),
        workspace_appendix="## Session workspace\nFiles here",
    )

    assert "Graph Management Assistant" in prompt
    assert "Use Kartograph schema tools only." in prompt
    assert "**schema_modeling**" in prompt
    assert "kartograph_get_schema_ontology" in prompt
    assert "Quick workflow" in prompt
    assert "kg-123" in prompt
    assert "tenant-456" in prompt
    assert "Files here" in prompt


def test_build_agent_system_prompt_includes_workspace_readiness() -> None:
    prompt = build_agent_system_prompt(
        {"system_prompt": "Base"},
        settings=AgentRuntimeSettings(
            KARTOGRAPH_WORKLOAD_TOKEN="token",
            KARTOGRAPH_KNOWLEDGE_GRAPH_ID="kg-123",
        ),
        workspace_readiness={
            "prepopulated_entity_types_without_instances_live": ["folder"],
            "prepopulated_relationship_types_without_instances_live": [],
            "prepopulated_entity_types": [
                {"label": "folder", "live_instance_count": 0, "metadata_instance_count": 0}
            ],
            "blocking_reasons": ["Prepopulated entity types require instances before transition: folder"],
            "transition_eligible": False,
        },
    )

    assert "Workspace readiness" in prompt
    assert "`folder`" in prompt
    assert "kartograph_get_workspace_readiness" in prompt
    assert "Read" in prompt
    assert "Glob" in prompt


def test_build_agent_system_prompt_omits_tools_without_workload_token() -> None:
    prompt = build_agent_system_prompt(
        {"system_prompt": "Base"},
        settings=AgentRuntimeSettings(KARTOGRAPH_WORKLOAD_TOKEN=""),
    )

    assert "Quick workflow" not in prompt
    assert "Base" in prompt
