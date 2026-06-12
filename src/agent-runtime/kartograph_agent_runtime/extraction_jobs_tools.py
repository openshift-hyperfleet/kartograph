"""MCP tool handlers for extraction job set configuration."""

from __future__ import annotations

from typing import Any

from claude_agent_sdk import tool

from kartograph_agent_runtime.tools import RuntimeTooling

KARTOGRAPH_EXTRACTION_JOBS_TOOL_NAMES = (
    "kartograph_get_extraction_jobs_config",
    "kartograph_save_extraction_jobs_config",
    "kartograph_get_extraction_jobs_plan_summary",
    "kartograph_get_extraction_jobs_status",
)


def append_extraction_jobs_tools(*, tooling: RuntimeTooling, tools: list[Any]) -> None:
    """Register extraction job configuration tools on the Kartograph MCP server."""

    @tool(
        "kartograph_get_extraction_jobs_config",
        (
            "Read saved extraction job sets for this knowledge graph, including live "
            "entity type instance counts. Call before proposing or saving changes."
        ),
        {},
    )
    async def get_extraction_jobs_config(_args: dict[str, Any]) -> dict[str, Any]:
        try:
            return RuntimeTooling.format_tool_result(
                await tooling.get_extraction_jobs_config(),
            )
        except Exception as exc:  # noqa: BLE001
            return {
                "content": [
                    {"type": "text", "text": f"Failed to read extraction jobs config: {exc}"}
                ],
                "is_error": True,
            }

    @tool(
        "kartograph_save_extraction_jobs_config",
        (
            "Save extraction job sets for this knowledge graph and regenerate pending jobs. "
            "Pass the full job_sets array (read existing config first and merge edits). "
            "Each job set needs: name, strategy (by_instances or by_files), description, "
            "entity_type + instances_per_job for by_instances, or file_patterns + files_per_job "
            "for by_files. For by_instances, description must match per_instance_description_authoring: "
            "opening capture-everything paragraph, Properties section listing each property, then "
            "one '{EntityType} -> {rel} -> {CounterpartType}:' line per ontology relationship."
        ),
        {
            "version": str,
            "job_sets": list,
        },
    )
    async def save_extraction_jobs_config(args: dict[str, Any]) -> dict[str, Any]:
        job_sets = args.get("job_sets")
        if not isinstance(job_sets, list):
            return {
                "content": [{"type": "text", "text": "job_sets must be a list of job set objects."}],
                "is_error": True,
            }
        payload: dict[str, Any] = {
            "version": str(args.get("version") or "1.0"),
            "job_sets": job_sets,
        }
        try:
            return RuntimeTooling.format_tool_result(
                await tooling.save_extraction_jobs_config(payload=payload),
            )
        except Exception as exc:  # noqa: BLE001
            return {
                "content": [
                    {"type": "text", "text": f"Failed to save extraction jobs config: {exc}"}
                ],
                "is_error": True,
            }

    @tool(
        "kartograph_get_extraction_jobs_plan_summary",
        (
            "Return projected pending job counts per configured job set based on live "
            "graph instances and file catalog matches."
        ),
        {},
    )
    async def get_extraction_jobs_plan_summary(_args: dict[str, Any]) -> dict[str, Any]:
        try:
            return RuntimeTooling.format_tool_result(
                await tooling.get_extraction_jobs_plan_summary(),
            )
        except Exception as exc:  # noqa: BLE001
            return {
                "content": [
                    {"type": "text", "text": f"Failed to load extraction jobs plan summary: {exc}"}
                ],
                "is_error": True,
            }

    @tool(
        "kartograph_get_extraction_jobs_status",
        (
            "Return materialized extraction job queue metrics: counts by status, recent jobs, "
            "and active workers."
        ),
        {},
    )
    async def get_extraction_jobs_status(_args: dict[str, Any]) -> dict[str, Any]:
        try:
            return RuntimeTooling.format_tool_result(
                await tooling.get_extraction_jobs_status(),
            )
        except Exception as exc:  # noqa: BLE001
            return {
                "content": [
                    {"type": "text", "text": f"Failed to load extraction jobs status: {exc}"}
                ],
                "is_error": True,
            }

    tools.extend(
        [
            get_extraction_jobs_config,
            save_extraction_jobs_config,
            get_extraction_jobs_plan_summary,
            get_extraction_jobs_status,
        ]
    )
