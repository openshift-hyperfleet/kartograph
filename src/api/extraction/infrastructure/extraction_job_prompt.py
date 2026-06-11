"""Build prompts for extraction job agent runs."""

from __future__ import annotations

from extraction.domain.extraction_job import ExtractionJobRecord


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
            "## Completion",
            "When finished, ensure all required mutations are applied through the workload API.",
            "Do not modify files outside repository-files/.",
        ]
    )
    return "\n".join(lines)
