"""Architecture tests for the Ingestion bounded context.

These tests enforce DDD architectural boundaries ensuring the Ingestion
bounded context does not depend on other bounded contexts (IAM, Graph,
Extraction, Management, Querying). Ingestion may only import from
shared_kernel, infrastructure (cross-cutting), and its own sub-packages.

Key domain isolation rule: the adapter port (IDatasourceAdapter) lives in
the Ingestion domain/ports layer and must NOT import dlt or any adapter
framework — that is an infrastructure-layer concern.
"""

import importlib

import pytest
from pytest_archon import archrule


def _subpackage_exists(name: str) -> bool:
    """Check whether an Ingestion subpackage has been created.

    Only returns False when the target package itself is missing.
    Re-raises ModuleNotFoundError for broken nested imports so that
    real import errors inside an existing package surface immediately.
    """
    try:
        importlib.import_module(name)
        return True
    except ModuleNotFoundError as e:
        if e.name == name:
            return False
        raise


_has_domain = _subpackage_exists("ingestion.domain")
_has_ports = _subpackage_exists("ingestion.ports")
_has_infrastructure = _subpackage_exists("ingestion.infrastructure")

_skip_no_domain = pytest.mark.skipif(
    not _has_domain,
    reason="ingestion.domain subpackage does not exist yet",
)
_skip_no_ports = pytest.mark.skipif(
    not _has_ports,
    reason="ingestion.ports subpackage does not exist yet",
)
_skip_no_infrastructure = pytest.mark.skipif(
    not _has_infrastructure,
    reason="ingestion.infrastructure subpackage does not exist yet",
)


# ---------------------------------------------------------------------------
# Domain isolation: adapter port must not import dlt or adapter frameworks
# ---------------------------------------------------------------------------


@_skip_no_ports
class TestIngestionPortsDomainIsolation:
    """The adapter port lives in the Ingestion domain layer.

    The IDatasourceAdapter protocol is a pure Python Protocol. It must
    not import dlt, httpx, or any other adapter framework — those are
    infrastructure concerns. This is the critical domain isolation rule
    from the spec's 'Domain isolation' scenario.
    """

    def test_ports_does_not_import_dlt(self):
        """Adapter port must not import dlt or any adapter framework.

        Spec scenario: Domain isolation
        - GIVEN the adapter port definition
        - THEN the domain layer does not import dlt or any adapter framework
        """
        (
            archrule("ingestion_ports_no_dlt")
            .match("ingestion.ports*")
            .should_not_import("dlt*")
            .check("ingestion")
        )

    def test_ports_does_not_import_httpx(self):
        """Adapter port must not import httpx (an HTTP client library).

        Ports define interfaces only; HTTP transport is infrastructure.
        """
        (
            archrule("ingestion_ports_no_httpx")
            .match("ingestion.ports*")
            .should_not_import("httpx*")
            .check("ingestion")
        )

    def test_ports_does_not_import_infrastructure(self):
        """Ports should not depend on infrastructure implementations."""
        (
            archrule("ingestion_ports_no_infrastructure")
            .match("ingestion.ports*")
            .should_not_import("ingestion.infrastructure*")
            .check("ingestion")
        )

    def test_ports_does_not_import_fastapi(self):
        """Ports must not import FastAPI; they are framework-agnostic."""
        (
            archrule("ingestion_ports_no_fastapi")
            .match("ingestion.ports*")
            .should_not_import("fastapi*", "starlette*")
            .check("ingestion")
        )


@_skip_no_domain
class TestIngestionDomainLayerBoundaries:
    """The Ingestion domain layer has no forbidden dependencies."""

    def test_domain_does_not_import_infrastructure(self):
        """Domain layer should not depend on infrastructure."""
        (
            archrule("ingestion_domain_no_infrastructure")
            .match("ingestion.domain*")
            .should_not_import("ingestion.infrastructure*")
            .check("ingestion")
        )

    def test_domain_does_not_import_dlt(self):
        """Domain layer must not import dlt or any adapter framework."""
        (
            archrule("ingestion_domain_no_dlt")
            .match("ingestion.domain*")
            .should_not_import("dlt*")
            .check("ingestion")
        )

    def test_domain_does_not_import_fastapi(self):
        """Domain layer must not import FastAPI."""
        (
            archrule("ingestion_domain_no_fastapi")
            .match("ingestion.domain*")
            .should_not_import("fastapi*", "starlette*")
            .check("ingestion")
        )


# ---------------------------------------------------------------------------
# Cross-context isolation
# ---------------------------------------------------------------------------


class TestIngestionBoundedContextIsolation:
    """Ingestion must not import from other bounded contexts.

    The Ingestion bounded context is responsible for extracting raw data
    via adapters. It communicates with Management via the shared kernel
    (ICredentialReader) and produces JobPackages for the Extraction context
    via domain events — never by direct import.
    """

    def test_ingestion_does_not_import_iam(self):
        """Ingestion must not depend on IAM context."""
        (
            archrule("ingestion_no_iam")
            .match("ingestion*")
            .should_not_import("iam*")
            .check("ingestion")
        )

    def test_ingestion_does_not_import_graph(self):
        """Ingestion must not depend on Graph context."""
        (
            archrule("ingestion_no_graph")
            .match("ingestion*")
            .should_not_import("graph*")
            .check("ingestion")
        )

    def test_ingestion_does_not_import_management(self):
        """Ingestion must not depend on Management context directly.

        Ingestion retrieves credentials via the ICredentialReader port
        in the shared kernel — NOT by importing management internals.
        This is the 'Backend independence' scenario: the Ingestion context
        requires no code changes when the Management credential backend
        changes (e.g., Fernet → Vault).
        """
        (
            archrule("ingestion_no_management")
            .match("ingestion*")
            .should_not_import("management*")
            .check("ingestion")
        )

    def test_ingestion_does_not_import_extraction(self):
        """Ingestion must not depend on Extraction context."""
        (
            archrule("ingestion_no_extraction")
            .match("ingestion*")
            .should_not_import("extraction*")
            .check("ingestion")
        )

    def test_ingestion_does_not_import_query(self):
        """Ingestion must not depend on Querying context."""
        (
            archrule("ingestion_no_query")
            .match("ingestion*")
            .should_not_import("query*")
            .check("ingestion")
        )


# ---------------------------------------------------------------------------
# Allowed dependencies
# ---------------------------------------------------------------------------


class TestIngestionAllowedDependencies:
    """Ingestion may import from shared_kernel and its own sub-packages."""

    def test_ingestion_may_import_shared_kernel(self):
        """Ingestion may import from shared_kernel.

        The shared kernel provides ICredentialReader (credential port),
        job package value objects (ChangesetEntry, AdapterCheckpoint, etc.),
        and DataSourceAdapterType. These are explicitly agreed shared types.
        """
        (
            archrule("ingestion_may_import_shared_kernel")
            .match("ingestion*")
            .may_import("shared_kernel*")
            .check("ingestion")
        )
