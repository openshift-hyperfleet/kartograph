"""Tool wiring for graph read enclave and mutation emitters."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx

from kartograph_agent_runtime.settings import AgentRuntimeSettings


@dataclass(frozen=True)
class RuntimeTooling:
    """HTTP-backed tools available to the Claude agent runtime."""

    settings: AgentRuntimeSettings

    async def search_graph_by_slug(
        self, *, slug: str, entity_type: str | None = None
    ) -> dict[str, Any]:
        headers = {"X-Workload-Token": self.settings.workload_token}
        params: dict[str, str] = {"slug": slug}
        if entity_type:
            params["entity_type"] = entity_type
        url = f"{self.settings.api_base_url.rstrip('/')}/extraction/workloads/graph/search-by-slug"
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url, headers=headers, params=params)
            response.raise_for_status()
            return response.json()

    async def propose_mutation(
        self, *, operation: str, summary: str, payload: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        headers = {"X-Workload-Token": self.settings.workload_token}
        url = f"{self.settings.api_base_url.rstrip('/')}/extraction/workloads/mutations/propose"
        body = {
            "operation": operation,
            "summary": summary,
            "payload": payload or {},
        }
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, headers=headers, json=body)
            response.raise_for_status()
            return response.json()
