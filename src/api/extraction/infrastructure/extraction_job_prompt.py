"""Build prompts for extraction job agent runs."""

from __future__ import annotations

from pathlib import Path

from extraction.domain.extraction_job import ExtractionJobRecord

EXTRACTION_PROMPT_FILENAME = "extraction_prompt.md"
MUTATIONS_HELPER = "helpers/workload-mutations.sh"

EXTRACTION_JOB_INVOKE_PROMPT = (
    "You are running a Kartograph extraction job in /workspace. "
    f"Read {EXTRACTION_PROMPT_FILENAME}, job-context.json, and sources-index.json, then follow "
    "the instructions completely. Write JSONL batches under mutations/, validate with "
    f"`bash {MUTATIONS_HELPER} validate mutations/<batch>.jsonl`, then apply with "
    f"`bash {MUTATIONS_HELPER} apply mutations/<batch>.jsonl`. Do not finish until apply "
    "succeeds and mutations/result.json reports operations_applied > 0."
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
        "Read job-context.json and sources-index.json in the workspace for API credentials,",
        "JobPackage sources, and repository-files materialization status.",
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
                "Process only the instances listed below. Read source files under repository-files/",
                "when materialized (see job-context.json repository_files and instance property paths",
                "such as config_file_path or source_path). Use the workload API to read existing graph",
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
            "## Repository files",
            "If job-context.json repository_files.files_written is 0, report the warnings there",
            "and still apply any updates supported by graph context — but prefer reading",
            "repository-files/ content whenever sample_paths are listed.",
            "",
            "## Mutations workflow (required)",
            "This container has no Kartograph MCP tools. Use the bundled helper script:",
            f"- Validate: `bash {MUTATIONS_HELPER} validate mutations/<batch>.jsonl`",
            f"- Apply: `bash {MUTATIONS_HELPER} apply mutations/<batch>.jsonl`",
            "The helper reads api_base_url and workload_token from job-context.json (also exported",
            "as KARTOGRAPH_WORKLOAD_TOKEN, KARTOGRAPH_API_BASE_URL, KARTOGRAPH_KNOWLEDGE_GRAPH_ID,",
            "and KARTOGRAPH_TENANT_ID in the container environment), calls the workload API, and",
            "writes mutations/result.json (the CI verdict artifact).",
            "Always validate before apply. Do not finish until apply succeeds.",
            "",
            "Manual curl (only if helper fails): base `{api_base_url}/extraction/workloads`,",
            "header `X-Workload-Token: <workload_token>`, POST `/mutations/validate` or",
            "`/mutations/apply` with JSON body `{\"jsonl\": \"<file contents>\"}`.",
            "",
            "Other useful GET endpoints:",
            "- `/schema/authoring-guide` — JSONL mutation shapes and rules",
            "- `/schema/ontology` — current graph schema",
            "- `/graph/search?q=...` — search existing nodes",
            "- `/graph/instances?entity_type=...` — list instances by type",
            "",
            "## Completion",
            "When finished, mutations/result.json must show action=apply and operations_applied > 0.",
            "Do not modify files outside repository-files/ except mutations/ and helpers/.",
        ]
    )
    return "\n".join(lines)
