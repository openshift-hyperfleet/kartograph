"""Run extraction jobs inside agentic-ci sandbox containers."""

from __future__ import annotations

import os
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from agentic_ci.harness import create_harness
from agentic_ci import otel

from extraction.domain.extraction_job import ExtractionJobRecord
from extraction.infrastructure.extraction_job_metrics import metrics_from_otel_log
from extraction.infrastructure.extraction_job_prompt import build_extraction_job_prompt
from extraction.infrastructure.extraction_job_workdir_materializer import (
    ExtractionJobWorkdirMaterializer,
)
from extraction.infrastructure.vertex_runtime_env import build_vertex_container_env
from extraction.infrastructure.workload_runtime_factory import get_workload_credential_issuer
from extraction.infrastructure.workload_runtime_settings import (
    ExtractionWorkloadRuntimeSettings,
    get_extraction_workload_runtime_settings,
)
from extraction.ports.extraction_job_runner import IExtractionJobRunner
from shared_kernel.container_runtime.factory import create_container_runtime
from shared_kernel.container_runtime.ports import ContainerRuntimeError

_CONTAINER_NAME_SAFE = re.compile(r"[^a-zA-Z0-9_.-]+")
_GCLOUD_ADC_FILENAME = "application_default_credentials.json"


def _sanitize_container_name(job_id: str) -> str:
    cleaned = _CONTAINER_NAME_SAFE.sub("-", job_id).strip("-")
    return f"kartograph-extract-{cleaned}"[:63].rstrip("-_.")


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

    async def run(self, job: ExtractionJobRecord, *, tenant_id: str) -> dict[str, Any]:
        if self._workdir_materializer is None:
            raise RuntimeError("AgenticCiExtractionJobRunner requires a workdir materializer")
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
        prompt = build_extraction_job_prompt(job=job)
        return await self._run_in_container(job=job, workdir=workdir, prompt=prompt)

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
            command = self._harness.build_args(prompt, model)
            rc = self._run_foreground(
                binary=binary,
                image=self._settings.agentic_ci_image,
                name=container_name,
                env=env,
                binds=binds,
                command=command,
                timeout_seconds=self._settings.agentic_ci_timeout_seconds,
            )
            if otel_proc is not None:
                otel.stop_collector(otel_proc)
                otel_proc = None
            metrics = metrics_from_otel_log(otel_log) if otel_log is not None else {}
            if rc != 0:
                raise RuntimeError(
                    f"agentic-ci container exited with code {rc} for job {job.job_id}"
                )
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
        env: dict[str, str] = {
            "DISABLE_AUTOUPDATER": "1",
            "AGENT_MODEL": self._resolve_model(),
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
            mount_target = self._harness.credential_mount_target()
            gcloud_root = self._settings.gcloud_config_mount.rstrip("/")
            adc = f"{gcloud_root}/{_GCLOUD_ADC_FILENAME}"
            config = f"{gcloud_root}/configurations/config_default"
            if Path(adc).is_file():
                binds.append(
                    f"{adc}:{mount_target}/.config/gcloud/application_default_credentials.json:ro,z"
                )
            if Path(config).is_file():
                binds.append(
                    f"{config}:{mount_target}/.config/gcloud/configurations/config_default:ro,z"
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
