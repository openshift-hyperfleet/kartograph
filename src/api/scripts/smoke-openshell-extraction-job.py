#!/usr/bin/env python3
"""Smoke-test OpenShell extraction job sandbox bootstrap and claude launch."""

from __future__ import annotations

import json
import shlex
import sys
import tempfile
from pathlib import Path

from agentic_ci.harness import create_harness

from extraction.infrastructure.extraction_job_prompt import (
    build_extraction_job_invoke_prompt,
    write_extraction_prompt_file,
)
from extraction.infrastructure.extraction_job_workdir_layout import prepare_agentic_ci_workspace
from extraction.infrastructure.openshell import gateway as openshell_gateway
from extraction.infrastructure.openshell import sandbox as openshell_sandbox
from extraction.infrastructure.openshell.cli import run_openshell
from extraction.infrastructure.openshell.inference_env import insert_claude_bare_flag
from extraction.infrastructure.openshell.runtime_env import apply_openshell_cli_env
from extraction.infrastructure.openshell.vertex_provider import ensure_vertex_provider
from extraction.infrastructure.openshell_extraction_job_runner import OpenShellExtractionJobRunner
from extraction.infrastructure.workload_runtime_settings import get_extraction_workload_runtime_settings

_AGENTIC_CI_ENV_SCRIPT = "/tmp/.agentic-ci-env.sh"


def main() -> int:
    settings = get_extraction_workload_runtime_settings()
    harness = create_harness(settings.agentic_ci_harness)
    sandbox_name = "kartograph-extract-smoke-test"
    work_mount = settings.openshell_container_work_mount
    workdir = Path(tempfile.mkdtemp(prefix="kartograph-extract-smoke-"))
    runner = OpenShellExtractionJobRunner(settings=settings)

    prepare_agentic_ci_workspace(workdir, container_run_uid=None, container_run_gid=None)
    (workdir / "job-context.json").write_text(
        json.dumps(
            {
                "api_base_url": settings.sandbox_reachable_api_base_url(),
                "workload_token": "smoke",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (workdir / "sources-index.json").write_text("{}\n", encoding="utf-8")
    write_extraction_prompt_file(workdir=workdir, prompt="Smoke test job.")

    print("workdir:", workdir)
    print("image:", settings.openshell_extraction_sandbox_image())

    openshell_gateway.ensure_gateway_registered(
        gateway_name=settings.openshell_gateway_name,
        gateway_url=settings.openshell_gateway_url,
    )
    apply_openshell_cli_env(settings)
    if settings.vertex_enabled():
        ensure_vertex_provider(
            provider_name=settings.openshell_provider_name,
            project_id=settings.vertex_project_id,
            region=settings.vertex_region,
            gcloud_config_mount=settings.gcloud_config_mount,
            auth_mode="vertex",
            model=runner._resolve_model(),
        )
    openshell_sandbox.delete_sandbox(sandbox_name)
    try:
        openshell_sandbox.create_sandbox(
            name=sandbox_name,
            image=settings.openshell_extraction_sandbox_image(),
            provider_name=settings.openshell_provider_name,
        )
        write_extraction_prompt_file(workdir=workdir, prompt="Smoke test job.")
        openshell_sandbox.upload_directory_contents(
            sandbox_name=sandbox_name,
            local_dir=str(workdir),
            dest=work_mount,
        )
        openshell_sandbox.apply_policy(
            sandbox_name=sandbox_name,
            workload="extraction_job",
            policy_dir=settings.openshell_policy_dir or None,
            api_host="host.docker.internal:8000",
            vertex_region=settings.vertex_region if settings.vertex_enabled() else None,
            policy_enforcement=settings.openshell_policy_enforcement,
        )

        version = run_openshell(
            [
                "sandbox",
                "exec",
                "--name",
                sandbox_name,
                "--no-tty",
                "--",
                "/usr/local/bin/claude",
                "--version",
            ],
            timeout=60.0,
        )
        print("claude_version_rc:", version.returncode)
        print("claude_version:", (version.stdout or version.stderr or "").strip()[:200])
        if version.returncode != 0:
            return 1

        listing = run_openshell(
            [
                "sandbox",
                "exec",
                "--name",
                sandbox_name,
                "--no-tty",
                "--",
                "bash",
                "-c",
                f"ls -la {shlex.quote(work_mount)}",
            ],
            timeout=60.0,
        )
        print("sandbox_listing:\n", listing.stdout)
        if "extraction_prompt.md" not in (listing.stdout or ""):
            print("FAIL: extraction_prompt.md missing in sandbox")
            return 1

        model = runner._resolve_model()
        invoke_prompt = build_extraction_job_invoke_prompt(workspace_dir=work_mount)
        runner._write_env_script_in_sandbox(
            sandbox_name=sandbox_name,
            model=model,
            otel_port=4318,
            otel_rate_file=None,
        )
        agent_args = harness.build_args(
            "Reply with exactly the word OK and nothing else.",
            model,
        )
        if settings.vertex_enabled() and harness.auth_mode == "vertex":
            agent_args = insert_claude_bare_flag(agent_args)
        shell_cmd = [
            "bash",
            "-c",
            f". {_AGENTIC_CI_ENV_SCRIPT} && cd {work_mount} && exec \"$@\"",
            "--",
            *agent_args,
        ]
        print("running_short_claude_invoke...")
        res = run_openshell(
            ["sandbox", "exec", "--name", sandbox_name, "--no-tty", "--", *shell_cmd],
            timeout=180.0,
            check=False,
        )
        print("claude_invoke_rc:", res.returncode)
        combined = ((res.stdout or "") + (res.stderr or "")).strip()
        if combined:
            print("claude_output:", combined[:3000])
        if res.returncode != 0:
            return 1
    finally:
        openshell_sandbox.delete_sandbox(sandbox_name)

    print("SMOKE_TEST_PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
