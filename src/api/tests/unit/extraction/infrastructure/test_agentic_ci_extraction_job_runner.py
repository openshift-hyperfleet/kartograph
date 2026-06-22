"""Unit tests for agentic-ci extraction container credential wiring."""

from __future__ import annotations

from pathlib import Path

from extraction.infrastructure.agentic_ci_extraction_job_runner import (
    AgenticCiExtractionJobRunner,
    _patch_job_context_api_base,
    _strip_harness_binary,
)
from extraction.infrastructure.extraction_job_prompt import (
    EXTRACTION_JOB_INVOKE_PROMPT,
    write_extraction_prompt_file,
)
from extraction.infrastructure.workload_runtime_settings import (
    ExtractionWorkloadRuntimeSettings,
)


def test_strip_harness_binary_removes_leading_claude() -> None:
    command = [
        "claude",
        "--permission-mode",
        "bypassPermissions",
        "-p",
        "do the job",
    ]

    assert _strip_harness_binary(command) == [
        "--permission-mode",
        "bypassPermissions",
        "-p",
        "do the job",
    ]


def test_write_extraction_prompt_file_materializes_instructions(tmp_path: Path) -> None:
    write_extraction_prompt_file(workdir=tmp_path, prompt="Extract all entities.")

    prompt_path = tmp_path / "extraction_prompt.md"
    assert prompt_path.is_file()
    assert prompt_path.read_text(encoding="utf-8") == "Extract all entities.\n"


def test_extraction_job_invoke_prompt_references_materialized_file() -> None:
    assert "extraction_prompt.md" in EXTRACTION_JOB_INVOKE_PROMPT
    assert "job-context.json" in EXTRACTION_JOB_INVOKE_PROMPT
    assert "helpers/workload-mutations.sh" in EXTRACTION_JOB_INVOKE_PROMPT
    assert "helpers/workload-graph-read.sh" in EXTRACTION_JOB_INVOKE_PROMPT
    assert "mutations/result.json" in EXTRACTION_JOB_INVOKE_PROMPT


def test_patch_job_context_api_base_rewrites_host_reachable_url(tmp_path: Path) -> None:
    context_path = tmp_path / "job-context.json"
    context_path.write_text(
        '{"api_base_url": "http://api:8000", "workload_token": "tok"}',
        encoding="utf-8",
    )

    _patch_job_context_api_base(tmp_path, "http://127.0.0.1:8000")

    import json

    updated = json.loads(context_path.read_text(encoding="utf-8"))
    assert updated["api_base_url"] == "http://127.0.0.1:8000"
    assert updated["workload_token"] == "tok"


def test_build_binds_mounts_full_gcloud_config_for_vertex() -> None:
    runner = AgenticCiExtractionJobRunner(
        settings=ExtractionWorkloadRuntimeSettings(
            gcloud_config_mount="/host/.config/gcloud",
            gcloud_config_container_path="/gcloud/config",
        )
    )
    binds = runner._build_binds(workdir=__import__("pathlib").Path("/tmp/job-workdir"))

    assert "/tmp/job-workdir:/workspace:z" in binds
    assert "/host/.config/gcloud:/gcloud/config:ro,z" in binds


def test_build_container_env_sets_google_application_credentials_for_vertex(
    monkeypatch,
) -> None:
    monkeypatch.setenv("CLAUDE_CODE_USE_VERTEX", "1")
    runner = AgenticCiExtractionJobRunner(
        settings=ExtractionWorkloadRuntimeSettings(
            vertex_project_id="my-project",
            vertex_region="us-east5",
            gcloud_config_mount="/host/.config/gcloud",
            gcloud_config_container_path="/gcloud/config",
        )
    )
    env = runner._build_container_env(otel_port=0)

    assert env["CLAUDE_MODEL"] == runner._resolve_model()
    assert env["AGENT_MODEL"] == runner._resolve_model()
    assert env["CLAUDE_CODE_USE_VERTEX"] == "1"
    assert env["ANTHROPIC_VERTEX_PROJECT_ID"] == "my-project"
    assert env["GOOGLE_APPLICATION_CREDENTIALS"] == (
        "/gcloud/config/application_default_credentials.json"
    )
    assert env["CLOUDSDK_CONFIG"] == "/gcloud/config"
    assert env["HOME"] == "/tmp"
