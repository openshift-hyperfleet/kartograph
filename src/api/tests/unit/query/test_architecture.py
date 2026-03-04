"""Architecture tests for the Query bounded context.

These tests enforce DDD architectural boundaries ensuring the Query
bounded context does not depend on other bounded contexts (IAM,
Management, Graph, Extraction, Ingestion). Query may only import
from shared_kernel, infrastructure (cross-cutting), and its own
sub-packages.

Note on Query -> Graph coupling:
- query.infrastructure.query_repository imports graph.ports.protocols
  (GraphClientProtocol) — a shared port interface used as an integration
  contract between contexts.
- query.dependencies imports graph.infrastructure.age_client — this is
  the composition/wiring layer analogous to infrastructure.mcp_dependencies.

These couplings are documented and scoped. The domain, ports, and
application layers of Query remain fully isolated from Graph.
"""

from pytest_archon import archrule


class TestQueryBoundedContextIsolation:
    """Tests that Query does not import from other bounded contexts.

    The Query bounded context is the consumer interface. It provides
    read access to end-users and agents via the MCP server. It must
    remain fully decoupled from other bounded contexts to support
    independent deployment and evolution.
    """

    def test_query_does_not_import_iam(self):
        """Query bounded context should not depend on IAM context.

        IAM manages authentication and authorization. Query should not
        couple to IAM's user, tenant, or API key domain objects.
        """
        (
            archrule("query_no_iam")
            .match("query*")
            .should_not_import("iam*")
            .check("query")
        )

    def test_query_does_not_import_management(self):
        """Query bounded context should not depend on Management context.

        Management is the control plane for configurations. Query handles
        read access, not configuration management.
        """
        (
            archrule("query_no_management")
            .match("query*")
            .should_not_import("management*")
            .check("query")
        )

    def test_query_does_not_import_graph_domain_or_application(self):
        """Query domain, ports, and application should not import Graph
        domain or application layers.

        Each context should have its own domain objects to maintain
        proper bounded context isolation. The existing narrower rules
        in test_architecture.py enforce this for domain and application.
        """
        (
            archrule("query_no_graph_domain_app")
            .match("query.domain*", "query.ports*", "query.application*")
            .should_not_import("graph.domain*", "graph.application*")
            .check("query")
        )

    def test_query_does_not_import_ingestion(self):
        """Query bounded context should not depend on Ingestion context.

        Ingestion handles data extraction via adapters. Query should not
        couple to ingestion adapters or job packages.
        """
        (
            archrule("query_no_ingestion")
            .match("query*")
            .should_not_import("ingestion*")
            .check("query")
        )

    def test_query_does_not_import_extraction(self):
        """Query bounded context should not depend on Extraction context.

        Extraction handles AI processing of raw content into graph data.
        Query has no reason to depend on extraction logic.
        """
        (
            archrule("query_no_extraction")
            .match("query*")
            .should_not_import("extraction*")
            .check("query")
        )


class TestQueryDomainBoundedContextIsolation:
    """Tests that Query domain layer is isolated from other bounded contexts.

    The domain layer is the innermost ring and must be the most strictly
    isolated. It should contain only pure business logic.
    """

    def test_query_domain_does_not_import_iam(self):
        """Query domain should not import from IAM context."""
        (
            archrule("query_domain_no_iam")
            .match("query.domain*")
            .should_not_import("iam*")
            .check("query")
        )

    def test_query_domain_does_not_import_management(self):
        """Query domain should not import from Management context."""
        (
            archrule("query_domain_no_management")
            .match("query.domain*")
            .should_not_import("management*")
            .check("query")
        )

    def test_query_domain_does_not_import_graph(self):
        """Query domain should not import from Graph context."""
        (
            archrule("query_domain_no_graph")
            .match("query.domain*")
            .should_not_import("graph*")
            .check("query")
        )

    def test_query_domain_does_not_import_extraction(self):
        """Query domain should not import from Extraction context."""
        (
            archrule("query_domain_no_extraction")
            .match("query.domain*")
            .should_not_import("extraction*")
            .check("query")
        )

    def test_query_domain_does_not_import_ingestion(self):
        """Query domain should not import from Ingestion context."""
        (
            archrule("query_domain_no_ingestion")
            .match("query.domain*")
            .should_not_import("ingestion*")
            .check("query")
        )


