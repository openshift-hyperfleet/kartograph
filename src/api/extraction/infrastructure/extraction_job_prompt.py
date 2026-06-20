"""Build prompts for extraction job agent runs."""

from __future__ import annotations

from pathlib import Path

from extraction.domain.extraction_job import ExtractionJobRecord
from infrastructure.management.maintenance_job_materializer import MAINTENANCE_JOB_SET_NAME

EXTRACTION_PROMPT_FILENAME = "extraction_prompt.md"
MUTATIONS_HELPER = "helpers/workload-mutations.sh"
GRAPH_READ_HELPER = "helpers/workload-graph-read.sh"
MUTATION_EXAMPLES = "helpers/mutation-examples.jsonl"

EXTRACTION_JOB_INVOKE_PROMPT = (
    "You are running a Kartograph extraction job in /workspace. "
    f"Read {EXTRACTION_PROMPT_FILENAME}, job-context.json, and sources-index.json, then follow "
    "the instructions completely. For maintenance jobs, sources-index.json layout.mode is "
    "maintenance_commit_snapshots — read baseline/HEAD paths and diff paths from layout.target_files. "
    "Read job-context.json target_instances for graph_id and "
    "properties_missing before querying the graph. For existing instances, fetch live properties "
    f"with `bash {GRAPH_READ_HELPER} search-by-slug <slug> --entity-type <Type> --out "
    "mutations/current_<slug>.json` before editing. Copy JSONL shapes from "
    f"{MUTATION_EXAMPLES} when writing mutations. Write JSONL batches under mutations/, validate with "
    f"`bash {MUTATIONS_HELPER} validate mutations/<batch>.jsonl`, then apply with "
    f"`bash {MUTATIONS_HELPER} apply mutations/<batch>.jsonl`. Do not finish until apply "
    "succeeds and mutations/result.json reports operations_applied > 0."
)


def build_extraction_job_invoke_prompt(*, workspace_dir: str = "/workspace") -> str:
    """Return the one-shot claude-code -p prompt for one extraction job run."""
    prompt = EXTRACTION_JOB_INVOKE_PROMPT
    if workspace_dir != "/workspace":
        prompt = prompt.replace("/workspace", workspace_dir.rstrip("/"))
    return prompt


def write_extraction_prompt_file(*, workdir: Path, prompt: str) -> Path:
    """Materialize the full job instructions for the agent to read from disk."""
    path = workdir / EXTRACTION_PROMPT_FILENAME
    path.write_text(prompt.strip() + "\n", encoding="utf-8")
    return path


