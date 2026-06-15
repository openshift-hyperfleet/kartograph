"""Unit tests for OpenShell extraction job runner sandbox wiring."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from extraction.infrastructure.openshell.cli import OpenShellCliError
from extraction.infrastructure.openshell_extraction_job_runner import OpenShellExtractionJobRunner
from extraction.infrastructure.workload_runtime_settings import ExtractionWorkloadRuntimeSettings


def test_openshell_extraction_sandbox_image_uses_agentic_ci_claude_sandbox() -> None:
    settings = ExtractionWorkloadRuntimeSettings(
        sticky_image="kartograph-agent-runtime:dev",
        openshell_extraction_image="quay.io/aipcc/agentic-ci/claude-sandbox:latest",
        agentic_ci_image="ghcr.io/opendatahub-io/ai-helpers:latest",
    )

    assert (
        settings.openshell_extraction_sandbox_image()
        == "quay.io/aipcc/agentic-ci/claude-sandbox:latest"
    )
    assert settings.openshell_extraction_sandbox_image() != settings.sticky_image
    assert settings.openshell_extraction_sandbox_image() != settings.agentic_ci_image


def test_run_agent_uses_harness_claude_binary() -> None:
    runner = OpenShellExtractionJobRunner()

    command = runner._harness.build_args("Extract entities.", "claude-opus-4-6")

    assert command[0] == "claude"
    assert "-p" in command


def test_build_extraction_job_invoke_prompt_uses_openshell_workspace() -> None:
    from extraction.infrastructure.extraction_job_prompt import build_extraction_job_invoke_prompt

    prompt = build_extraction_job_invoke_prompt(workspace_dir="/sandbox")

    assert "in /sandbox." in prompt
    assert "/workspace" not in prompt


def test_extraction_provider_defaults_to_kartograph_gma() -> None:
    settings = ExtractionWorkloadRuntimeSettings()

    assert settings.openshell_provider_name == "kartograph-gma"


def test_run_agent_uses_inference_local_bare_for_vertex(monkeypatch) -> None:
    monkeypatch.setenv("CLAUDE_CODE_USE_VERTEX", "1")
    monkeypatch.setenv("ANTHROPIC_VERTEX_PROJECT_ID", "my-project")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    runner = OpenShellExtractionJobRunner()

    agent_args = runner._harness.build_args("Extract entities.", "claude-opus-4-6")
    from extraction.infrastructure.openshell.inference_env import insert_claude_bare_flag

    if runner._settings.vertex_enabled() and runner._harness.auth_mode == "vertex":
        agent_args = insert_claude_bare_flag(agent_args)

    assert agent_args[0] == "claude"
    assert agent_args[1] == "--bare"


def test_sync_mutation_artifacts_downloads_mutations_directory(tmp_path: Path) -> None:
    runner = OpenShellExtractionJobRunner()
    workdir = tmp_path / "job"

    with patch(
        "extraction.infrastructure.openshell_extraction_job_runner.openshell_sandbox.download_directory_contents",
    ) as download_dir:
        runner._sync_mutation_artifacts_from_sandbox(
            sandbox_name="kartograph-extract-job-1",
            workdir=workdir,
            work_mount="/sandbox",
        )

    download_dir.assert_called_once_with(
        sandbox_name="kartograph-extract-job-1",
        remote_dir="/sandbox/mutations",
        local_dir=workdir,
    )


def test_sync_mutation_artifacts_falls_back_to_result_json(tmp_path: Path) -> None:
    runner = OpenShellExtractionJobRunner()
    workdir = tmp_path / "job"

    with patch(
        "extraction.infrastructure.openshell_extraction_job_runner.openshell_sandbox.download_directory_contents",
        side_effect=OpenShellCliError("sandbox missing"),
    ), patch(
        "extraction.infrastructure.openshell_extraction_job_runner.openshell_sandbox.download_path",
    ) as download_file:
        runner._sync_mutation_artifacts_from_sandbox(
            sandbox_name="kartograph-extract-job-1",
            workdir=workdir,
            work_mount="/sandbox",
        )

    download_file.assert_called_once_with(
        sandbox_name="kartograph-extract-job-1",
        sandbox_path="/sandbox/mutations/result.json",
        local_path=str(workdir / "mutations" / "result.json"),
    )


def test_sync_mutation_artifacts_skips_fallback_when_result_exists(tmp_path: Path) -> None:
    runner = OpenShellExtractionJobRunner()
    workdir = tmp_path / "job"
    result = workdir / "mutations" / "result.json"
    result.parent.mkdir(parents=True)
    result.write_text('{"action":"apply","applied":true,"operations_applied":1,"errors":[]}\n')

    with patch(
        "extraction.infrastructure.openshell_extraction_job_runner.openshell_sandbox.download_directory_contents",
        side_effect=OpenShellCliError("sandbox missing"),
    ), patch(
        "extraction.infrastructure.openshell_extraction_job_runner.openshell_sandbox.download_path",
    ) as download_file:
        runner._sync_mutation_artifacts_from_sandbox(
            sandbox_name="kartograph-extract-job-1",
            workdir=workdir,
            work_mount="/sandbox",
        )

    download_file.assert_not_called()