class TestQueryApplicationBoundedContextIsolation:
    """Tests that Query application layer is isolated from other bounded contexts.

    Application services orchestrate domain logic but must not reach
    across context boundaries.
    """

    def test_query_application_does_not_import_iam(self):
        """Query application should not import from IAM context."""
        (
            archrule("query_app_no_iam")
            .match("query.application*")
            .should_not_import("iam*")
            .check("query")
        )

    def test_query_application_does_not_import_management(self):
        """Query application should not import from Management context."""
        (
            archrule("query_app_no_management")
            .match("query.application*")
            .should_not_import("management*")
            .check("query")
        )

    def test_query_application_does_not_import_graph(self):
        """Query application should not import from Graph context."""
        (
            archrule("query_app_no_graph")
            .match("query.application*")
            .should_not_import("graph*")
            .check("query")
        )

    def test_query_application_does_not_import_extraction(self):
        """Query application should not import from Extraction context."""
        (
            archrule("query_app_no_extraction")
            .match("query.application*")
            .should_not_import("extraction*")
            .check("query")
        )

    def test_query_application_does_not_import_ingestion(self):
        """Query application should not import from Ingestion context."""
        (
            archrule("query_app_no_ingestion")
            .match("query.application*")
            .should_not_import("ingestion*")
            .check("query")
        )


class TestQueryPortsBoundedContextIsolation:
    """Tests that Query ports layer is isolated from other bounded contexts.

    Port interfaces define contracts; they must not depend on other
    bounded contexts.
    """

    def test_query_ports_does_not_import_iam(self):
        """Query ports should not import from IAM context."""
        (
            archrule("query_ports_no_iam")
            .match("query.ports*")
            .should_not_import("iam*")
            .check("query")
        )

    def test_query_ports_does_not_import_management(self):
        """Query ports should not import from Management context."""
        (
            archrule("query_ports_no_management")
            .match("query.ports*")
            .should_not_import("management*")
            .check("query")
        )

    def test_query_ports_does_not_import_graph(self):
        """Query ports should not import from Graph context."""
        (
            archrule("query_ports_no_graph")
            .match("query.ports*")
            .should_not_import("graph*")
            .check("query")
        )

    def test_query_ports_does_not_import_extraction(self):
        """Query ports should not import from Extraction context."""
        (
            archrule("query_ports_no_extraction")
            .match("query.ports*")
            .should_not_import("extraction*")
            .check("query")
        )

    def test_query_ports_does_not_import_ingestion(self):
        """Query ports should not import from Ingestion context."""
        (
            archrule("query_ports_no_ingestion")
            .match("query.ports*")
            .should_not_import("ingestion*")
            .check("query")
        )


