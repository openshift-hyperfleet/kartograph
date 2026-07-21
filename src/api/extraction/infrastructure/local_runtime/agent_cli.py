"""Local agent: polls the hosted API and executes Sandbox work on this machine.

See specs/extraction/local-sandbox-execution.spec.md. This process is meant
to run on a user's own laptop, not inside the hosted API's containers -- it
authenticates with an ordinary Kartograph API key
(`iam/api-keys.spec.md`), long-polls `/extraction/local-runtime/poll` for
work, and drives the same `sandbox.py`/`policy.py`/`gateway.py` OpenShell
modules hosted execution uses, pointed at a locally-registered OpenShell
gateway instead of an in-cluster one ("Unchanged Sandbox Lifecycle
Semantics"). Run via
``uv run python -m extraction.infrastructure.local_runtime.agent_cli``
(from this `src/api` checkout) after `openshell gateway add` /
`openshell-gateway` are set up locally, exactly as for the existing
backend=openshell dev workflow.
"""

from __future__ import annotations

import json
import logging
import threading
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

import httpx
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from extraction.infrastructure.openshell import gateway as openshell_gateway
from extraction.infrastructure.openshell import sandbox as openshell_sandbox
from extraction.infrastructure.openshell.runtime_env import apply_openshell_cli_env
from extraction.infrastructure.openshell.vertex_provider import (
    ensure_vertex_provider_from_static_token,
)
from extraction.infrastructure.runtime_session_auth import (
    RUNTIME_AUTH_HEADER,
    issue_runtime_auth_token,
)
from extraction.infrastructure.vertex_runtime_env import (
    build_openshell_inference_container_env,
)
from extraction.infrastructure.workload_runtime_settings import (
    ExtractionWorkloadRuntimeSettings,
    get_extraction_workload_runtime_settings,
)

logger = logging.getLogger("kartograph.extraction.local_runtime.agent_cli")

#: Local execution always requests hard Landlock enforcement, regardless of
#: any soft/hard_requirement setting -- see specs/extraction/
#: local-sandbox-execution.spec.md, "Local Execution Always Requests Hard
#: Landlock Enforcement".
_LOCAL_POLICY_ENFORCEMENT = "hard_requirement"
_MESSAGE_HISTORY_WINDOW = 20


class LocalAgentSettings(BaseSettings):
    """Configuration for this local agent process itself (not the hosted API)."""

    model_config = SettingsConfigDict(
        env_prefix="KARTOGRAPH_LOCAL_AGENT_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    api_base_url: str = Field(
        description="Hosted Kartograph API base URL to poll for local runtime work."
    )
    api_key: str = Field(
        repr=False,
        description="Kartograph API key authenticating this agent (iam/api-keys.spec.md).",
    )
    poll_error_backoff_seconds: float = Field(default=5.0, ge=1.0, le=60.0)
    heartbeat_interval_seconds: float = Field(default=10.0, ge=2.0, le=60.0)


@dataclass
class _TrackedSandboxSession:
    """What this agent process remembers about a Sandbox it started.

    Lost on agent restart -- an accepted limitation of this temporary mode
    (specs "Known Limitations"); the user re-dispatches via the existing
    session reset flow if the agent restarts mid-session.
    """

    sandbox_name: str
    forward_port: int
    runtime_base_url: str
    runtime_auth_token: str


class LocalRuntimeAgentClient:
    """Thin HTTP client for the local-runtime agent endpoints."""

    def __init__(
        self,
        *,
        api_base_url: str,
        api_key: str,
        client: httpx.Client | None = None,
    ) -> None:
        self._client = client or httpx.Client(
            base_url=api_base_url.rstrip("/"),
            headers={"X-API-Key": api_key},
            timeout=30.0,
        )

    def poll(self) -> dict[str, Any] | None:
        response = self._client.post("/extraction/local-runtime/poll")
        if response.status_code == 204:
            return None
        response.raise_for_status()
        return response.json()

    def heartbeat(self, request_id: str) -> None:
        response = self._client.post(
            f"/extraction/local-runtime/{request_id}/heartbeat"
        )
        response.raise_for_status()

    def complete(self, request_id: str, *, result: dict[str, Any]) -> None:
        response = self._client.post(
            f"/extraction/local-runtime/{request_id}/complete",
            json={"result": result},
        )
        response.raise_for_status()

    def fail(self, request_id: str, *, failure_reason: str) -> None:
        response = self._client.post(
            f"/extraction/local-runtime/{request_id}/fail",
            json={"failure_reason": (failure_reason or "unknown error")[:2000]},
        )
        response.raise_for_status()

    def mint_vertex_token(self, request_id: str) -> dict[str, Any]:
        response = self._client.post(
            f"/extraction/local-runtime/{request_id}/vertex-token"
        )
        response.raise_for_status()
        return response.json()

    def close(self) -> None:
        self._client.close()


