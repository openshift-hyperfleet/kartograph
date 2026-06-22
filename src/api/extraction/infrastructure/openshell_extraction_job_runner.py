"""Run extraction jobs inside OpenShell sandboxes via agentic-ci patterns."""

from __future__ import annotations

import json
import os
import shlex
import tempfile
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from agentic_ci import otel
from agentic_ci.harness import create_harness

from extraction.domain.extraction_job import ExtractionJobRecord
from extraction.domain.prepared_extraction_job_run import PreparedExtractionJobRun
from extraction.infrastructure.extraction_job_activity import (
    activity_log_path,
    append_activity_line,
    append_activity_message,
    format_activity_log_line,
    format_claude_code_stream_line,
)
from extraction.infrastructure.extraction_job_metrics import merge_extraction_job_metrics
from extraction.infrastructure.extraction_job_mutation_metrics import (
    reconcile_mutation_metrics,
)
from extraction.infrastructure.extraction_job_prompt import (
    build_extraction_job_invoke_prompt,
    write_extraction_prompt_file,
)
from extraction.infrastructure.maintenance_job_prompt import build_job_run_prompt
from extraction.infrastructure.extraction_job_verdict import require_successful_apply
from extraction.infrastructure.extraction_job_workdir_layout import mutation_result_path
from extraction.infrastructure.extraction_job_workdir_materializer import (
    ExtractionJobWorkdirMaterializer,
)
from extraction.infrastructure.openshell.extraction_sandbox_pool import (
    resolve_extraction_sandbox_assignment,
)
from extraction.infrastructure.openshell import gateway as openshell_gateway
from extraction.infrastructure.openshell import sandbox as openshell_sandbox
from extraction.infrastructure.openshell.audit import LoggingOpenShellRuntimeProbe
from extraction.infrastructure.openshell.inference_env import (
    build_openshell_inference_env_script_lines,
    insert_claude_bare_flag,
    insert_vertex_compatible_effort,
)
from extraction.infrastructure.openshell.cli import OpenShellCliError
from extraction.infrastructure.openshell.runtime_env import apply_openshell_cli_env
from extraction.infrastructure.openshell.vertex_provider import ensure_vertex_provider
from extraction.infrastructure.workload_credential_issuer import INTERACTIVE_WORKLOAD_SCOPES
from extraction.infrastructure.workload_runtime_factory import get_workload_credential_issuer
from extraction.infrastructure.workload_runtime_settings import (
    ExtractionWorkloadRuntimeSettings,
    get_extraction_workload_runtime_settings,
)
from extraction.ports.extraction_job_runner import IExtractionJobRunner

_AGENTIC_CI_ENV_SCRIPT = "/tmp/.agentic-ci-env.sh"


def _patch_job_context_api_base(workdir: Path, api_base_url: str) -> None:
    context_path = workdir / "job-context.json"
    context = json.loads(context_path.read_text(encoding="utf-8"))
    context["api_base_url"] = api_base_url.rstrip("/")
    context_path.write_text(json.dumps(context, indent=2) + "\n", encoding="utf-8")


def _api_host_from_base_url(api_base_url: str) -> str:
    parsed = urlparse(api_base_url)
    if parsed.hostname:
        port_suffix = f":{parsed.port}" if parsed.port else ""
        return f"{parsed.hostname}{port_suffix}"
    return "api:8000"