class TestQueryInfrastructureBoundedContextIsolation:
    """Tests that Query infrastructure layer is isolated from other bounded contexts.

    Infrastructure implementations (repositories, prompt repository)
    must not cross bounded context boundaries.

    Exception: query.infrastructure.query_repository imports
    graph.ports.protocols.GraphClientProtocol as an integration contract.
    Graph domain/application/infrastructure imports are still forbidden.
    """

    def test_query_infrastructure_does_not_import_iam(self):
        """Query infrastructure should not import from IAM context."""
        (
            archrule("query_infra_no_iam")
            .match("query.infrastructure*")
            .should_not_import("iam*")
            .check("query")
        )

    def test_query_infrastructure_does_not_import_management(self):
        """Query infrastructure should not import from Management context."""
        (
            archrule("query_infra_no_management")
            .match("query.infrastructure*")
            .should_not_import("management*")
            .check("query")
        )

    def test_query_infrastructure_does_not_import_graph_internals(self):
        """Query infrastructure should not import Graph domain, application,
        or infrastructure.

        Note: query.infrastructure.query_repository imports
        graph.ports.protocols.GraphClientProtocol which is allowed as
        a shared port contract. Only Graph internals are forbidden.
        """
        (
            archrule("query_infra_no_graph_internals")
            .match("query.infrastructure*")
            .should_not_import(
                "graph.domain*",
                "graph.application*",
                "graph.infrastructure*",
            )
            .check("query")
        )

    def test_query_infrastructure_does_not_import_extraction(self):
        """Query infrastructure should not import from Extraction context."""
        (
            archrule("query_infra_no_extraction")
            .match("query.infrastructure*")
            .should_not_import("extraction*")
            .check("query")
        )

    def test_query_infrastructure_does_not_import_ingestion(self):
        """Query infrastructure should not import from Ingestion context."""
        (
            archrule("query_infra_no_ingestion")
            .match("query.infrastructure*")
            .should_not_import("ingestion*")
            .check("query")
        )


class TestQueryPresentationBoundedContextIsolation:
    """Tests that Query presentation layer is isolated from other bounded contexts.

    MCP server and HTTP handlers must not reach into other bounded contexts
    for domain objects or infrastructure.

    Exception: query.presentation.mcp transitively reaches
    graph.ports.protocols and graph.infrastructure.age_client via
    query.dependencies (the composition layer). Presentation-layer
    rules for Graph are scoped to domain and application only.
    """

    def test_query_presentation_does_not_import_iam(self):
        """Query presentation should not import from IAM context."""
        (
            archrule("query_pres_no_iam")
            .match("query.presentation*")
            .should_not_import("iam*")
            .check("query")
        )

    def test_query_presentation_does_not_import_management(self):
        """Query presentation should not import from Management context."""
        (
            archrule("query_pres_no_management")
            .match("query.presentation*")
            .should_not_import("management*")
            .check("query")
        )

    def test_query_presentation_does_not_import_graph_domain_or_application(self):
        """Query presentation should not import Graph domain or application.

        The composition layer (query.dependencies) wires Graph
        infrastructure, but Graph domain and application objects must
        not leak into the Query presentation layer.
        """
        (
            archrule("query_pres_no_graph_domain_app")
            .match("query.presentation*")
            .should_not_import("graph.domain*", "graph.application*")
            .check("query")
        )

    def test_query_presentation_does_not_import_extraction(self):
        """Query presentation should not import from Extraction context."""
        (
            archrule("query_pres_no_extraction")
            .match("query.presentation*")
            .should_not_import("extraction*")
            .check("query")
        )

    def test_query_presentation_does_not_import_ingestion(self):
        """Query presentation should not import from Ingestion context."""
        (
            archrule("query_pres_no_ingestion")
            .match("query.presentation*")
            .should_not_import("ingestion*")
            .check("query")
        )


class TestQueryAllowedDependencies:
    """Tests that Query can import from its allowed dependencies.

    Query is allowed to import from:
    - shared_kernel (authorization, outbox, types)
    - infrastructure (settings, database, cross-cutting concerns)
    - Other Query sub-packages (domain, ports, application, etc.)
    """

    def test_query_may_import_shared_kernel(self):
        """Query may import from shared_kernel (authorization, outbox, types)."""
        (
            archrule("query_may_import_shared_kernel")
            .match("query*")
            .may_import("shared_kernel*")
            .check("query")
        )

    def test_query_may_import_infrastructure(self):
        """Query may import from infrastructure (settings, database)."""
        (
            archrule("query_may_import_infrastructure")
            .match("query*")
            .may_import("infrastructure*")
            .check("query")
        )
