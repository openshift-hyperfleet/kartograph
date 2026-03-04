"""Architecture tests for the Graph bounded context.

These tests enforce DDD architectural boundaries ensuring the Graph
bounded context does not depend on other bounded contexts (IAM,
Management, Extraction, Ingestion, Querying). Graph may only import
from shared_kernel, infrastructure (cross-cutting), and its own
sub-packages.

Note: graph.presentation.routes imports iam.dependencies.user for
authentication. This is a legitimate cross-cutting concern — the
presentation layer uses IAM's FastAPI dependency for user authentication.
The isolation rules below account for this by scoping the IAM rule
to domain, ports, application, and infrastructure layers.
"""

from pytest_archon import archrule


class TestGraphBoundedContextIsolation:
    """Tests that Graph does not import from other bounded contexts.

    The Graph bounded context is the persistence engine. It executes
    writes and serves reads for knowledge graph data. It must remain
    fully decoupled from other bounded contexts to support independent
    deployment and evolution.
    """

    def test_graph_domain_ports_app_infra_does_not_import_iam(self):
        """Graph domain, ports, application, and infrastructure should not
        depend on IAM context.

        Note: graph.presentation.routes legitimately imports
        iam.dependencies.user for authentication middleware. That is
        allowed as a cross-cutting presentation concern but the inner
        layers must remain isolated.
        """
        (
            archrule("graph_inner_no_iam")
            .match(
                "graph.domain*",
                "graph.ports*",
                "graph.application*",
                "graph.infrastructure*",
            )
            .should_not_import("iam*")
            .check("graph")
        )

    def test_graph_does_not_import_management(self):
        """Graph bounded context should not depend on Management context.

        Management is the control plane for configurations. Graph handles
        persistence, not configuration management.
        """
        (
            archrule("graph_no_management")
            .match("graph*")
            .should_not_import("management*")
            .check("graph")
        )

    def test_graph_does_not_import_ingestion(self):
        """Graph bounded context should not depend on Ingestion context.

        Ingestion handles data extraction via adapters. Graph should not
        couple to ingestion adapters or job packages.
        """
        (
            archrule("graph_no_ingestion")
            .match("graph*")
            .should_not_import("ingestion*")
            .check("graph")
        )

    def test_graph_does_not_import_extraction(self):
        """Graph bounded context should not depend on Extraction context.

        Extraction handles AI processing of raw content into graph data.
        Graph receives mutation logs from Extraction but should not
        import Extraction code directly.
        """
        (
            archrule("graph_no_extraction")
            .match("graph*")
            .should_not_import("extraction*")
            .check("graph")
        )

    def test_graph_does_not_import_querying(self):
        """Graph bounded context should not depend on Querying context.

        Querying provides read access via MCP server. Graph should not
        couple to query translation or MCP concerns.
        """
        (
            archrule("graph_no_querying")
            .match("graph*")
            .should_not_import("query*")
            .check("graph")
        )


class TestGraphDomainBoundedContextIsolation:
    """Tests that Graph domain layer is isolated from other bounded contexts.

    The domain layer is the innermost ring and must be the most strictly
    isolated. It should contain only pure business logic.
    """

    def test_graph_domain_does_not_import_iam(self):
        """Graph domain should not import from IAM context."""
        (
            archrule("graph_domain_no_iam")
            .match("graph.domain*")
            .should_not_import("iam*")
            .check("graph")
        )

    def test_graph_domain_does_not_import_management(self):
        """Graph domain should not import from Management context."""
        (
            archrule("graph_domain_no_management")
            .match("graph.domain*")
            .should_not_import("management*")
            .check("graph")
        )

    def test_graph_domain_does_not_import_extraction(self):
        """Graph domain should not import from Extraction context."""
        (
            archrule("graph_domain_no_extraction")
            .match("graph.domain*")
            .should_not_import("extraction*")
            .check("graph")
        )

    def test_graph_domain_does_not_import_ingestion(self):
        """Graph domain should not import from Ingestion context."""
        (
            archrule("graph_domain_no_ingestion")
            .match("graph.domain*")
            .should_not_import("ingestion*")
            .check("graph")
        )

    def test_graph_domain_does_not_import_querying(self):
        """Graph domain should not import from Querying context."""
        (
            archrule("graph_domain_no_querying")
            .match("graph.domain*")
            .should_not_import("query*")
            .check("graph")
        )


