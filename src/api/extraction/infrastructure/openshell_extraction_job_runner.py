"""Run extraction jobs inside OpenShell sandboxes."""

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
from extraction.infrastructure.extraction_job_activity import (
    activity_log_path,
    append_activity_line,
    append_activity_message,
    format_activity_log_line,
    format_claude_code_stream_line,
)
from extraction.infrastructure.extraction_job_metrics import merge_extraction_job_metrics
from extraction.infrastructure.extraction_job_prompt import (
    EXTRACTION_JOB_INVOKE_PROMPT,
    build_extraction_job_prompt,
    write_extraction_prompt_file,
)
from extraction.infrastructure.extraction_job_verdict import require_successful_apply
from extraction.infrastructure.extraction_job_workdir_materializer import (
    ExtractionJobWorkdirMaterializer,
)
from extraction.infrastructure.openshell import gateway as openshell_gateway
from extraction.infrastructure.openshell import sandbox as openshell_sandbox
from extraction.infrastructure.openshell.audit import LoggingOpenShellRuntimeProbe
from extraction.infrastructure.workload_runtime_factory import get_workload_credential_issuer
from extraction.infrastructure.workload_runtime_settings import (
    ExtractionWorkloadRuntimeSettings,
    get_extraction_workload_runtime_settings,
)
from extraction.ports.extraction_job_runner import IExtractionJobRunner


def _strip_harness_binary(command: list[str]) -> list[str]:
    if command and command[0] in {"claude", "opencode"}:
        return command[1:]
    return command


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

    async def run(self, job: ExtractionJobRecord, *, tenant_id: str) -> dict[str, Any]:
        if self._workdir_materializer is None:
            raise RuntimeError("OpenShellExtractionJobRunner requires a workdir materializer")
        credentials = get_workload_credential_issuer().issue(
            tenant_id=tenant_id,
            knowledge_graph_id=job.knowledge_graph_id,
            extra_scopes=("workload:chat",),
        )
        workdir = await self._workdir_materializer.prepare(
            job=job,
            tenant_id=tenant_id,
            credentials=credentials,
        )
        _patch_job_context_api_base(workdir, self._settings.api_base_url)
        prompt = build_extraction_job_prompt(job=job)
        return await self._run_in_sandbox(job=job, workdir=workdir, prompt=prompt)

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
        sandbox_name = openshell_sandbox.sanitize_sandbox_name("kartograph-extract-", job.job_id)
        run_dir = tempfile.mkdtemp(prefix="kartograph-openshell-")
        otel_proc = None
        otel_log: Path | None = None

        try:
            openshell_gateway.ensure_gateway_registered(
                gateway_name=self._settings.openshell_gateway_name,
                gateway_url=self._settings.openshell_gateway_url,
            )
            openshell_sandbox.delete_sandbox(sandbox_name)
            openshell_sandbox.create_sandbox(
                name=sandbox_name,
                image=self._settings.agentic_ci_image,
                provider_name=self._settings.openshell_provider_name,
            )
            openshell_sandbox.emit_lifecycle(
                sandbox_name=sandbox_name,
                action="created",
                probe=self._probe,
                image=self._settings.agentic_ci_image,
                job_id=job.job_id,
            )
            openshell_sandbox.upload_path(
                sandbox_name=sandbox_name,
                local_path=str(workdir),
                dest="/workspace",
            )
            openshell_sandbox.apply_policy(
                sandbox_name=sandbox_name,
                workload="extraction_job",
                policy_dir=self._settings.openshell_policy_dir or None,
                api_host=_api_host_from_base_url(self._settings.api_base_url),
                policy_enforcement=self._settings.openshell_policy_enforcement,
                probe=self._probe,
            )

            otel_proc, otel_port, otel_log_path, _otel_rate = otel.start_collector(run_dir)
            otel_log = Path(otel_log_path)
            write_extraction_prompt_file(workdir=workdir, prompt=prompt)
            model = self._resolve_model()
            command = _strip_harness_binary(
                self._harness.build_args(EXTRACTION_JOB_INVOKE_PROMPT, model)
            )
            env_script = self._build_env_script(model=model, otel_port=otel_port)
            log_path = activity_log_path(workdir)
            append_activity_line(log_path, f"📡 Processing job {job.job_id} in OpenShell sandbox...")
            rc = self._run_agent(
                sandbox_name=sandbox_name,
                env_script=env_script,
                command=command,
                timeout_seconds=self._settings.agentic_ci_timeout_seconds,
                activity_log_path=log_path,
            )
            append_activity_line(log_path, f"✅ OpenShell sandbox finished with exit code {rc}")
            if otel_proc is not None:
                otel.stop_collector(otel_proc)
                otel_proc = None
            metrics = merge_extraction_job_metrics(
                otel_log=otel_log,
                workdir=workdir,
                activity_log=log_path,
            )
            if rc != 0:
                raise RuntimeError(
                    f"OpenShell extraction sandbox exited with code {rc} for job {job.job_id}"
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
            metrics["operations_applied"] = verdict.operations_applied
            return metrics
        finally:
            if otel_proc is not None:
                otel.stop_collector(otel_proc)
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

    def _build_env_script(self, *, model: str, otel_port: int) -> str:
        lines = self._harness.build_env_script_lines(otel_port, None)
        lines.append("export CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1")
        lines.append(f"export AGENT_MODEL={shlex.quote(model)}")
        lines.append("cd /workspace")
        return "\n".join(lines) + "\n"

    def _run_agent(
        self,
        *,
        sandbox_name: str,
        env_script: str,
        command: list[str],
        timeout_seconds: int,
        activity_log_path: Path,
    ) -> int:
        shell = (
            f"cat > /tmp/.kartograph-env.sh <<'EOF'\n{env_script}EOF\n"
            f". /tmp/.kartograph-env.sh && exec {' '.join(shlex.quote(part) for part in command)}"
        )
        started = time.monotonic()
        proc = openshell_sandbox.exec_streaming(
            sandbox_name=sandbox_name,
            command=["bash", "-lc", shell],
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
