"""Graph-backed schema service for extraction workload runtimes."""

from __future__ import annotations

import json

from sqlalchemy.ext.asyncio import AsyncSession

from infrastructure.canonical_schema.graph_canonical_schema_repository import (
    GraphCanonicalSchemaRepository,
)
from infrastructure.extraction_workload.graph_mutation_writer import (
    GraphWorkloadGraphMutationWriter,
)
from management.domain.value_objects import OntologyConfig
from management.ports.exceptions import CanonicalSchemaMutationError


class GraphWorkloadSchemaService:
    """Read and write canonical schema using the Management graph-native store."""

    def __init__(
        self,
        session: AsyncSession,
        *,
        mutation_writer: GraphWorkloadGraphMutationWriter,
    ) -> None:
        self._session = session
        self._repository = GraphCanonicalSchemaRepository(session)
        self._mutation_writer = mutation_writer

    async def get_ontology(self, *, knowledge_graph_id: str) -> OntologyConfig | None:
        return await self._repository.get_ontology(knowledge_graph_id)

    async def replace_ontology(
        self,
        *,
        knowledge_graph_id: str,
        config: OntologyConfig,
    ) -> OntologyConfig:
        await self._repository.replace_ontology(knowledge_graph_id, config)
        await self._session.commit()
        return config

    async def apply_mutation_jsonl(
        self,
        *,
        tenant_id: str,
        knowledge_graph_id: str,
        jsonl: str,
    ) -> dict[str, object]:
        try:
            operations = GraphWorkloadGraphMutationWriter.parse_jsonl(jsonl)
            define_ops, instance_ops = GraphWorkloadGraphMutationWriter.split_operations(
                operations
            )
        except CanonicalSchemaMutationError as exc:
            return {"applied": False, "errors": [str(exc)]}

        if not define_ops and not instance_ops:
            return {"applied": True, "errors": [], "operations_applied": 0}

        errors: list[str] = []
        operations_applied = 0

        if define_ops:
            define_jsonl = "\n".join(
                json.dumps(operation.model_dump(mode="json")) for operation in define_ops
            )
            try:
                await self._repository.apply_mutation_log(knowledge_graph_id, define_jsonl)
            except CanonicalSchemaMutationError as exc:
                errors.append(str(exc))

        if instance_ops and not errors:
            instance_result = await self._mutation_writer.apply_instance_operations(
                tenant_id=tenant_id,
                knowledge_graph_id=knowledge_graph_id,
                operations=instance_ops,
            )
            if not instance_result.get("applied"):
                errors.extend(str(item) for item in instance_result.get("errors", []))
            else:
                operations_applied = int(instance_result.get("operations_applied", 0))

        if errors:
            await self._session.rollback()
            return {"applied": False, "errors": errors}

        await self._session.commit()
        return {"applied": True, "errors": [], "operations_applied": operations_applied}