class TestGraphApplicationBoundedContextIsolation:
    """Tests that Graph application layer is isolated from other bounded contexts.

    Application services orchestrate domain logic but must not reach
    across context boundaries.
    """

    def test_graph_application_does_not_import_iam(self):
        """Graph application should not import from IAM context."""
        (
            archrule("graph_app_no_iam")
            .match("graph.application*")
            .should_not_import("iam*")
            .check("graph")
        )

    def test_graph_application_does_not_import_management(self):
        """Graph application should not import from Management context."""
        (
            archrule("graph_app_no_management")
            .match("graph.application*")
            .should_not_import("management*")
            .check("graph")
        )

    def test_graph_application_does_not_import_extraction(self):
        """Graph application should not import from Extraction context."""
        (
            archrule("graph_app_no_extraction")
            .match("graph.application*")
            .should_not_import("extraction*")
            .check("graph")
        )

    def test_graph_application_does_not_import_ingestion(self):
        """Graph application should not import from Ingestion context."""
        (
            archrule("graph_app_no_ingestion")
            .match("graph.application*")
            .should_not_import("ingestion*")
            .check("graph")
        )

    def test_graph_application_does_not_import_querying(self):
        """Graph application should not import from Querying context."""
        (
            archrule("graph_app_no_querying")
            .match("graph.application*")
            .should_not_import("query*")
            .check("graph")
        )


class TestGraphInfrastructureBoundedContextIsolation:
    """Tests that Graph infrastructure layer is isolated from other bounded contexts.

    Infrastructure implementations (repositories, AGE client) must not
    cross bounded context boundaries.
    """

    def test_graph_infrastructure_does_not_import_iam(self):
        """Graph infrastructure should not import from IAM context."""
        (
            archrule("graph_infra_no_iam")
            .match("graph.infrastructure*")
            .should_not_import("iam*")
            .check("graph")
        )

    def test_graph_infrastructure_does_not_import_management(self):
        """Graph infrastructure should not import from Management context."""
        (
            archrule("graph_infra_no_management")
            .match("graph.infrastructure*")
            .should_not_import("management*")
            .check("graph")
        )

    def test_graph_infrastructure_does_not_import_extraction(self):
        """Graph infrastructure should not import from Extraction context."""
        (
            archrule("graph_infra_no_extraction")
            .match("graph.infrastructure*")
            .should_not_import("extraction*")
            .check("graph")
        )

    def test_graph_infrastructure_does_not_import_ingestion(self):
        """Graph infrastructure should not import from Ingestion context."""
        (
            archrule("graph_infra_no_ingestion")
            .match("graph.infrastructure*")
            .should_not_import("ingestion*")
            .check("graph")
        )

    def test_graph_infrastructure_does_not_import_querying(self):
        """Graph infrastructure should not import from Querying context."""
        (
            archrule("graph_infra_no_querying")
            .match("graph.infrastructure*")
            .should_not_import("query*")
            .check("graph")
        )


class TestGraphPresentationBoundedContextIsolation:
    """Tests that Graph presentation layer is isolated from other bounded contexts.

    Routes and HTTP handlers must not reach into other bounded contexts
    for domain objects or infrastructure.

    Exception: graph.presentation.routes imports iam.dependencies.user
    for FastAPI authentication — this is a legitimate cross-cutting
    presentation concern. IAM isolation is enforced at the inner layers.
    """

    def test_graph_presentation_does_not_import_management(self):
        """Graph presentation should not import from Management context."""
        (
            archrule("graph_pres_no_management")
            .match("graph.presentation*")
            .should_not_import("management*")
            .check("graph")
        )

    def test_graph_presentation_does_not_import_extraction(self):
        """Graph presentation should not import from Extraction context."""
        (
            archrule("graph_pres_no_extraction")
            .match("graph.presentation*")
            .should_not_import("extraction*")
            .check("graph")
        )

    def test_graph_presentation_does_not_import_ingestion(self):
        """Graph presentation should not import from Ingestion context."""
        (
            archrule("graph_pres_no_ingestion")
            .match("graph.presentation*")
            .should_not_import("ingestion*")
            .check("graph")
        )

    def test_graph_presentation_does_not_import_querying(self):
        """Graph presentation should not import from Querying context."""
        (
            archrule("graph_pres_no_querying")
            .match("graph.presentation*")
            .should_not_import("query*")
            .check("graph")
        )


class TestGraphAllowedDependencies:
    """Tests that Graph can import from its allowed dependencies.

    Graph is allowed to import from:
    - shared_kernel (authorization, outbox, graph primitives)
    - infrastructure (settings, database, cross-cutting concerns)
    - Other Graph sub-packages (domain, ports, application, etc.)
    """

    def test_graph_may_import_shared_kernel(self):
        """Graph may import from shared_kernel (authorization, outbox, types)."""
        (
            archrule("graph_may_import_shared_kernel")
            .match("graph*")
            .may_import("shared_kernel*")
            .check("graph")
        )

    def test_graph_may_import_infrastructure(self):
        """Graph may import from infrastructure (settings, database)."""
        (
            archrule("graph_may_import_infrastructure")
            .match("graph*")
            .may_import("infrastructure*")
            .check("graph")
        )
