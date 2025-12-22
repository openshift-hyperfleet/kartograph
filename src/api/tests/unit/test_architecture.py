"""Architecture tests using pytest-archon.

These tests enforce DDD architectural boundaries between layers
within the Graph bounded context.
"""

from pytest_archon import archrule


class TestGraphDomainLayerBoundaries:
    """Tests that the domain layer has no forbidden dependencies."""

    def test_domain_does_not_import_infrastructure(self):
        """Domain layer should not depend on infrastructure.

        The domain layer contains pure business logic and should not
        know about database clients, SQL, or other infrastructure concerns.
        """
        (
            archrule("domain_no_infrastructure")
            .match("graph.domain*")
            .should_not_import("graph.infrastructure*")
            .check("graph")
        )

    def test_domain_does_not_import_application(self):
        """Domain layer should not depend on application layer.

        Domain objects should be usable without application services.
        """
        (
            archrule("domain_no_application")
            .match("graph.domain*")
            .should_not_import("graph.application*")
            .check("graph")
        )

    def test_domain_does_not_import_fastapi(self):
        """Domain layer should not depend on FastAPI.

        Domain objects should be framework-agnostic.
        """
        (
            archrule("domain_no_fastapi")
            .match("graph.domain*")
            .should_not_import("fastapi*", "starlette*")
            .check("graph")
        )


class TestGraphPortsLayerBoundaries:
    """Tests that the ports layer has no forbidden dependencies."""

    def test_ports_does_not_import_infrastructure(self):
        """Ports should not depend on infrastructure implementations.

        Ports define interfaces; they should not know about
        concrete implementations like AgeGraphClient.
        """
        (
            archrule("ports_no_infrastructure")
            .match("graph.ports*")
            .should_not_import("graph.infrastructure*")
            .check("graph")
        )

    def test_ports_does_not_import_application(self):
        """Ports should not depend on application layer.

        Ports are interfaces for the application layer to use,
        not the other way around.
        """
        (
            archrule("ports_no_application")
            .match("graph.ports*")
            .should_not_import("graph.application*")
            .check("graph")
        )


class TestGraphApplicationLayerBoundaries:
    """Tests that the application layer has appropriate dependencies."""

    def test_application_does_not_import_infrastructure(self):
        """Application layer should not directly import infrastructure.

        Application services should depend on repository interfaces (ports),
        not on infrastructure implementations like AgeGraphClient or
        GraphExtractionReadOnlyRepository.
        """
        (
            archrule("application_no_infrastructure")
            .match("graph.application*")
            .should_not_import("graph.infrastructure*")
            .check("graph")
        )

    def test_application_can_import_domain_and_ports(self):
        """Application layer should be able to import domain and ports.

        These are allowed dependencies in our DDD architecture.
        """
        (
            archrule("application_may_import_domain_ports")
            .match("graph.application*")
            .may_import("graph.domain*", "graph.ports*")
            .check("graph")
        )


class TestGraphInfrastructureLayerBoundaries:
    """Tests that infrastructure has appropriate dependencies."""

    def test_infrastructure_does_not_import_application(self):
        """Infrastructure should not depend on application layer.

        Infrastructure is used BY the application layer, not vice versa.
        """
        (
            archrule("infrastructure_no_application")
            .match("graph.infrastructure*")
            .should_not_import("graph.application*")
            .check("graph")
        )

    def test_infrastructure_can_import_domain_and_ports(self):
        """Infrastructure can import domain and ports.

        Repository implementations need to convert between
        infrastructure types (Vertex/Edge) and domain types (NodeRecord/EdgeRecord).
        They also implement the port interfaces.
        """
        (
            archrule("infrastructure_may_import_domain_ports")
            .match("graph.infrastructure*")
            .may_import("graph.domain*", "graph.ports*")
            .check("graph")
        )


class TestQueryDomainLayerBoundaries:
    """Tests that the Querying domain layer has no forbidden dependencies."""

    def test_query_domain_does_not_import_infrastructure(self):
        """Domain layer should not depend on infrastructure."""
        (
            archrule("query_domain_no_infrastructure")
            .match("query.domain*")
            .should_not_import("query.infrastructure*", "graph.infrastructure*")
            .check("query")
        )

    def test_query_domain_does_not_import_application(self):
        """Domain layer should not depend on application layer."""
        (
            archrule("query_domain_no_application")
            .match("query.domain*")
            .should_not_import("query.application*")
            .check("query")
        )


class TestQueryPortsLayerBoundaries:
    """Tests that Querying ports have no forbidden dependencies."""

    def test_query_ports_does_not_import_infrastructure(self):
        """Ports should not depend on infrastructure."""
        (
            archrule("query_ports_no_infrastructure")
            .match("query.ports*")
            .should_not_import("query.infrastructure*", "graph.infrastructure*")
            .check("query")
        )


class TestQueryApplicationLayerBoundaries:
    """Tests that Querying application layer has appropriate dependencies."""

    def test_query_application_does_not_import_infrastructure(self):
        """Application should not directly import infrastructure."""
        (
            archrule("query_application_no_infrastructure")
            .match("query.application*")
            .should_not_import("query.infrastructure*", "graph.infrastructure*")
            .check("query")
        )