class _HeartbeatPump:
    """Sends heartbeats for one claimed request on a background thread.

    Keeps a long-running `sandbox_start` (Sandbox creation, up to five
    minutes) or `chat_turn` (up to the hosted chat-turn timeout) from being
    reaped by the server-side sweep (specs "Heartbeat loss fails the claim")
    while this agent is still actively working the request.
    """

    def __init__(
        self,
        *,
        client: LocalRuntimeAgentClient,
        request_id: str,
        interval_seconds: float,
    ) -> None:
        self._client = client
        self._request_id = request_id
        self._interval_seconds = interval_seconds
        self._stop_event = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        self._thread.join(timeout=self._interval_seconds + 5.0)

    def _run(self) -> None:
        while not self._stop_event.wait(self._interval_seconds):
            try:
                self._client.heartbeat(self._request_id)
            except httpx.HTTPError:
                logger.warning(
                    "local_runtime_heartbeat_failed request_id=%s", self._request_id
                )


def _sanitize_local_sandbox_name(session_id: str) -> str:
    return openshell_sandbox.sanitize_sandbox_name("kartograph-local-", session_id)


def _api_host_from_base_url(api_base_url: str) -> str | None:
    if not api_base_url:
        return None
    parsed = urlparse(api_base_url)
    if not parsed.hostname:
        return None
    port_suffix = f":{parsed.port}" if parsed.port else ""
    return f"{parsed.hostname}{port_suffix}"


