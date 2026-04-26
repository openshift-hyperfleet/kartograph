"""Architecture tests for the Ingestion bounded context.

Enforces DDD architectural boundaries:
- Domain layer must not import infrastructure or application
- Infrastructure can import domain and ports
- Ingestion must not import management, IAM, or Graph internal domain types
"""

from __future__ import annotations

import importlib

import pytest
from pytest_archon import archrule


def _subpackage_exists(name: str) -> bool:
    """Check whether an Ingestion subpackage has been created."""
    try:
        importlib.import_module(name)
        return True
    except ModuleNotFoundError as e:
        if e.name == name:
            return False
        raise


_has_domain = _subpackage_exists("ingestion.domain")
_has_ports = _subpackage_exists("ingestion.ports")
_has_application = _subpackage_exists("ingestion.application")
_has_infrastructure = _subpackage_exists("ingestion.infrastructure")

_skip_no_domain = pytest.mark.skipif(
    not _has_domain,
    reason="ingestion.domain subpackage does not exist yet",
)
_skip_no_ports = pytest.mark.skipif(
    not _has_ports,
    reason="ingestion.ports subpackage does not exist yet",
)
_skip_no_application = pytest.mark.skipif(
    not _has_application,
    reason="ingestion.application subpackage does not exist yet",
)
_skip_no_infrastructure = pytest.mark.skipif(
    not _has_infrastructure,
    reason="ingestion.infrastructure subpackage does not exist yet",
)


@_skip_no_domain
class TestIngestionDomainLayerBoundaries:
    """Domain layer must be pure Python with no framework imports."""

    def test_domain_does_not_import_infrastructure(self):
        """Domain layer should not depend on infrastructure."""
        (
            archrule("ingestion_domain_no_infrastructure")
            .match("ingestion.domain*")
            .should_not_import("ingestion.infrastructure*")
            .check("ingestion")
        )

    def test_domain_does_not_import_application(self):
        """Domain layer should not depend on application layer."""
        (
            archrule("ingestion_domain_no_application")
            .match("ingestion.domain*")
            .should_not_import("ingestion.application*")
            .check("ingestion")
        )

    def test_domain_does_not_import_fastapi(self):
        """Domain layer should not depend on FastAPI."""
        (
            archrule("ingestion_domain_no_fastapi")
            .match("ingestion.domain*")
            .should_not_import("fastapi*", "starlette*")
            .check("ingestion")
        )


@_skip_no_application
class TestIngestionApplicationLayerBoundaries:
    """Application layer must not import infrastructure directly."""

    def test_application_does_not_import_infrastructure(self):
        """Application layer should not directly import infrastructure."""
        (
            archrule("ingestion_application_no_infrastructure")
            .match("ingestion.application*")
            .should_not_import("ingestion.infrastructure*")
            .check("ingestion")
        )


class TestIngestionBoundedContextIsolation:
    """Ingestion must not import from other bounded contexts' internals."""

    def test_ingestion_does_not_import_iam(self):
        """Ingestion should not depend on IAM context."""
        (
            archrule("ingestion_no_iam")
            .match("ingestion*")
            .should_not_import("iam*")
            .check("ingestion")
        )

    def test_ingestion_does_not_import_graph_domain(self):
        """Ingestion should not depend on Graph domain types."""
        (
            archrule("ingestion_no_graph_domain")
            .match("ingestion*")
            .should_not_import("graph.domain*", "graph.application*")
            .check("ingestion")
        )

    def test_ingestion_does_not_import_extraction(self):
        """Ingestion should not depend on Extraction context."""
        (
            archrule("ingestion_no_extraction")
            .match("ingestion*")
            .should_not_import("extraction*")
            .check("ingestion")
        )

    def test_ingestion_may_import_shared_kernel(self):
        """Ingestion may import from shared_kernel."""
        (
            archrule("ingestion_may_import_shared_kernel")
            .match("ingestion*")
            .may_import("shared_kernel*")
            .check("ingestion")
        )