def build_maintenance_target_files_prompt_section(*, job: ExtractionJobRecord) -> str:
    """Describe commit-scoped repository-files layout for maintenance jobs."""
    if not job.target_files:
        return ""

    lines = [
        "## Maintenance repository layout",
        "Changed files use commit-first directories under repository-files/:",
        "- Baseline (last extraction): repository-files/{baseline_commit}/{repository_folder}/{path}",
        "- HEAD (branch tip): repository-files/{head_commit}/{repository_folder}/{path}",
        "- Unified diff: repository-files/diffs/{baseline_commit}..{head_commit}/{repository_folder}/{path}.patch",
        "See sources-index.json layout.target_files for exact paths per assigned file.",
        "",
        "### Assigned files",
    ]
    for target_file in job.target_files:
        baseline = target_file.baseline_commit or "<baseline>"
        head = target_file.head_commit or "<head>"
        status = target_file.change_status or "modified"
        lines.append(
            f"- [{status}] {target_file.repository_folder}/{target_file.path}"
        )
        lines.append(f"  - baseline: repository-files/{baseline}/{target_file.repository_folder}/{target_file.path}")
        if status != "removed":
            lines.append(
                f"  - head: repository-files/{head}/{target_file.repository_folder}/{target_file.path}"
            )
        if target_file.patch and target_file.baseline_commit and target_file.head_commit:
            lines.append(
                "  - diff: "
                f"repository-files/diffs/{target_file.baseline_commit}..{target_file.head_commit}/"
                f"{target_file.repository_folder}/{target_file.path}.patch"
            )
    return "\n".join(lines)


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
                "Process only the instances listed below. Each entry in job-context.json",
                "target_instances includes graph_id (for UPDATE/DELETE) and properties_missing",
                "(ontology fields still empty on the live node). Read source files under",
                "repository-files/ when materialized (see job-context.json repository_files and",
                "instance property paths such as config_path, config_file_path, or source_path).",
                "Use the workload API for additional graph context and emit JSONL mutations for",
                "new or updated entities and relationships.",
                "",
            ]
        )
        for instance in job.target_instances:
            lines.append(f"- {instance.entity_type}: {instance.slug}")
        lines.append("")
    if job.target_files:
        if job.job_set_name == MAINTENANCE_JOB_SET_NAME:
            lines.append(build_maintenance_target_files_prompt_section(job=job))
            lines.append("")
        else:
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
            "job-context.json repository_files reports materialization status:",
            "- paths_not_found lists instance-referenced paths with no JobPackage match.",
            "- When paths_not_found is non-empty but files_written > 0, targeted paths missed but",
            "  files are available under repository-files/ (often via directory prefix matching",
            "  or a full-repo fallback) — search repository-files/ before concluding sources are absent.",
            "If files_written is 0, report repository_files.warnings and still apply updates",
            "supported by graph context when possible.",
            "",
            "## JSONL mutation format",
            f"Copy field names and structure from `{MUTATION_EXAMPLES}` in the workspace.",
            "Every line needs both op (CREATE|UPDATE|DELETE) and type (node|edge).",
            "Use set_properties (not properties). UPDATE and DELETE require top-level id.",
            "Existing instances must use UPDATE with graph_id from job-context.json target_instances.",
            "",
            "## Editing existing instances (token-efficient)",
            "UPDATE merges `set_properties` into the live node — properties you omit are preserved.",
            "Include only the fields you are changing in each UPDATE line; never resubmit every",
            "property when a subset changed.",
            "`properties_missing` lists empty ontology fields only. Populated fields you refine",
            "(for example a long `description`) are not listed — fetch current values before editing.",
            f"- Fetch one instance: `bash {GRAPH_READ_HELPER} search-by-slug <slug> --entity-type <Type> "
            "--out mutations/current_<slug>.json`",
            f"- List by type: `bash {GRAPH_READ_HELPER} instances <EntityType> --limit 100 --offset 0`",
            "For surgical edits to long text: load the saved JSON, edit the target property with",
            "Bash/python, then write one UPDATE line with only the changed keys in `set_properties`.",
            "Generate JSONL programmatically (Write + python3); do not paste full prior text into chat.",
            "Prefer UPDATE over CREATE when graph_id is present in job-context.json.",
            "",
            "## Graph read workflow (required before UPDATE)",
            f"Use `bash {GRAPH_READ_HELPER}` (reads api_base_url and workload_token from job-context.json):",
            f"- `bash {GRAPH_READ_HELPER} search-by-slug <slug> [--entity-type <Type>] [--out FILE]`",
            f"- `bash {GRAPH_READ_HELPER} instances <EntityType> [--limit N] [--offset N] [--out FILE]`",
            f"- `bash {GRAPH_READ_HELPER} ontology [--out FILE]`",
            f"- `bash {GRAPH_READ_HELPER} authoring-guide [--out FILE]`",
            "",
            "## Mutations workflow (required)",
            "This container has no Kartograph MCP tools. Use the bundled helper script:",
            f"- Validate: `bash {MUTATIONS_HELPER} validate mutations/<batch>.jsonl`",
            f"- Apply: `bash {MUTATIONS_HELPER} apply mutations/<batch>.jsonl`",
            "The helper reads api_base_url and workload_token from job-context.json, calls the",
            "workload API, and writes mutations/result.json (the CI verdict artifact).",
            "Always validate before apply. Do not finish until apply succeeds.",
            "",
            "Manual curl (only if helpers fail): base `{api_base_url}/extraction/workloads`,",
            "header `X-Workload-Token: <workload_token>`, POST `/mutations/validate` or",
            "`/mutations/apply` with JSON body `{\"jsonl\": \"<file contents>\"}`.",
            "",
            "Other useful GET endpoints (prefer workload-graph-read.sh):",
            "- `/schema/authoring-guide` — JSONL mutation shapes and rules",
            "- `/schema/ontology` — current graph schema",
            "- `/graph/search-by-slug?slug=...&entity_type=...` — one instance with full properties",
            "- `/graph/instances?entity_type=...` — paginated instances by type",
            "",
            "## Completion",
            "When finished, mutations/result.json must show action=apply and operations_applied > 0.",
            "Do not modify files outside repository-files/ except mutations/ and helpers/.",
        ]
    )
    return "\n".join(lines)
