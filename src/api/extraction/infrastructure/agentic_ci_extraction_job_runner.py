"""Run extraction jobs inside agentic-ci sandbox containers."""

from __future__ import annotations

import json
import os
import re
import subprocess
import tempfile
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from agentic_ci.harness import create_harness
from agentic_ci import otel

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
from extraction.infrastructure.extraction_job_prompt import (
    EXTRACTION_JOB_INVOKE_PROMPT,
    write_extraction_prompt_file,
)
from extraction.infrastructure.maintenance_job_prompt import build_job_run_prompt
from extraction.infrastructure.extraction_job_workdir_materializer import (
    ExtractionJobWorkdirMaterializer,
)
from extraction.infrastructure.extraction_job_verdict import require_successful_apply
from extraction.infrastructure.vertex_runtime_env import (
    build_gcloud_adc_env,
    build_gcloud_config_bind,
    build_vertex_container_env,
)
from extraction.infrastructure.workload_credential_issuer import INTERACTIVE_WORKLOAD_SCOPES
from extraction.infrastructure.workload_runtime_factory import get_workload_credential_issuer
from extraction.infrastructure.workload_runtime_settings import (
    ExtractionWorkloadRuntimeSettings,
    get_extraction_workload_runtime_settings,
)
from extraction.ports.extraction_job_runner import IExtractionJobRunner
from shared_kernel.container_runtime.factory import create_container_runtime
from shared_kernel.container_runtime.ports import ContainerRuntimeError

_CONTAINER_NAME_SAFE = re.compile(r"[^a-zA-Z0-9_.-]+")


def _sanitize_container_name(job_id: str) -> str:
    cleaned = _CONTAINER_NAME_SAFE.sub("-", job_id).strip("-")
    return f"kartograph-extract-{cleaned}"[:63].rstrip("-_.")


def _strip_harness_binary(command: list[str]) -> list[str]:
    """Drop the CLI binary when the image entrypoint already execs it."""
    if command and command[0] in {"claude", "opencode"}:
        return command[1:]
    return command


def _patch_job_context_api_base(workdir: Path, api_base_url: str) -> None:
    """Rewrite api_base_url so host-network job containers can reach the API."""
    context_path = workdir / "job-context.json"
    context = json.loads(context_path.read_text(encoding="utf-8"))
    context["api_base_url"] = api_base_url.rstrip("/")
    context_path.write_text(json.dumps(context, indent=2) + "\n", encoding="utf-8")