class TestDependencyLayerBoundaries:
    """Tests that dependency modules respect DDD boundaries."""

    def test_infrastructure_dependencies_does_not_import_graph(self):
        """Infrastructure dependencies should not import bounded contexts."""
        (
            archrule("infrastructure_deps_no_graph")
            .match("infrastructure.dependencies*")
            .should_not_import("graph*")
            .check("infrastructure")
        )

    def test_infrastructure_dependencies_does_not_import_query(self):
        """Infrastructure dependencies should not import bounded contexts."""
        (
            archrule("infrastructure_deps_no_query")
            .match("infrastructure.dependencies*")
            .should_not_import("query*")
            .check("infrastructure")
        )

    def test_graph_dependencies_can_import_infrastructure(self):
        """Graph dependencies can import infrastructure (allowed)."""
        (
            archrule("graph_deps_may_import_infrastructure")
            .match("graph.dependencies*")
            .may_import("infrastructure*")
            .check("graph")
        )

    def test_graph_dependencies_does_not_import_query(self):
        """Graph dependencies should not import other contexts."""
        (
            archrule("graph_deps_no_query")
            .match("graph.dependencies*")
            .should_not_import("query*")
            .check("graph")
        )

    def test_infrastructure_mcp_dependencies_can_compose_contexts(self):
        """MCP composition layer can import from bounded contexts.

        infrastructure.mcp_dependencies is the composition/integration layer
        for MCP resources and tools. It's explicitly allowed to wire together
        Graph and Query contexts. This is the single point for future service
        decomposition - when splitting into microservices, swap GraphSchemaService
        here for an HTTP REST client.
        """
        (
            archrule("mcp_deps_may_compose")
            .match("infrastructure.mcp_dependencies*")
            .may_import("graph*", "query*")
            .check("infrastructure")
        )


class TestCrossContextBoundaries:
    """Tests that context boundaries are respected."""

    def test_query_does_not_import_graph_application(self):
        """Querying context should not import Graph application layer."""
        (
            archrule("query_no_graph_application")
            .match("query*")
            .should_not_import("graph.application*")
            .check("query")
        )

    def test_query_does_not_import_graph_domain(self):
        """Querying context should not import Graph domain objects.

        Each context should have its own domain objects to maintain
        proper bounded context isolation.
        """
        (
            archrule("query_no_graph_domain")
            .match("query.domain*", "query.application*", "query.ports*")
            .should_not_import("graph.domain*")
            .check("query")
        )


class TestSharedKernelBoundaries:
    """Tests that Shared Kernel boundaries are properly maintained.

    The Shared Kernel pattern requires explicit agreement between contexts.
    These tests ensure:
    1. Shared kernel doesn't create circular dependencies
    2. Bounded contexts can import from shared kernel
    3. No duplication of shared kernel logic in bounded contexts
    """

    def test_shared_kernel_does_not_import_bounded_contexts(self):
        """Shared kernel must not import from bounded contexts.

        The Shared Kernel is foundational and must not depend on any
        bounded context (graph, query, etc.) to avoid circular dependencies.
        This is critical for the pattern to work correctly.
        """
        (
            archrule("shared_kernel_no_bounded_contexts")
            .match("shared_kernel*")
            .should_not_import(
                "graph*",
                "query*",
                "management*",
                "ingestion*",
                "extraction*",
                "identity*",
            )
            .check("shared_kernel")
        )

    def test_shared_kernel_does_not_import_infrastructure(self):
        """Shared kernel should not import infrastructure layer.

        Shared kernel contains pure, portable logic that should not
        depend on database clients, connection pools, or other infrastructure.
        """
        (
            archrule("shared_kernel_no_infrastructure")
            .match("shared_kernel*")
            .should_not_import("infrastructure*")
            .check("shared_kernel")
        )

    def test_shared_kernel_does_not_import_fastapi(self):
        """Shared kernel should not import FastAPI.

        Shared kernel must be framework-agnostic to support reuse
        across contexts and future service separation.
        """
        (
            archrule("shared_kernel_no_fastapi")
            .match("shared_kernel*")
            .should_not_import("fastapi*", "starlette*")
            .check("shared_kernel")
        )

    def test_graph_context_can_import_shared_kernel(self):
        """Graph context may import from shared kernel.

        This is the intended use case for the Shared Kernel pattern -
        contexts explicitly agree to depend on shared foundational components.
        """
        (
            archrule("graph_may_import_shared_kernel")
            .match("graph*")
            .may_import("shared_kernel*")
            .check("graph")
        )

    def test_query_context_can_import_shared_kernel(self):
        """Query context may import from shared kernel.

        This is the intended use case for the Shared Kernel pattern -
        contexts explicitly agree to depend on shared foundational components.
        """
        (
            archrule("query_may_import_shared_kernel")
            .match("query*")
            .may_import("shared_kernel*")
            .check("query")
        )