class OpenShellExtractionJobRunner(IExtractionJobRunner):
    """Execute one extraction job inside an OpenShell sandbox with network policy."""

    def __init__(
        self,
        *,
        settings: ExtractionWorkloadRuntimeSettings | None = None,
        workdir_materializer: ExtractionJobWorkdirMaterializer | None = None,
    ) -> None:
        self._settings = settings or get_extraction_workload_runtime_settings()
        self._workdir_materializer = workdir_materializer
        self._harness = create_harness(self._settings.agentic_ci_harness)
        self._probe = LoggingOpenShellRuntimeProbe()

    async def prepare_for_run(
        self,
        job: ExtractionJobRecord,
        *,
        tenant_id: str,
    ) -> PreparedExtractionJobRun:
        if self._workdir_materializer is None:
            raise RuntimeError("OpenShellExtractionJobRunner requires a workdir materializer")
        credentials = get_workload_credential_issuer().issue(
            tenant_id=tenant_id,
            knowledge_graph_id=job.knowledge_graph_id,
            extra_scopes=(*INTERACTIVE_WORKLOAD_SCOPES, f"job:{job.job_id}"),
        )
        workdir = await self._workdir_materializer.prepare(
            job=job,
            tenant_id=tenant_id,
            credentials=credentials,
        )
        _patch_job_context_api_base(workdir, self._settings.sandbox_reachable_api_base_url())
        prompt = build_job_run_prompt(job=job)
        return PreparedExtractionJobRun(workdir=workdir, prompt=prompt)

    async def run_prepared(
        self,
        job: ExtractionJobRecord,
        *,
        prepared: PreparedExtractionJobRun,
    ) -> dict[str, Any]:
        return await self._run_in_sandbox(
            job=job,
            workdir=prepared.workdir,
            prompt=prepared.prompt,
        )

    async def run(self, job: ExtractionJobRecord, *, tenant_id: str) -> dict[str, Any]:
        prepared = await self.prepare_for_run(job, tenant_id=tenant_id)
        return await self.run_prepared(job, prepared=prepared)

    async def _run_in_sandbox(
        self,
        *,
        job: ExtractionJobRecord,
        workdir: Path,
        prompt: str,
    ) -> dict[str, Any]:
        import asyncio

        return await asyncio.to_thread(self._run_in_sandbox_sync, job, workdir, prompt)

    def _run_in_sandbox_sync(
        self,
        job: ExtractionJobRecord,
        workdir: Path,
        prompt: str,
    ) -> dict[str, Any]:
        assignment = resolve_extraction_sandbox_assignment(job, self._settings)
        sandbox_name = assignment.sandbox_name
        run_dir = tempfile.mkdtemp(prefix="kartograph-openshell-")
        otel_proc = None
        otel_log: Path | None = None

        try:
            openshell_gateway.ensure_gateway_registered(
                gateway_name=self._settings.openshell_gateway_name,
                gateway_url=self._settings.openshell_gateway_url,
            )
            apply_openshell_cli_env(self._settings)
            if self._settings.vertex_enabled():
                ensure_vertex_provider(
                    provider_name=self._settings.openshell_provider_name,
                    project_id=self._settings.vertex_project_id,
                    region=self._settings.vertex_region,
                    gcloud_config_mount=self._settings.gcloud_config_mount,
                    auth_mode="vertex",
                    model=self._resolve_model(),
                )
            sandbox_image = self._settings.openshell_extraction_sandbox_image()
            created = False
            if assignment.reuse and openshell_sandbox.sandbox_exists(sandbox_name):
                openshell_sandbox.emit_lifecycle(
                    sandbox_name=sandbox_name,
                    action="reused",
                    probe=self._probe,
                    image=sandbox_image,
                    job_id=job.job_id,
                )
            else:
                openshell_sandbox.delete_sandbox(sandbox_name)
                openshell_sandbox.create_sandbox(
                    name=sandbox_name,
                    image=sandbox_image,
                    provider_name=self._settings.openshell_provider_name,
                )
                openshell_sandbox.emit_lifecycle(
                    sandbox_name=sandbox_name,
                    action="created",
                    probe=self._probe,
                    image=sandbox_image,
                    job_id=job.job_id,
                )
                created = True
            work_mount = self._settings.openshell_container_work_mount
            if assignment.reuse and not created:
                self._reset_sandbox_workspace(
                    sandbox_name=sandbox_name,
                    work_mount=work_mount,
                )
            write_extraction_prompt_file(workdir=workdir, prompt=prompt)
            openshell_sandbox.upload_directory_contents(
                sandbox_name=sandbox_name,
                local_dir=str(workdir),
                dest=work_mount,
            )
            if created or not assignment.reuse:
                openshell_sandbox.apply_policy(
                    sandbox_name=sandbox_name,
                    workload="extraction_job",
                    policy_dir=self._settings.openshell_policy_dir or None,
                    api_host=_api_host_from_base_url(self._settings.sandbox_reachable_api_base_url()),
                    vertex_region=(
                        self._settings.vertex_region
                        if self._settings.vertex_enabled()
                        else None
                    ),
                    policy_enforcement=self._settings.openshell_policy_enforcement,
                    probe=self._probe,
                )

            otel_proc, otel_port, otel_log_path, otel_rate_file = otel.start_collector(run_dir)
            otel_log = Path(otel_log_path)
            model = self._resolve_model()
            invoke_prompt = build_extraction_job_invoke_prompt(workspace_dir=work_mount)
            log_path = activity_log_path(workdir)
            slot_note = (
                f" (worker sandbox {assignment.slot})"
                if assignment.slot is not None
                else ""
            )
            append_activity_line(
                log_path,
                f"📡 Processing job {job.job_id} on {job.worker_id or 'worker'} "
                f"in OpenShell sandbox {sandbox_name}{slot_note}...",
            )
            rc = self._run_agent(
                sandbox_name=sandbox_name,
                model=model,
                otel_port=otel_port,
                otel_rate_file=otel_rate_file,
                invoke_prompt=invoke_prompt,
                timeout_seconds=self._settings.agentic_ci_timeout_seconds,
                activity_log_path=log_path,
            )
            append_activity_line(log_path, f"✅ OpenShell sandbox finished with exit code {rc}")
            if otel_proc is not None:
                otel.stop_collector(otel_proc)
                otel_proc = None
            if rc != 0:
                detail = self._read_activity_log_tail(log_path)
                raise RuntimeError(
                    "OpenShell extraction sandbox exited with code "
                    f"{rc} for job {job.job_id}"
                    + (f": {detail}" if detail else "")
                )
            self._sync_mutation_artifacts_from_sandbox(
                sandbox_name=sandbox_name,
                workdir=workdir,
                work_mount=work_mount,
            )
            verdict = require_successful_apply(workdir)
            append_activity_message(
                log_path,
                kind="done",
                text=(
                    f"Applied {verdict.operations_applied} graph mutation operation(s) "
                    "via workload API."
                ),
            )
            metrics = merge_extraction_job_metrics(
                otel_log=otel_log,
                workdir=workdir,
                activity_log=log_path,
            )
            metrics = reconcile_mutation_metrics(
                metrics,
                workdir=workdir,
                operations_applied=verdict.operations_applied,
            )
            metrics["operations_applied"] = verdict.operations_applied
            if assignment.slot is not None:
                metrics["sandbox_slot"] = assignment.slot
            metrics["sandbox_name"] = sandbox_name
            return metrics
        finally:
            if otel_proc is not None:
                otel.stop_collector(otel_proc)
            if not assignment.reuse:
                openshell_sandbox.delete_sandbox(sandbox_name)
                openshell_sandbox.emit_lifecycle(
                    sandbox_name=sandbox_name,
                    action="deleted",
                    probe=self._probe,
                    job_id=job.job_id,
                )

    def _resolve_model(self) -> str:
        configured = self._settings.agentic_ci_model.strip()
        if configured:
            return configured
        model_env = self._harness.model_env_var()
        from_env = os.environ.get(model_env, "").strip()
        if from_env:
            return from_env
        return self._harness.default_model()

    @staticmethod
    def _reset_sandbox_workspace(*, sandbox_name: str, work_mount: str) -> None:
        """Clear the prior job workspace before uploading the next job package."""
        quoted = shlex.quote(work_mount.rstrip("/"))
        openshell_sandbox.run_sandbox_exec(
            sandbox_name=sandbox_name,
            command=[
                "bash",
                "-lc",
                f"mkdir -p {quoted} && find {quoted} -mindepth 1 -maxdepth 1 -exec rm -rf -- {{}} +",
            ],
        )

    @staticmethod
    def _read_activity_log_tail(log_path: Path, *, max_lines: int = 8) -> str:
        if not log_path.is_file():
            return ""
        lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines()
        tail = [line.strip() for line in lines[-max_lines:] if line.strip()]
        return " | ".join(tail)

    @staticmethod
    def _sync_mutation_artifacts_from_sandbox(
        *,
        sandbox_name: str,
        workdir: Path,
        work_mount: str,
    ) -> None:
        """Copy mutations/ artifacts from the sandbox back to the host workdir."""
        remote_mutations = f"{work_mount.rstrip('/')}/mutations"
        try:
            openshell_sandbox.download_directory_contents(
                sandbox_name=sandbox_name,
                remote_dir=remote_mutations,
                local_dir=workdir,
            )
        except OpenShellCliError:
            if mutation_result_path(workdir).is_file():
                return
            openshell_sandbox.download_path(
                sandbox_name=sandbox_name,
                sandbox_path=f"{remote_mutations}/result.json",
                local_path=str(mutation_result_path(workdir)),
            )

    def _write_env_script_in_sandbox(
        self,
        *,
        sandbox_name: str,
        model: str,
        otel_port: int,
        otel_rate_file: str | None,
    ) -> None:
        """Upload env script into the sandbox (agentic-ci OpenShellBackend pattern)."""
        if self._settings.vertex_enabled() and self._harness.auth_mode == "vertex":
            lines = build_openshell_inference_env_script_lines(
                workspace_dir=self._settings.openshell_container_work_mount,
                otel_port=otel_port,
                otel_rate_file=otel_rate_file,
            )
        else:
            lines = self._harness.build_env_script_lines(otel_port, otel_rate_file)
        lines.append("export CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1")
        lines.append(f"export AGENT_MODEL={shlex.quote(model)}")
        script = "\n".join(lines) + "\n"

        with tempfile.NamedTemporaryFile(
            mode="w",
            prefix="agentic-ci-env-",
            suffix=".sh",
            delete=False,
        ) as handle:
            handle.write(script)
            local_path = handle.name

        try:
            openshell_sandbox.upload_path(
                sandbox_name=sandbox_name,
                local_path=local_path,
            )
            remote_name = Path(local_path).name
            openshell_sandbox.run_sandbox_exec(
                sandbox_name=sandbox_name,
                command=[
                    "bash",
                    "-c",
                    f"mv {shlex.quote(remote_name)} {_AGENTIC_CI_ENV_SCRIPT}",
                ],
            )
        finally:
            Path(local_path).unlink(missing_ok=True)

    def _run_agent(
        self,
        *,
        sandbox_name: str,
        model: str,
        otel_port: int,
        otel_rate_file: str | None,
        invoke_prompt: str,
        timeout_seconds: int,
        activity_log_path: Path,
    ) -> int:
        self._write_env_script_in_sandbox(
            sandbox_name=sandbox_name,
            model=model,
            otel_port=otel_port,
            otel_rate_file=otel_rate_file,
        )
        agent_args = self._harness.build_args(invoke_prompt, model)
        if self._settings.vertex_enabled() and self._harness.auth_mode == "vertex":
            agent_args = insert_claude_bare_flag(agent_args)
            agent_args = insert_vertex_compatible_effort(agent_args)
        work_mount = shlex.quote(self._settings.openshell_container_work_mount)
        cmd = [
            "bash",
            "-c",
            f". {_AGENTIC_CI_ENV_SCRIPT} && cd {work_mount} && exec \"$@\"",
            "--",
            *agent_args,
        ]
        started = time.monotonic()
        proc = openshell_sandbox.exec_streaming(
            sandbox_name=sandbox_name,
            command=cmd,
        )
        captured_tail: list[str] = []
        stream_log_path = activity_log_path.parent / "agent_stream.jsonl"
        try:
            assert proc.stdout is not None
            with activity_log_path.open("a", encoding="utf-8") as log_handle, stream_log_path.open(
                "a",
                encoding="utf-8",
            ) as stream_handle:
                for line in proc.stdout:
                    if time.monotonic() - started > timeout_seconds:
                        proc.kill()
                        append_activity_message(
                            activity_log_path,
                            kind="error",
                            text=f"OpenShell sandbox timed out after {timeout_seconds}s",
                        )
                        raise RuntimeError(
                            f"OpenShell extraction sandbox timed out after {timeout_seconds}s"
                        )
                    cleaned = line.rstrip("\n")
                    if not cleaned:
                        continue
                    if cleaned.startswith("{"):
                        stream_handle.write(cleaned + "\n")
                        stream_handle.flush()
                    parsed = format_claude_code_stream_line(cleaned)
                    if parsed:
                        ts = datetime.now(UTC).isoformat()
                        for kind, text in parsed:
                            log_handle.write(f"{ts} {format_activity_log_line(kind=kind, text=text)}\n")
                            captured_tail.append(text)
                    else:
                        ts = datetime.now(UTC).isoformat()
                        log_handle.write(f"{ts} {format_activity_log_line(kind='info', text=cleaned)}\n")
                        captured_tail.append(cleaned)
                    log_handle.flush()
                    if len(captured_tail) > 20:
                        captured_tail.pop(0)
            rc = proc.wait(timeout=30)
        except Exception:
            proc.kill()
            raise
        return int(rc)
