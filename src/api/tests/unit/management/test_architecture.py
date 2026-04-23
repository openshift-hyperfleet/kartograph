"""Architecture tests for the Management bounded context.

These tests enforce DDD architectural boundaries ensuring the Management
bounded context does not depend on other bounded contexts (IAM, Graph,
Extraction, Ingestion, Querying). Management may only import from
shared_kernel, infrastructure (cross-cutting), and its own sub-packages.

Written TDD-first: cross-context isolation rules pass trivially against
the empty module stub. DDD layer rules are conditionally skipped until
the corresponding subpackages are created (pytest-archon raises
"NO CANDIDATES MATCHED" on empty match sets).
"""

import importlib

import pytest
from pytest_archon import archrule


def _subpackage_exists(name: str) -> bool:
    """Check whether a Management subpackage has been created.

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


_has_domain = _subpackage_exists("management.domain")
_has_ports = _subpackage_exists("management.ports")
_has_application = _subpackage_exists("management.application")
_has_infrastructure = _subpackage_exists("management.infrastructure")
_has_presentation = _subpackage_exists("management.presentation")

_skip_no_domain = pytest.mark.skipif(
    not _has_domain,
    reason="management.domain subpackage does not exist yet",
)
_skip_no_ports = pytest.mark.skipif(
    not _has_ports,
    reason="management.ports subpackage does not exist yet",
)
_skip_no_application = pytest.mark.skipif(
    not _has_application,
    reason="management.application subpackage does not exist yet",
)
_skip_no_infrastructure = pytest.mark.skipif(
    not _has_infrastructure,
    reason="management.infrastructure subpackage does not exist yet",
)
_skip_no_presentation = pytest.mark.skipif(
    not _has_presentation,
    reason="management.presentation subpackage does not exist yet",
)


# ---------------------------------------------------------------------------
# DDD layer boundaries (within Management)
#
# These rules become enforceable when the corresponding subpackages are
# created. Until then they are skipped to avoid pytest-archon's
# "NO CANDIDATES MATCHED" failure on empty match sets.
# ---------------------------------------------------------------------------


@_skip_no_domain
class TestManagementDomainLayerBoundaries:
    """Tests that the Management domain layer has no forbidden dependencies."""

    def test_domain_does_not_import_infrastructure(self):
        """Domain layer should not depend on infrastructure.

        The domain layer contains pure business logic and should not
        know about database clients, SQL, or other infrastructure concerns.
        """
        (
            archrule("management_domain_no_infrastructure")
            .match("management.domain*")
            .should_not_import("management.infrastructure*")
            .check("management")
        )

    def test_domain_does_not_import_application(self):
        """Domain layer should not depend on application layer.

        Domain objects should be usable without application services.
        """
        (
            archrule("management_domain_no_application")
            .match("management.domain*")
            .should_not_import("management.application*")
            .check("management")
        )

    def test_domain_does_not_import_fastapi(self):
        """Domain layer should not depend on FastAPI.

        Domain objects should be framework-agnostic.
        """
        (
            archrule("management_domain_no_fastapi")
            .match("management.domain*")
            .should_not_import("fastapi*", "starlette*")
            .check("management")
        )


@_skip_no_ports
class TestManagementPortsLayerBoundaries:
    """Tests that the Management ports layer has no forbidden dependencies."""

    def test_ports_does_not_import_infrastructure(self):
        """Ports should not depend on infrastructure implementations.

        Ports define interfaces; they should not know about
        concrete implementations.
        """
        (
            archrule("management_ports_no_infrastructure")
            .match("management.ports*")
            .should_not_import("management.infrastructure*")
            .check("management")
        )

    def test_ports_does_not_import_application(self):
        """Ports should not depend on application layer.

        Ports are interfaces for the application layer to use,
        not the other way around.
        """
        (
            archrule("management_ports_no_application")
            .match("management.ports*")
            .should_not_import("management.application*")
            .check("management")
        )


@_skip_no_application
class TestManagementApplicationLayerBoundaries:
    """Tests that the Management application layer has appropriate dependencies."""

    def test_application_does_not_import_infrastructure(self):
        """Application layer should not directly import infrastructure.

        Application services should depend on repository interfaces (ports),
        not on infrastructure implementations.
        """
        (
            archrule("management_application_no_infrastructure")
            .match("management.application*")
            .should_not_import("management.infrastructure*")
            .check("management")
        )

    def test_application_can_import_domain_and_ports(self):
        """Application layer should be able to import domain and ports.

        These are allowed dependencies in our DDD architecture.
        """
        (
            archrule("management_application_may_import_domain_ports")
            .match("management.application*")
            .may_import("management.domain*", "management.ports*")
            .check("management")
        )


@_skip_no_infrastructure
class TestManagementInfrastructureLayerBoundaries:
    """Tests that Management infrastructure has appropriate dependencies."""

    def test_infrastructure_does_not_import_application(self):
        """Infrastructure should not depend on application layer.

        Infrastructure is used BY the application layer, not vice versa.
        """
        (
            archrule("management_infrastructure_no_application")
            .match("management.infrastructure*")
            .should_not_import("management.application*")
            .check("management")
        )

    def test_infrastructure_can_import_domain_and_ports(self):
        """Infrastructure can import domain and ports.

        Repository implementations need to convert between ORM models
        and domain aggregates, and implement the port interfaces.
        """
        (
            archrule("management_infrastructure_may_import_domain_ports")
            .match("management.infrastructure*")
            .may_import("management.domain*", "management.ports*")
            .check("management")
        )


# ---------------------------------------------------------------------------
# Cross-context isolation (Management must not import other contexts)
#
# These rules match against "management*" which resolves to the stub
# __init__.py, so they pass trivially now and become enforceable as
# the context is populated.
# ---------------------------------------------------------------------------


class TestManagementBoundedContextIsolation:
    """Tests that Management does not import from other bounded contexts.

    The Management bounded context is the Control Plane for the platform,
    managing metadata and configuration for KnowledgeGraphs and DataSources.
    It must remain fully decoupled from other bounded contexts to support
    independent deployment and evolution.
    """

    def test_management_does_not_import_iam(self):
        """Management bounded context should not depend on IAM context.

        IAM manages authentication and authorization. Management should
        not couple to IAM's user, tenant, or API key domain objects.

        Two packages are excluded from this restriction:
        - management.dependencies: DI wiring that extracts CurrentUser from
          IAM for tenant scoping (e.g., scope_to_tenant=current_user.tenant_id).
        - management.presentation: Route handlers that enforce authentication
          by declaring get_current_user as a FastAPI dependency and using
          CurrentUser to extract user_id for service calls. Only
          knowledge_graphs.routes legitimately imports IAM, but
          management.presentation.__init__ aggregates sub-routers, causing
          pytest-archon to propagate the IAM import up to the root package.
          The entire presentation tree must be excluded because of this
          transitive propagation through the router aggregation __init__.
        """
        (
            archrule("management_no_iam")
            .match("management*")
            .exclude("management.dependencies*", "management.presentation*")
            .should_not_import("iam*")
            .check("management")
        )

    def test_management_does_not_import_graph(self):
        """Management bounded context should not depend on Graph context.

        Graph is the persistence engine for knowledge graphs. Management
        manages configurations, not graph data directly.
        """
        (
            archrule("management_no_graph")
            .match("management*")
            .should_not_import("graph*")
            .check("management")
        )

    def test_management_does_not_import_ingestion(self):
        """Management bounded context should not depend on Ingestion context.

        Ingestion handles data extraction via adapters. Management defines
        configurations but should not couple to adapter implementations.
        """
        (
            archrule("management_no_ingestion")
            .match("management*")
            .should_not_import("ingestion*")
            .check("management")
        )

    def test_management_does_not_import_extraction(self):
        """Management bounded context should not depend on Extraction context.

        Extraction handles AI processing of raw content into graph data.
        Management has no reason to depend on extraction logic.
        """
        (
            archrule("management_no_extraction")
            .match("management*")
            .should_not_import("extraction*")
            .check("management")
        )

    def test_management_does_not_import_querying(self):
        """Management bounded context should not depend on Querying context.

        Querying provides read access via MCP server. Management should
        not couple to query translation or MCP concerns.
        """
        (
            archrule("management_no_querying")
            .match("management*")
            .should_not_import("query*")
            .check("management")
        )


# ---------------------------------------------------------------------------
# Allowed dependencies
# ---------------------------------------------------------------------------


class TestManagementAllowedDependencies:
    """Tests that Management can import from its allowed dependencies.

    Management is allowed to import from:
    - shared_kernel (authorization, outbox, types)
    - infrastructure (settings, database, cross-cutting concerns)
    - Other Management sub-packages (domain, ports, application, etc.)
    """

    def test_management_may_import_shared_kernel(self):
        """Management may import from shared_kernel (authorization, outbox, types)."""
        (
            archrule("management_may_import_shared_kernel")
            .match("management*")
            .may_import("shared_kernel*")
            .check("management")
        )

    def test_management_may_import_infrastructure(self):
        """Management may import from infrastructure (settings, database)."""
        (
            archrule("management_may_import_infrastructure")
            .match("management*")
            .may_import("infrastructure*")
            .check("management")
        )
