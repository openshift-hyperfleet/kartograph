"""Tool wiring for graph read enclave and mutation emitters."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

import httpx

from kartograph_agent_runtime.settings import AgentRuntimeSettings


@dataclass(frozen=True)
class RuntimeTooling:
    """HTTP-backed tools available to the Claude agent runtime."""

    settings: AgentRuntimeSettings

    def _headers(self) -> dict[str, str]:
        return {"X-Workload-Token": self.settings.workload_token}

    def _base_url(self) -> str:
        return self.settings.api_base_url.rstrip("/")

    async def get_schema_authoring_guide(self) -> dict[str, Any]:
        url = f"{self._base_url()}/extraction/workloads/schema/authoring-guide"
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url, headers=self._headers())
            response.raise_for_status()
            return response.json()

    async def get_workspace_readiness(self) -> dict[str, Any]:
        url = f"{self._base_url()}/extraction/workloads/schema/readiness"
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url, headers=self._headers())
            response.raise_for_status()
            return response.json()

    async def get_schema_ontology(self) -> dict[str, Any]:
        url = f"{self._base_url()}/extraction/workloads/schema/ontology"
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url, headers=self._headers())
            response.raise_for_status()
            return response.json()

    async def save_schema_ontology(self, *, ontology: dict[str, Any]) -> dict[str, Any]:
        url = f"{self._base_url()}/extraction/workloads/schema/ontology"
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.put(url, headers=self._headers(), json=ontology)
            response.raise_for_status()
            return response.json()

    async def apply_graph_mutations(self, *, jsonl: str) -> dict[str, Any]:
        url = f"{self._base_url()}/extraction/workloads/mutations/apply"
        async with httpx.AsyncClient(timeout=600.0) as client:
            response = await client.post(
                url,
                headers=self._headers(),
                json={"jsonl": jsonl},
            )
            response.raise_for_status()
            return response.json()

    async def validate_graph_mutations(self, *, jsonl: str) -> dict[str, Any]:
        url = f"{self._base_url()}/extraction/workloads/mutations/validate"
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                url,
                headers=self._headers(),
                json={"jsonl": jsonl},
            )
            response.raise_for_status()
            return response.json()

    def read_jsonl_from_workspace(self, *, relative_path: str) -> str:
        from kartograph_agent_runtime.workspace_paths import read_workspace_text_file

        return read_workspace_text_file(self.settings.workspace_dir, relative_path)

    async def apply_graph_mutations_from_file(self, *, path: str) -> dict[str, Any]:
        jsonl = self.read_jsonl_from_workspace(relative_path=path)
        return await self.apply_graph_mutations(jsonl=jsonl)

    async def validate_graph_mutations_from_file(self, *, path: str) -> dict[str, Any]:
        jsonl = self.read_jsonl_from_workspace(relative_path=path)
        return await self.validate_graph_mutations(jsonl=jsonl)

    async def list_instances_by_type(
        self,
        *,
        entity_type: str,
        limit: int = 100,
        offset: int = 0,
    ) -> dict[str, Any]:
        url = f"{self._base_url()}/extraction/workloads/graph/instances"
        params = {
            "entity_type": entity_type,
            "limit": str(max(1, min(limit, 500))),
            "offset": str(max(0, offset)),
        }
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url, headers=self._headers(), params=params)
            response.raise_for_status()
            return response.json()

    async def list_relationship_instances(
        self,
        *,
        relationship_type: str,
        source_entity_type: str | None = None,
        target_entity_type: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> dict[str, Any]:
        url = f"{self._base_url()}/extraction/workloads/graph/relationships"
        params: dict[str, str] = {
            "relationship_type": relationship_type,
            "limit": str(max(1, min(limit, 500))),
            "offset": str(max(0, offset)),
        }
        if source_entity_type:
            params["source_entity_type"] = source_entity_type
        if target_entity_type:
            params["target_entity_type"] = target_entity_type
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url, headers=self._headers(), params=params)
            response.raise_for_status()
            return response.json()

    async def check_graph_slugs(
        self,
        *,
        entity_type: str,
        slugs: list[str],
    ) -> dict[str, Any]:
        url = f"{self._base_url()}/extraction/workloads/graph/check-slugs"
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                url,
                headers=self._headers(),
                json={"entity_type": entity_type, "slugs": slugs},
            )
            response.raise_for_status()
            return response.json()

    async def search_graph_by_slug(
        self, *, slug: str, entity_type: str | None = None
    ) -> dict[str, Any]:
        headers = self._headers()
        params: dict[str, str] = {"slug": slug}
        if entity_type:
            params["entity_type"] = entity_type
        url = f"{self._base_url()}/extraction/workloads/graph/search-by-slug"
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url, headers=headers, params=params)
            response.raise_for_status()
            return response.json()

    async def propose_mutation(
        self, *, operation: str, summary: str, payload: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        headers = self._headers()
        url = f"{self._base_url()}/extraction/workloads/mutations/propose"
        body = {
            "operation": operation,
            "summary": summary,
            "payload": payload or {},
        }
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, headers=headers, json=body)
            response.raise_for_status()
            return response.json()

    @staticmethod
    def format_tool_result(payload: dict[str, Any]) -> dict[str, Any]:
        text = json.dumps(payload, indent=2)
        return {"content": [{"type": "text", "text": text}]}