class AgenticCiExtractionJobRunner(IExtractionJobRunner):
    """Execute one extraction job using opendatahub-io/agentic-ci harness and containers."""

    def __init__(
        self,
        *,
        settings: ExtractionWorkloadRuntimeSettings | None = None,
        workdir_materializer: ExtractionJobWorkdirMaterializer | None = None,
    ) -> None:
        self._settings = settings or get_extraction_workload_runtime_settings()
        self._workdir_materializer = workdir_materializer
        self._harness = create_harness(self._settings.agentic_ci_harness)

    async def prepare_for_run(
        self,
        job: ExtractionJobRecord,
        *,
        tenant_id: str,
    ) -> PreparedExtractionJobRun:
        if self._workdir_materializer is None:
            raise RuntimeError("AgenticCiExtractionJobRunner requires a workdir materializer")
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
        _patch_job_context_api_base(workdir, self._settings.agentic_ci_api_base_url)
        prompt = build_job_run_prompt(job=job)
        return PreparedExtractionJobRun(workdir=workdir, prompt=prompt)

    async def run_prepared(
        self,
        job: ExtractionJobRecord,
        *,
        prepared: PreparedExtractionJobRun,
    ) -> dict[str, Any]:
        return await self._run_in_container(
            job=job,
            workdir=prepared.workdir,
            prompt=prepared.prompt,
        )

    async def run(self, job: ExtractionJobRecord, *, tenant_id: str) -> dict[str, Any]:
        prepared = await self.prepare_for_run(job, tenant_id=tenant_id)
        return await self.run_prepared(job, prepared=prepared)

    async def _run_in_container(
        self,
        *,
        job: ExtractionJobRecord,
        workdir: Path,
        prompt: str,
    ) -> dict[str, Any]:
        import asyncio

        return await asyncio.to_thread(self._run_in_container_sync, job, workdir, prompt)

    def _run_in_container_sync(
        self,
        job: ExtractionJobRecord,
        workdir: Path,
        prompt: str,
    ) -> dict[str, Any]:
        runtime = create_container_runtime(self._settings.container_engine)
        binary = getattr(runtime, "_binary", "podman")
        model = self._resolve_model()
        run_dir = tempfile.mkdtemp(prefix="kartograph-agentic-ci-")
        otel_proc = None
        otel_log: Path | None = None
        container_name = _sanitize_container_name(job.job_id)

        try:
            otel_proc, otel_port, otel_log_path, _otel_rate = otel.start_collector(run_dir)
            otel_log = Path(otel_log_path)
            env = self._build_container_env(otel_port=otel_port)
            binds = self._build_binds(workdir=workdir)
            write_extraction_prompt_file(workdir=workdir, prompt=prompt)
            command = _strip_harness_binary(
                self._harness.build_args(EXTRACTION_JOB_INVOKE_PROMPT, model)
            )
            log_path = activity_log_path(workdir)
            append_activity_line(log_path, f"📡 Processing job {job.job_id}...")
            rc = self._run_foreground(
                binary=binary,
                image=self._settings.agentic_ci_image,
                name=container_name,
                env=env,
                binds=binds,
                command=command,
                timeout_seconds=self._settings.agentic_ci_timeout_seconds,
                activity_log_path=log_path,
            )
            append_activity_line(log_path, f"✅ Container finished with exit code {rc}")
            if otel_proc is not None:
                otel.stop_collector(otel_proc)
                otel_proc = None
            log_path = activity_log_path(workdir)
            metrics = merge_extraction_job_metrics(
                otel_log=otel_log,
                workdir=workdir,
                activity_log=log_path,
            )
            if rc != 0:
                raise RuntimeError(
                    f"agentic-ci container exited with code {rc} for job {job.job_id}"
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
            subprocess.run(
                [binary, "rm", "-f", container_name],
                capture_output=True,
                check=False,
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

    def _build_container_env(self, *, otel_port: int) -> dict[str, str]:
        model = self._resolve_model()
        env: dict[str, str] = {
            "DISABLE_AUTOUPDATER": "1",
            "AGENT_MODEL": model,
            self._harness.model_env_var(): model,
        }
        if self._harness.auth_mode == "api-key":
            api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
            if api_key:
                env["ANTHROPIC_API_KEY"] = api_key
        else:
            env.update(
                build_vertex_container_env(
                    project_id=self._settings.vertex_project_id,
                    region=self._settings.vertex_region,
                )
            )
            if self._settings.gcloud_config_mount:
                container_gcloud = self._settings.gcloud_config_container_path.rstrip("/")
                env.update(build_gcloud_adc_env(container_config_path=container_gcloud))
        if self._harness.supports_otel and otel_port:
            env.update(
                {
                    "CLAUDE_CODE_ENABLE_TELEMETRY": "1",
                    "OTEL_METRICS_EXPORTER": "otlp",
                    "OTEL_LOGS_EXPORTER": "otlp",
                    "OTEL_EXPORTER_OTLP_PROTOCOL": "http/json",
                    "OTEL_EXPORTER_OTLP_ENDPOINT": f"http://127.0.0.1:{otel_port}",
                    "OTEL_METRIC_EXPORT_INTERVAL": "10000",
                }
            )
        return env

    def _build_binds(self, *, workdir: Path) -> list[str]:
        binds = [f"{workdir}:/workspace:z"]
        if self._settings.gcloud_config_mount and self._settings.vertex_enabled():
            binds.append(
                build_gcloud_config_bind(
                    host_mount=self._settings.gcloud_config_mount,
                    container_path=self._settings.gcloud_config_container_path,
                )
            )
        return binds

    def _run_foreground(
        self,
        *,
        binary: str,
        image: str,
        name: str,
        env: dict[str, str],
        binds: list[str],
        command: list[str],
        timeout_seconds: int,
        activity_log_path: Path | None = None,
    ) -> int:
        cmd = [
            binary,
            "run",
            "--rm",
            "--name",
            name,
            "--network",
            "host",
            "--workdir",
            "/workspace",
        ]
        if self._settings.container_run_uid is not None and self._settings.container_run_gid is not None:
            cmd.extend(
                [
                    "--user",
                    f"{self._settings.container_run_uid}:{self._settings.container_run_gid}",
                ]
            )
        for key, value in sorted(env.items()):
            cmd.extend(["--env", f"{key}={value}"])
        for bind in binds:
            cmd.extend(["--volume", bind])
        cmd.append(image)
        cmd.extend(command)
        if activity_log_path is not None:
            return self._run_foreground_streaming(
                cmd=cmd,
                binary=binary,
                name=name,
                timeout_seconds=timeout_seconds,
                activity_log_path=activity_log_path,
            )

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=False,
                timeout=timeout_seconds,
            )
        except subprocess.TimeoutExpired as exc:
            subprocess.run([binary, "rm", "-f", name], capture_output=True, check=False)
            raise RuntimeError(
                f"agentic-ci container timed out after {timeout_seconds}s"
            ) from exc
        if result.returncode != 0:
            detail = result.stderr.strip() or result.stdout.strip()
            raise ContainerRuntimeError(
                f"{binary} run failed for {name}: {detail or 'unknown error'}"
            )
        return int(result.returncode)

    def _run_foreground_streaming(
        self,
        *,
        cmd: list[str],
        binary: str,
        name: str,
        timeout_seconds: int,
        activity_log_path: Path,
    ) -> int:
        started = time.monotonic()
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
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
                            text=f"Container timed out after {timeout_seconds}s",
                        )
                        raise RuntimeError(
                            f"agentic-ci container timed out after {timeout_seconds}s"
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
        except subprocess.TimeoutExpired as exc:
            proc.kill()
            subprocess.run([binary, "rm", "-f", name], capture_output=True, check=False)
            append_activity_line(activity_log_path, "❌ Container wait timed out")
            raise RuntimeError(
                f"agentic-ci container timed out after {timeout_seconds}s"
            ) from exc

        if rc != 0:
            detail = next(
                (line for line in reversed(captured_tail) if line.strip()),
                f"exit code {rc}",
            )
            append_activity_message(
                activity_log_path,
                kind="error",
                text=f"Container failed: {detail}",
            )
            raise ContainerRuntimeError(
                f"{binary} run failed for {name}: {detail}"
            )
        return int(rc)
