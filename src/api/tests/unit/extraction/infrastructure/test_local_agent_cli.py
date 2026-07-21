"""Unit tests for the local agent CLI (poll loop, dispatch, sandbox lifecycle).

See specs/extraction/local-sandbox-execution.spec.md. Heavy mocking of the
OpenShell subprocess-wrapping modules is intentional -- this test suite
verifies *orchestration* (which openshell.py functions are called, with what
arguments, in what order, and how failures propagate), not the real OpenShell
CLI, which is exercised only via manual/integration verification against a
live gateway.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import httpx
import pytest

from extraction.infrastructure.local_runtime.agent_cli import (
    LocalAgentSettings,
    LocalRuntimeAgent,
    LocalRuntimeAgentClient,
    _api_host_from_base_url,
    _HeartbeatPump,
    _TrackedSandboxSession,
)
from extraction.infrastructure.openshell.cli import OpenShellCliError
from extraction.infrastructure.workload_runtime_settings import (
    ExtractionWorkloadRuntimeSettings,
)


class TestLocalAgentSettings:
    def test_requires_api_base_url_and_api_key(self, monkeypatch) -> None:
        monkeypatch.delenv("KARTOGRAPH_LOCAL_AGENT_API_BASE_URL", raising=False)
        monkeypatch.delenv("KARTOGRAPH_LOCAL_AGENT_API_KEY", raising=False)

        with pytest.raises(Exception):
            LocalAgentSettings(_env_file=None)  # type: ignore[call-arg]

    def test_reads_configured_values(self) -> None:
        settings = LocalAgentSettings(
            api_base_url="https://kartograph-stage.example.com",
            api_key="kg_test_key",
        )

        assert settings.api_base_url == "https://kartograph-stage.example.com"
        assert settings.api_key == "kg_test_key"
        assert settings.poll_error_backoff_seconds == 5.0
        assert settings.heartbeat_interval_seconds == 10.0


class TestApiHostFromBaseUrl:
    def test_extracts_host_and_port(self) -> None:
        assert _api_host_from_base_url("https://kartograph-stage.example.com:8443") == (
            "kartograph-stage.example.com:8443"
        )

    def test_returns_none_for_empty_input(self) -> None:
        assert _api_host_from_base_url("") is None


class TestLocalRuntimeAgentClient:
    def _client(self, handler) -> LocalRuntimeAgentClient:
        transport = httpx.MockTransport(handler)
        http_client = httpx.Client(
            base_url="https://hosted.example.com",
            headers={"X-API-Key": "kg_test"},
            transport=transport,
        )
        return LocalRuntimeAgentClient(
            api_base_url="https://hosted.example.com",
            api_key="kg_test",
            client=http_client,
        )

    def test_poll_returns_none_on_204(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            assert request.url.path == "/extraction/local-runtime/poll"
            assert request.headers["X-API-Key"] == "kg_test"
            return httpx.Response(204)

        client = self._client(handler)
        assert client.poll() is None

    def test_poll_returns_json_body_on_200(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={"id": "req-1", "kind": "sandbox_start"})

        client = self._client(handler)
        work = client.poll()
        assert work == {"id": "req-1", "kind": "sandbox_start"}

    def test_poll_raises_on_401(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(401)

        client = self._client(handler)
        with pytest.raises(httpx.HTTPStatusError):
            client.poll()

    def test_heartbeat_posts_to_expected_path(self) -> None:
        seen = {}

        def handler(request: httpx.Request) -> httpx.Response:
            seen["path"] = request.url.path
            return httpx.Response(204)

        client = self._client(handler)
        client.heartbeat("req-1")
        assert seen["path"] == "/extraction/local-runtime/req-1/heartbeat"

    def test_complete_sends_result_body(self) -> None:
        seen = {}

        def handler(request: httpx.Request) -> httpx.Response:
            seen["body"] = json.loads(request.content)
            return httpx.Response(204)

        client = self._client(handler)
        client.complete("req-1", result={"container_id": "sandbox-abc"})
        assert seen["body"] == {"result": {"container_id": "sandbox-abc"}}

    def test_fail_sends_truncated_failure_reason(self) -> None:
        seen = {}

        def handler(request: httpx.Request) -> httpx.Response:
            seen["body"] = json.loads(request.content)
            return httpx.Response(204)

        client = self._client(handler)
        client.fail("req-1", failure_reason="x" * 3000)
        assert len(seen["body"]["failure_reason"]) == 2000

    def test_mint_vertex_token_returns_json_body(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            assert request.url.path == "/extraction/local-runtime/req-1/vertex-token"
            return httpx.Response(
                200, json={"access_token": "tok", "expires_at": "2026-01-01T00:00:00Z"}
            )

        client = self._client(handler)
        token = client.mint_vertex_token("req-1")
        assert token["access_token"] == "tok"


class TestHeartbeatPump:
    def test_sends_heartbeats_until_stopped(self) -> None:
        client = MagicMock()
        pump = _HeartbeatPump(client=client, request_id="req-1", interval_seconds=0.05)

        pump.start()
        import time

        time.sleep(0.2)
        pump.stop()

        assert client.heartbeat.call_count >= 2
        client.heartbeat.assert_called_with("req-1")

    def test_survives_heartbeat_errors(self) -> None:
        client = MagicMock()
        client.heartbeat.side_effect = httpx.ConnectError("down")
        pump = _HeartbeatPump(client=client, request_id="req-1", interval_seconds=0.05)

        pump.start()
        import time

        time.sleep(0.2)
        pump.stop()  # must not raise despite heartbeat errors


def _settings(**overrides) -> ExtractionWorkloadRuntimeSettings:
    defaults = dict(backend="local")
    defaults.update(overrides)
    return ExtractionWorkloadRuntimeSettings(**defaults)


def _agent(client=None, **settings_overrides) -> LocalRuntimeAgent:
    return LocalRuntimeAgent(
        client=client or MagicMock(),
        runtime_settings=_settings(**settings_overrides),
    )


class TestHandleSandboxStart:
    def test_creates_sandbox_and_tracks_session_without_vertex(self) -> None:
        agent = _agent()
        work = {
            "id": "req-1",
            "session_id": "sess-1",
            "knowledge_graph_id": "kg-1",
            "kind": "sandbox_start",
            "payload": {
                "mode": "schema_bootstrap",
                "sticky_image": "kartograph-agent-runtime:test",
                "ui_mode": "initial_schema_design",
                "api_base_url": "https://hosted.example.com",
                "vertex_enabled": False,
            },
        }

        with (
            patch(
                "extraction.infrastructure.local_runtime.agent_cli.openshell_sandbox"
            ) as sandbox_mod,
        ):
            result = agent._handle_sandbox_start(work)

        sandbox_mod.delete_sandbox.assert_called_once()
        sandbox_mod.create_sandbox.assert_called_once()
        create_kwargs = sandbox_mod.create_sandbox.call_args.kwargs
        assert create_kwargs["image"] == "kartograph-agent-runtime:test"
        assert create_kwargs["provider_name"] is None
        sandbox_mod.apply_policy.assert_called_once()
        apply_kwargs = sandbox_mod.apply_policy.call_args.kwargs
        assert apply_kwargs["policy_enforcement"] == "hard_requirement"
        assert apply_kwargs["vertex_region"] is None
        sandbox_mod.exec_background.assert_called_once()
        sandbox_mod.start_forward.assert_called_once()
        assert "container_id" in result
        assert "sess-1" in agent._sessions

    def test_mints_vertex_token_and_configures_provider_when_enabled(self) -> None:
        client = MagicMock()
        client.mint_vertex_token.return_value = {
            "access_token": "minted-abc",
            "expires_at": "2026-01-01T00:00:00Z",
        }
        agent = _agent(client=client, openshell_provider_name="kartograph-local")
        work = {
            "id": "req-1",
            "session_id": "sess-1",
            "knowledge_graph_id": "kg-1",
            "kind": "sandbox_start",
            "payload": {
                "mode": "schema_bootstrap",
                "sticky_image": "kartograph-agent-runtime:test",
                "vertex_enabled": True,
                "vertex_project_id": "proj-1",
                "vertex_region": "us-east5",
            },
        }

        with (
            patch(
                "extraction.infrastructure.local_runtime.agent_cli.openshell_sandbox"
            ),
            patch(
                "extraction.infrastructure.local_runtime.agent_cli.ensure_vertex_provider_from_static_token"
            ) as ensure_provider,
        ):
            agent._handle_sandbox_start(work)

        client.mint_vertex_token.assert_called_once_with("req-1")
        ensure_provider.assert_called_once_with(
            provider_name="kartograph-local",
            project_id="proj-1",
            region="us-east5",
            access_token="minted-abc",
            expires_at="2026-01-01T00:00:00Z",
        )

    def test_policy_apply_failure_propagates_uncaught(self) -> None:
        """Fail-closed: a Landlock policy-apply failure must not be swallowed."""
        agent = _agent()
        work = {
            "id": "req-1",
            "session_id": "sess-1",
            "knowledge_graph_id": "kg-1",
            "kind": "sandbox_start",
            "payload": {"mode": "schema_bootstrap", "vertex_enabled": False},
        }

        with patch(
            "extraction.infrastructure.local_runtime.agent_cli.openshell_sandbox"
        ) as sandbox_mod:
            sandbox_mod.apply_policy.side_effect = OpenShellCliError(
                "hard_requirement Landlock enforcement unavailable"
            )
            with pytest.raises(OpenShellCliError, match="Landlock"):
                agent._handle_sandbox_start(work)

        assert "sess-1" not in agent._sessions


class TestHandleChatTurn:
    def test_relays_turn_and_buffers_events(self) -> None:
        agent = _agent()
        agent._sessions["sess-1"] = _TrackedSandboxSession(
            sandbox_name="kartograph-local-sess-1",
            forward_port=18800,
            runtime_base_url="http://127.0.0.1:18800",
            runtime_auth_token="runtime-token-abc",
        )
        work = {
            "id": "req-2",
            "session_id": "sess-1",
            "kind": "chat_turn",
            "payload": {
                "message": "hello",
                "ui_mode": "initial_schema_design",
                "workload_token": "wl-token",
            },
        }
        seen_requests: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            seen_requests.append(request)
            body = b'{"type": "text"}\n{"type": "done", "ok": true}\n'
            return httpx.Response(200, content=body)

        real_client_cls = httpx.Client

        def _build_mocked_client(**kwargs):
            return real_client_cls(
                base_url=kwargs["base_url"],
                headers=kwargs["headers"],
                timeout=kwargs["timeout"],
                transport=httpx.MockTransport(handler),
            )

        with patch(
            "extraction.infrastructure.local_runtime.agent_cli.httpx.Client",
            side_effect=_build_mocked_client,
        ):
            result = agent._handle_chat_turn(work)

        assert result == {"events": [{"type": "text"}, {"type": "done", "ok": True}]}
        assert len(seen_requests) == 1
        assert seen_requests[0].url.path == "/v1/turn"
        assert (
            seen_requests[0].headers["X-Kartograph-Runtime-Auth"] == "runtime-token-abc"
        )
        sent_body = json.loads(seen_requests[0].content)
        assert sent_body["message"] == "hello"
        assert sent_body["workload_token"] == "wl-token"

    def test_raises_when_session_not_tracked(self) -> None:
        agent = _agent()
        work = {"id": "req-2", "session_id": "sess-unknown", "payload": {}}

        with pytest.raises(RuntimeError, match="No local Sandbox is tracked"):
            agent._handle_chat_turn(work)


class TestHandleSandboxStop:
    def test_stops_forward_and_deletes_tracked_sandbox(self) -> None:
        agent = _agent()
        agent._sessions["sess-1"] = _TrackedSandboxSession(
            sandbox_name="kartograph-local-sess-1",
            forward_port=18800,
            runtime_base_url="http://127.0.0.1:18800",
            runtime_auth_token="tok",
        )
        work = {"id": "req-3", "session_id": "sess-1", "payload": {}}

        with patch(
            "extraction.infrastructure.local_runtime.agent_cli.openshell_sandbox"
        ) as sandbox_mod:
            agent._handle_sandbox_stop(work)

        sandbox_mod.stop_forward.assert_called_once_with(
            sandbox_name="kartograph-local-sess-1", port=18800
        )
        sandbox_mod.delete_sandbox.assert_called_once_with("kartograph-local-sess-1")
        assert "sess-1" not in agent._sessions


class TestPollOnce:
    def test_no_work_returns_none(self) -> None:
        client = MagicMock()
        client.poll.return_value = None
        agent = _agent(client=client)

        assert agent.poll_once() is None
        client.complete.assert_not_called()
        client.fail.assert_not_called()

    def test_successful_dispatch_reports_completion(self) -> None:
        client = MagicMock()
        client.poll.return_value = {
            "id": "req-1",
            "kind": "sandbox_stop",
            "session_id": "sess-1",
            "payload": {"container_id": "sandbox-1"},
        }
        agent = _agent(client=client)

        with patch(
            "extraction.infrastructure.local_runtime.agent_cli.openshell_sandbox"
        ):
            request_id = agent.poll_once()

        assert request_id == "req-1"
        client.complete.assert_called_once_with("req-1", result={})
        client.fail.assert_not_called()

    def test_dispatch_failure_is_reported_via_fail(self) -> None:
        client = MagicMock()
        client.poll.return_value = {
            "id": "req-1",
            "kind": "sandbox_start",
            "session_id": "sess-1",
            "payload": {"vertex_enabled": False},
        }
        agent = _agent(client=client)

        with patch(
            "extraction.infrastructure.local_runtime.agent_cli.openshell_sandbox"
        ) as sandbox_mod:
            sandbox_mod.apply_policy.side_effect = OpenShellCliError("policy failed")
            request_id = agent.poll_once()

        assert request_id == "req-1"
        client.complete.assert_not_called()
        client.fail.assert_called_once()
        fail_kwargs = client.fail.call_args.kwargs
        assert "policy failed" in fail_kwargs["failure_reason"]

    def test_unknown_kind_is_reported_via_fail(self) -> None:
        client = MagicMock()
        client.poll.return_value = {
            "id": "req-1",
            "kind": "unknown_kind",
            "payload": {},
        }
        agent = _agent(client=client)

        request_id = agent.poll_once()

        assert request_id == "req-1"
        client.fail.assert_called_once()
