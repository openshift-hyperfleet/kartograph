"""CLI entrypoint for sticky session agent runtime."""

from __future__ import annotations

import uvicorn

from kartograph_agent_runtime.settings import AgentRuntimeSettings


def main() -> None:
    settings = AgentRuntimeSettings()
    uvicorn.run(
        "kartograph_agent_runtime.server:app",
        host=settings.host,
        port=settings.port,
        log_level="info",
    )


if __name__ == "__main__":
    main()
