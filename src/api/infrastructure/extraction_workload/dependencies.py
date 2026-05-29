"""Dependencies for extraction workload HTTP endpoints."""

from __future__ import annotations

from functools import lru_cache
from typing import Annotated

from fastapi import Depends

from extraction.infrastructure.workload_runtime import ScopedWorkloadCredentialIssuer
from extraction.infrastructure.workload_runtime_factory import get_workload_credential_issuer
from extraction.ports.workload_graph import IWorkloadGraphReader
from infrastructure.database.connection_pool import ConnectionPool
from infrastructure.dependencies import get_age_connection_pool
from infrastructure.extraction_workload.graph_reader import GraphWorkloadGraphReader
from infrastructure.settings import get_database_settings


@lru_cache
def _cached_workload_credential_issuer() -> ScopedWorkloadCredentialIssuer:
    return get_workload_credential_issuer()


def get_extraction_workload_credential_issuer() -> ScopedWorkloadCredentialIssuer:
    return _cached_workload_credential_issuer()


def get_workload_graph_reader(
    pool: Annotated[ConnectionPool, Depends(get_age_connection_pool)],
) -> IWorkloadGraphReader:
    return GraphWorkloadGraphReader(pool=pool, settings=get_database_settings())
