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
        GraphReadOnlyRepository.
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
