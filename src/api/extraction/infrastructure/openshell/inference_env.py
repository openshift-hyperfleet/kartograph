"""OpenShell inference.local environment for sandbox agents."""

from __future__ import annotations


def build_openshell_inference_env_script_lines(
    *,
    workspace_dir: str = "/sandbox",
    otel_port: int | None = None,
    otel_rate_file: str | None = None,
) -> list[str]:
    """Return env exports for Claude Code via inference.local inside OpenShell sandboxes.

    Do not set ``CLAUDE_CODE_USE_VERTEX`` here — that makes Claude Code perform ADC
    discovery inside the sandbox, which fails without mounted GCP credentials.
    """
    lines = [
        "export ANTHROPIC_BASE_URL=https://inference.local",
        "export ANTHROPIC_API_KEY=unused",
        # Vertex via inference.local rejects beta-only fields (context_management, etc.)
        # when the gateway does not forward anthropic-beta headers.
        "export CLAUDE_CODE_DISABLE_EXPERIMENTAL_BETAS=1",
        f"export KARTOGRAPH_WORKSPACE={workspace_dir.rstrip('/')}",
        "export DISABLE_AUTOUPDATER=1",
    ]
    if otel_port:
        lines.extend(
            [
                "export CLAUDE_CODE_ENABLE_TELEMETRY=1",
                "export OTEL_METRICS_EXPORTER=otlp",
                "export OTEL_LOGS_EXPORTER=otlp",
                "export OTEL_EXPORTER_OTLP_PROTOCOL=http/json",
                f"export OTEL_EXPORTER_OTLP_ENDPOINT=http://10.200.0.1:{otel_port}",
                "export OTEL_METRIC_EXPORT_INTERVAL=10000",
            ]
        )
        if otel_rate_file:
            from shlex import quote

            lines.append(f"export OTEL_RATE_FILE={quote(otel_rate_file)}")
    return lines


def insert_claude_bare_flag(agent_args: list[str]) -> list[str]:
    """Insert ``--bare`` after the claude binary for OpenShell inference.local auth."""
    if not agent_args or agent_args[0] != "claude" or "--bare" in agent_args:
        return agent_args
    return [agent_args[0], "--bare", *agent_args[1:]]


def insert_vertex_compatible_effort(agent_args: list[str]) -> list[str]:
    """Ensure batch extraction CLI uses a Vertex-supported effort level."""
    if not agent_args or agent_args[0] != "claude":
        return agent_args
    if any(arg == "--effort" for arg in agent_args):
        return agent_args
    bare_index = 1
    if len(agent_args) > 1 and agent_args[1] == "--bare":
        bare_index = 2
    return [
        *agent_args[:bare_index],
        "--effort",
        "high",
        *agent_args[bare_index:],
    ]
