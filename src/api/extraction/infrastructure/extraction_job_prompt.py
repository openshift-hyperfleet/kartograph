"""Build prompts for extraction job agent runs."""

from __future__ import annotations

from pathlib import Path

from extraction.domain.extraction_job import ExtractionJobRecord

EXTRACTION_PROMPT_FILENAME = "extraction_prompt.md"

EXTRACTION_JOB_INVOKE_PROMPT = (
    "You are running a Kartograph extraction job in /workspace. "
    f"Read {EXTRACTION_PROMPT_FILENAME} and job-context.json, then follow the instructions "
    "completely. Use the workload API credentials in job-context.json to apply all required "
    "graph mutations before you finish."
)


def write_extraction_prompt_file(*, workdir: Path, prompt: str) -> Path:
    """Materialize the full job instructions for the agent to read from disk."""
    path = workdir / EXTRACTION_PROMPT_FILENAME
    path.write_text(prompt.strip() + "\n", encoding="utf-8")
    return path


def build_extraction_job_prompt(*, job: ExtractionJobRecord) -> str:
    """Return the agent prompt for one materialized extraction job."""
    lines = [
        "You are an extraction agent for Kartograph, a knowledge graph platform.",
        "Read job-context.json in the workspace for API credentials and scope.",
        "",
        "## Job instructions",
        job.description.strip() or "Extract graph entities and relationships for the assigned targets.",
        "",
    ]
    if job.target_instances:
        lines.extend(
            [
                "## Coverage default",
                "For each assigned instance: populate or update every schema property and every",
                "applicable relationship instance (create missing edges; update existing ones).",
                "Treat partial coverage as incomplete unless the job instructions below narrow scope.",
                "",
                "## Target entity instances",
                "Process only the instances listed below. Use the workload API to read existing graph",
                "context and emit JSONL mutations for new or updated entities and relationships.",
                "",
            ]
        )
        for instance in job.target_instances:
            lines.append(f"- {instance.entity_type}: {instance.slug}")
        lines.append("")
    if job.target_files:
        lines.extend(
            [
                "## Target repository files",
                "Inspect only the files materialized under repository-files/. Use their content to",
                "extract entities and relationships, then emit JSONL mutations via the workload API.",
                "",
            ]
        )
        for target_file in job.target_files:
            lines.append(
                f"- {target_file.repository_folder}/{target_file.path} (package {target_file.package_id})"
            )
        lines.append("")
    lines.extend(
        [
            "## Workload API",
            "This container has no Kartograph MCP tools. Call the workload HTTP API with Bash/curl.",
            "Read api_base_url and workload_token from job-context.json.",
            "Send header `X-Workload-Token: <workload_token>` on every request.",
            "",
            "Base path: `{api_base_url}/extraction/workloads`",
            "",
            "Useful endpoints:",
            "- GET `/schema/authoring-guide` — JSONL mutation shapes and rules",
            "- GET `/schema/ontology` — current graph schema",
            "- GET `/graph/search?q=...` — search existing nodes",
            "- GET `/graph/instances?entity_type=...` — list instances by type",
            "- POST `/mutations/validate` with body `{\"jsonl\": \"...\"}` — dry-run",
            "- POST `/mutations/apply` with body `{\"jsonl\": \"...\"}` — apply mutations",
            "",
            "Write `.jsonl` files in the workspace when batches are large. Validate before apply.",
            "",
            "## Completion",
            "When finished, ensure all required mutations are applied through the workload API.",
            "Do not modify files outside repository-files/.",
        ]
    )
    return "\n".join(lines)