class LocalRuntimeAgent:
    """Poll loop and dispatch for one user's local Sandbox work.

    Mirrors `OpenShellStickySessionRuntimeManager`'s orchestration
    (specs "Unchanged Sandbox Lifecycle Semantics") but reads instructions
    from claimed work request payloads instead of direct method arguments,
    and reports outcomes back to the hosted API over HTTP instead of
    returning a lease object in-process.
    """

    def __init__(
        self,
        *,
        client: LocalRuntimeAgentClient,
        runtime_settings: ExtractionWorkloadRuntimeSettings,
        heartbeat_interval_seconds: float = 10.0,
        stop_event: threading.Event | None = None,
    ) -> None:
        self._client = client
        self._runtime_settings = runtime_settings
        self._heartbeat_interval_seconds = heartbeat_interval_seconds
        self._stop_event = stop_event or threading.Event()
        self._sessions: dict[str, _TrackedSandboxSession] = {}

    def run_forever(self, *, poll_error_backoff_seconds: float = 5.0) -> None:
        apply_openshell_cli_env(self._runtime_settings)
        openshell_gateway.ensure_gateway_registered(
            gateway_name=self._runtime_settings.openshell_gateway_name,
            gateway_url=self._runtime_settings.openshell_gateway_url,
        )
        logger.info("local_runtime_agent_started")
        while not self._stop_event.is_set():
            try:
                self.poll_once()
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code == 401:
                    logger.error(
                        "local_runtime_agent_unauthorized; check KARTOGRAPH_LOCAL_AGENT_API_KEY"
                    )
                    raise
                logger.warning(
                    "local_runtime_agent_poll_http_error status=%s",
                    exc.response.status_code,
                )
                self._stop_event.wait(poll_error_backoff_seconds)
            except httpx.HTTPError as exc:
                logger.warning("local_runtime_agent_poll_transport_error error=%s", exc)
                self._stop_event.wait(poll_error_backoff_seconds)

    def poll_once(self) -> str | None:
        """Poll once; claim and execute at most one work request. Returns its id, if any."""
        work = self._client.poll()
        if work is None:
            return None
        request_id = str(work["id"])
        kind = str(work["kind"])
        pump = _HeartbeatPump(
            client=self._client,
            request_id=request_id,
            interval_seconds=self._heartbeat_interval_seconds,
        )
        pump.start()
        try:
            result = self._dispatch(kind=kind, work=work)
        except Exception as exc:  # noqa: BLE001 - every failure is reported, never swallowed
            logger.exception(
                "local_runtime_work_failed request_id=%s kind=%s", request_id, kind
            )
            pump.stop()
            self._client.fail(request_id, failure_reason=str(exc) or repr(exc))
            return request_id
        pump.stop()
        self._client.complete(request_id, result=result)
        logger.info(
            "local_runtime_work_completed request_id=%s kind=%s", request_id, kind
        )
        return request_id

    def _dispatch(self, *, kind: str, work: dict[str, Any]) -> dict[str, Any]:
        if kind == "sandbox_start":
            return self._handle_sandbox_start(work)
        if kind == "chat_turn":
            return self._handle_chat_turn(work)
        if kind == "sandbox_stop":
            return self._handle_sandbox_stop(work)
        raise ValueError(f"Unknown local runtime work kind: {kind!r}")

    def _handle_sandbox_start(self, work: dict[str, Any]) -> dict[str, Any]:
        payload: dict[str, Any] = work.get("payload") or {}
        session_id = str(work.get("session_id") or work["id"])
        sandbox_name = _sanitize_local_sandbox_name(session_id)
        provider_name = self._runtime_settings.openshell_provider_name
        vertex_enabled = bool(payload.get("vertex_enabled"))

        if vertex_enabled:
            token_response = self._client.mint_vertex_token(str(work["id"]))
            ensure_vertex_provider_from_static_token(
                provider_name=provider_name,
                project_id=str(payload.get("vertex_project_id", "")),
                region=str(payload.get("vertex_region", "")),
                access_token=str(token_response["access_token"]),
                expires_at=str(token_response["expires_at"]),
            )

        openshell_sandbox.delete_sandbox(sandbox_name)
        openshell_sandbox.create_sandbox(
            name=sandbox_name,
            image=str(
                payload.get("sticky_image") or self._runtime_settings.sticky_image
            ),
            provider_name=provider_name if vertex_enabled else None,
        )
        openshell_sandbox.emit_lifecycle(
            sandbox_name=sandbox_name,
            action="created",
            image=str(payload.get("sticky_image", "")),
            session_id=session_id,
        )

        # Fail-closed: apply_policy raises OpenShellCliError uncaught on any
        # policy-apply failure (including a host that cannot satisfy
        # hard_requirement Landlock enforcement), which propagates to
        # `poll_once` and is reported as a failed work request instead of
        # starting the Sandbox with softened enforcement (specs "Policy
        # apply fails closed").
        openshell_sandbox.apply_policy(
            sandbox_name=sandbox_name,
            ui_mode=str(payload.get("ui_mode") or payload.get("mode") or ""),
            workload="gma",
            policy_dir=self._runtime_settings.openshell_policy_dir or None,
            api_host=_api_host_from_base_url(str(payload.get("api_base_url", ""))),
            vertex_region=str(payload.get("vertex_region", ""))
            if vertex_enabled
            else None,
            policy_enforcement=_LOCAL_POLICY_ENFORCEMENT,
        )

        runtime_auth_token = issue_runtime_auth_token()
        env = self._build_sandbox_env(
            session_id=session_id,
            knowledge_graph_id=str(work.get("knowledge_graph_id", "")),
            payload=payload,
            runtime_auth_token=runtime_auth_token,
            vertex_enabled=vertex_enabled,
        )
        openshell_sandbox.exec_background(
            sandbox_name=sandbox_name,
            env=env,
            command=("/app/.venv/bin/python", "-m", "kartograph_agent_runtime"),
        )
        forward_port = openshell_sandbox.forward_port_for_session(
            session_id=session_id,
            base=self._runtime_settings.openshell_forward_port_base,
        )
        openshell_sandbox.start_forward(
            sandbox_name=sandbox_name,
            port=forward_port,
            target_port=self._runtime_settings.sticky_service_port,
        )
        openshell_sandbox.emit_lifecycle(
            sandbox_name=sandbox_name,
            action="started",
            forward_port=forward_port,
            session_id=session_id,
        )

        runtime_base_url = f"http://127.0.0.1:{forward_port}"
        self._sessions[session_id] = _TrackedSandboxSession(
            sandbox_name=sandbox_name,
            forward_port=forward_port,
            runtime_base_url=runtime_base_url,
            runtime_auth_token=runtime_auth_token,
        )
        return {"container_id": sandbox_name}

    def _build_sandbox_env(
        self,
        *,
        session_id: str,
        knowledge_graph_id: str,
        payload: dict[str, Any],
        runtime_auth_token: str,
        vertex_enabled: bool,
    ) -> dict[str, str]:
        env: dict[str, str] = {
            "KARTOGRAPH_SESSION_ID": session_id,
            "KARTOGRAPH_KNOWLEDGE_GRAPH_ID": knowledge_graph_id,
            "KARTOGRAPH_SESSION_MODE": str(payload.get("mode", "")),
            "KARTOGRAPH_WORKSPACE_DIR": self._runtime_settings.openshell_container_work_mount,
            "KARTOGRAPH_AGENT_TURN_TIMEOUT_SECONDS": str(
                int(self._runtime_settings.sticky_turn_timeout_seconds)
            ),
            "KARTOGRAPH_AGENT_MAX_TURNS": str(self._runtime_settings.sticky_max_turns),
            "KARTOGRAPH_RUNTIME_AUTH_TOKEN": runtime_auth_token,
        }
        tenant_id = payload.get("tenant_id")
        if tenant_id:
            env["KARTOGRAPH_TENANT_ID"] = str(tenant_id)
        api_base_url = payload.get("api_base_url")
        if api_base_url:
            env["KARTOGRAPH_API_BASE_URL"] = str(api_base_url)
        if vertex_enabled:
            env.update(build_openshell_inference_container_env())
        return env

    def _handle_chat_turn(self, work: dict[str, Any]) -> dict[str, Any]:
        session_id = str(work.get("session_id") or "")
        tracked = self._sessions.get(session_id)
        if tracked is None:
            raise RuntimeError(
                f"No local Sandbox is tracked for session {session_id!r} by this "
                "agent process. If this agent restarted since the Sandbox was "
                "started, reset the session to start a new one."
            )
        payload: dict[str, Any] = work.get("payload") or {}
        turn_request: dict[str, Any] = {
            "message": payload.get("message", ""),
            "ui_mode": payload.get("ui_mode", ""),
            "agent_configuration": payload.get("agent_configuration", {}),
            "message_history": (payload.get("message_history") or [])[
                -_MESSAGE_HISTORY_WINDOW:
            ],
        }
        workload_token = payload.get("workload_token")
        if workload_token:
            turn_request["workload_token"] = workload_token

        events: list[dict[str, Any]] = []
        timeout = httpx.Timeout(
            10.0, read=self._runtime_settings.sticky_turn_timeout_seconds + 30.0
        )
        with httpx.Client(
            base_url=tracked.runtime_base_url,
            headers={RUNTIME_AUTH_HEADER: tracked.runtime_auth_token},
            timeout=timeout,
        ) as sandbox_client:
            with sandbox_client.stream(
                "POST", "/v1/turn", json=turn_request
            ) as response:
                response.raise_for_status()
                for line in response.iter_lines():
                    trimmed = line.strip()
                    if trimmed:
                        events.append(json.loads(trimmed))
        return {"events": events}

    def _handle_sandbox_stop(self, work: dict[str, Any]) -> dict[str, Any]:
        session_id = str(work.get("session_id") or "")
        tracked = self._sessions.pop(session_id, None)
        payload: dict[str, Any] = work.get("payload") or {}
        sandbox_name = str(
            payload.get("container_id")
            or (
                tracked.sandbox_name
                if tracked
                else _sanitize_local_sandbox_name(session_id)
            )
        )
        forward_port = (
            tracked.forward_port
            if tracked is not None
            else openshell_sandbox.forward_port_for_session(
                session_id=session_id,
                base=self._runtime_settings.openshell_forward_port_base,
            )
        )
        openshell_sandbox.stop_forward(sandbox_name=sandbox_name, port=forward_port)
        openshell_sandbox.delete_sandbox(sandbox_name)
        openshell_sandbox.emit_lifecycle(
            sandbox_name=sandbox_name, action="deleted", session_id=session_id
        )
        return {}


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    agent_settings = LocalAgentSettings()  # type: ignore[call-arg]
    runtime_settings = get_extraction_workload_runtime_settings()
    client = LocalRuntimeAgentClient(
        api_base_url=agent_settings.api_base_url, api_key=agent_settings.api_key
    )
    agent = LocalRuntimeAgent(
        client=client,
        runtime_settings=runtime_settings,
        heartbeat_interval_seconds=agent_settings.heartbeat_interval_seconds,
    )
    try:
        agent.run_forever(
            poll_error_backoff_seconds=agent_settings.poll_error_backoff_seconds
        )
    finally:
        client.close()


if __name__ == "__main__":
    main()
