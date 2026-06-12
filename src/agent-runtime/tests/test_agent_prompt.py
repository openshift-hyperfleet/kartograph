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
    assert "Bash" in prompt
    assert "instance_generators" in prompt
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
            "next_action": "Run entity prepopulation for `folder`.",
            "prepopulation_tasks": [
                {
                    "kind": "entity",
                    "label": "folder",
                    "live_instance_count": 0,
                    "scanner_path": "instance_generators/folder.py",
                }
            ],
            "prepopulated_entity_types_without_instances_live": ["folder"],
            "prepopulated_relationship_types_without_instances_live": [],
            "prepopulated_entity_types": [
                {
                    "label": "folder",
                    "live_instance_count": 0,
                    "metadata_instance_count": 0,
                    "required_properties": ["name"],
                }
            ],
            "blocking_reasons": ["Prepopulated entity types require instances before transition: folder"],
            "transition_eligible": False,
        },
    )

    assert "Workspace readiness" in prompt
    assert "Next action" in prompt
    assert "instance_generators/folder.py" in prompt
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


def test_build_agent_system_prompt_compact_omits_skills_and_full_tools_table() -> None:
    prompt = build_agent_system_prompt(
        {
            "system_prompt": "You are the Graph Management Assistant.",
            "skills": {"prepopulation": "Run instance_generators with Bash."},
        },
        settings=AgentRuntimeSettings(
            KARTOGRAPH_WORKLOAD_TOKEN="token",
            KARTOGRAPH_KNOWLEDGE_GRAPH_ID="kg-123",
        ),
        prompt_detail="compact",
    )

    assert "**prepopulation**" not in prompt
    assert "Quick workflow" not in prompt
    assert "entities_to_jsonl.py" in prompt
    assert "never /tmp" in prompt.lower() or "Never /tmp" in prompt


def test_build_agent_system_prompt_compact_extraction_jobs_keeps_description_authoring_skill() -> None:
    prompt = build_agent_system_prompt(
        {
            "system_prompt": "You are the Graph Management Assistant.",
            "skills": {
                "prepopulation": "Run instance_generators with Bash.",
                "per_instance_description_authoring": "Use IGNORE lines when counterpart has more instances.",
                "job_set_contract": "Save via kartograph_save_extraction_jobs_config.",
            },
            "graph_management_ui_mode": "extraction-jobs",
        },
        settings=AgentRuntimeSettings(
            KARTOGRAPH_WORKLOAD_TOKEN="token",
            KARTOGRAPH_KNOWLEDGE_GRAPH_ID="kg-123",
        ),
        prompt_detail="compact",
    )

    assert "**prepopulation**" not in prompt
    assert "**per_instance_description_authoring**" in prompt
    assert "IGNORE lines" in prompt
    assert "relationship_authoring_by_entity_type" in prompt
    assert "entity_type_authoring_context" in prompt
