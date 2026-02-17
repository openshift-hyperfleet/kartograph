"""Architecture tests for the IAM bounded context.

These tests enforce DDD architectural boundaries ensuring the IAM
bounded context does not depend on other bounded contexts (Graph,
Extraction, Management, Ingestion, Querying). IAM may only import
from shared_kernel, infrastructure (cross-cutting), and its own
sub-packages.
"""

from pytest_archon import archrule


class TestIAMBoundedContextIsolation:
    """Tests that IAM does not import from other bounded contexts.

    The IAM bounded context manages Authentication & Authorization,
    including User, Team, Tenant, and API Key lifecycle management.
    It must remain fully decoupled from other bounded contexts to
    support independent deployment and evolution.
    """

    def test_iam_does_not_import_graph(self):
        """IAM bounded context should not depend on Graph context.

        Graph is the persistence engine for knowledge graphs. IAM has
        no business importing graph domain objects, repositories, or
        infrastructure.
        """
        (
            archrule("iam_no_graph")
            .match("iam*")
            .should_not_import("graph*")
            .check("iam")
        )

    def test_iam_does_not_import_extraction(self):
        """IAM bounded context should not depend on Extraction context.

        Extraction handles AI processing of raw content into graph data.
        IAM has no reason to depend on extraction logic.
        """
        (
            archrule("iam_no_extraction")
            .match("iam*")
            .should_not_import("extraction*")
            .check("iam")
        )

    def test_iam_does_not_import_management(self):
        """IAM bounded context should not depend on Management context.

        Management is the control plane for KnowledgeGraph and DataSource
        configurations. IAM should not couple to management operations.
        """
        (
            archrule("iam_no_management")
            .match("iam*")
            .should_not_import("management*")
            .check("iam")
        )

    def test_iam_does_not_import_ingestion(self):
        """IAM bounded context should not depend on Ingestion context.

        Ingestion handles data extraction via adapters. IAM should not
        couple to ingestion adapters or job packages.
        """
        (
            archrule("iam_no_ingestion")
            .match("iam*")
            .should_not_import("ingestion*")
            .check("iam")
        )

    def test_iam_does_not_import_querying(self):
        """IAM bounded context should not depend on Querying context.

        Querying provides read access via MCP server. IAM should not
        couple to query translation or MCP concerns.
        """
        (
            archrule("iam_no_querying")
            .match("iam*")
            .should_not_import("query*")
            .check("iam")
        )


class TestIAMDomainBoundedContextIsolation:
    """Tests that IAM domain layer is isolated from other bounded contexts.

    The domain layer is the innermost ring and must be the most strictly
    isolated. It should contain only pure business logic.
    """

    def test_iam_domain_does_not_import_graph(self):
        """IAM domain should not import from Graph context."""
        (
            archrule("iam_domain_no_graph")
            .match("iam.domain*")
            .should_not_import("graph*")
            .check("iam")
        )

    def test_iam_domain_does_not_import_extraction(self):
        """IAM domain should not import from Extraction context."""
        (
            archrule("iam_domain_no_extraction")
            .match("iam.domain*")
            .should_not_import("extraction*")
            .check("iam")
        )

    def test_iam_domain_does_not_import_management(self):
        """IAM domain should not import from Management context."""
        (
            archrule("iam_domain_no_management")
            .match("iam.domain*")
            .should_not_import("management*")
            .check("iam")
        )

    def test_iam_domain_does_not_import_ingestion(self):
        """IAM domain should not import from Ingestion context."""
        (
            archrule("iam_domain_no_ingestion")
            .match("iam.domain*")
            .should_not_import("ingestion*")
            .check("iam")
        )

    def test_iam_domain_does_not_import_querying(self):
        """IAM domain should not import from Querying context."""
        (
            archrule("iam_domain_no_querying")
            .match("iam.domain*")
            .should_not_import("query*")
            .check("iam")
        )


class TestIAMApplicationBoundedContextIsolation:
    """Tests that IAM application layer is isolated from other bounded contexts.

    Application services orchestrate domain logic but must not reach
    across context boundaries.
    """

    def test_iam_application_does_not_import_graph(self):
        """IAM application should not import from Graph context."""
        (
            archrule("iam_app_no_graph")
            .match("iam.application*")
            .should_not_import("graph*")
            .check("iam")
        )

    def test_iam_application_does_not_import_extraction(self):
        """IAM application should not import from Extraction context."""
        (
            archrule("iam_app_no_extraction")
            .match("iam.application*")
            .should_not_import("extraction*")
            .check("iam")
        )

    def test_iam_application_does_not_import_management(self):
        """IAM application should not import from Management context."""
        (
            archrule("iam_app_no_management")
            .match("iam.application*")
            .should_not_import("management*")
            .check("iam")
        )

    def test_iam_application_does_not_import_ingestion(self):
        """IAM application should not import from Ingestion context."""
        (
            archrule("iam_app_no_ingestion")
            .match("iam.application*")
            .should_not_import("ingestion*")
            .check("iam")
        )

    def test_iam_application_does_not_import_querying(self):
        """IAM application should not import from Querying context."""
        (
            archrule("iam_app_no_querying")
            .match("iam.application*")
            .should_not_import("query*")
            .check("iam")
        )


class TestIAMInfrastructureBoundedContextIsolation:
    """Tests that IAM infrastructure layer is isolated from other bounded contexts.

    Infrastructure implementations (repositories, ORM models) must not
    cross bounded context boundaries.
    """

    def test_iam_infrastructure_does_not_import_graph(self):
        """IAM infrastructure should not import from Graph context."""
        (
            archrule("iam_infra_no_graph")
            .match("iam.infrastructure*")
            .should_not_import("graph*")
            .check("iam")
        )

    def test_iam_infrastructure_does_not_import_extraction(self):
        """IAM infrastructure should not import from Extraction context."""
        (
            archrule("iam_infra_no_extraction")
            .match("iam.infrastructure*")
            .should_not_import("extraction*")
            .check("iam")
        )

    def test_iam_infrastructure_does_not_import_management(self):
        """IAM infrastructure should not import from Management context."""
        (
            archrule("iam_infra_no_management")
            .match("iam.infrastructure*")
            .should_not_import("management*")
            .check("iam")
        )

    def test_iam_infrastructure_does_not_import_ingestion(self):
        """IAM infrastructure should not import from Ingestion context."""
        (
            archrule("iam_infra_no_ingestion")
            .match("iam.infrastructure*")
            .should_not_import("ingestion*")
            .check("iam")
        )

    def test_iam_infrastructure_does_not_import_querying(self):
        """IAM infrastructure should not import from Querying context."""
        (
            archrule("iam_infra_no_querying")
            .match("iam.infrastructure*")
            .should_not_import("query*")
            .check("iam")
        )


class TestIAMPresentationBoundedContextIsolation:
    """Tests that IAM presentation layer is isolated from other bounded contexts.

    Routes and HTTP handlers must not reach into other bounded contexts
    for domain objects or infrastructure.
    """

    def test_iam_presentation_does_not_import_graph(self):
        """IAM presentation should not import from Graph context."""
        (
            archrule("iam_pres_no_graph")
            .match("iam.presentation*")
            .should_not_import("graph*")
            .check("iam")
        )

    def test_iam_presentation_does_not_import_extraction(self):
        """IAM presentation should not import from Extraction context."""
        (
            archrule("iam_pres_no_extraction")
            .match("iam.presentation*")
            .should_not_import("extraction*")
            .check("iam")
        )

    def test_iam_presentation_does_not_import_management(self):
        """IAM presentation should not import from Management context."""
        (
            archrule("iam_pres_no_management")
            .match("iam.presentation*")
            .should_not_import("management*")
            .check("iam")
        )

    def test_iam_presentation_does_not_import_ingestion(self):
        """IAM presentation should not import from Ingestion context."""
        (
            archrule("iam_pres_no_ingestion")
            .match("iam.presentation*")
            .should_not_import("ingestion*")
            .check("iam")
        )

    def test_iam_presentation_does_not_import_querying(self):
        """IAM presentation should not import from Querying context."""
        (
            archrule("iam_pres_no_querying")
            .match("iam.presentation*")
            .should_not_import("query*")
            .check("iam")
        )


class TestIAMAllowedDependencies:
    """Tests that IAM can import from its allowed dependencies.

    IAM is allowed to import from:
    - shared_kernel (authorization, outbox, types)
    - infrastructure (settings, database, cross-cutting concerns)
    - Other IAM sub-packages (domain, ports, application, etc.)
    """

    def test_iam_may_import_shared_kernel(self):
        """IAM may import from shared_kernel (authorization, outbox, types)."""
        (
            archrule("iam_may_import_shared_kernel")
            .match("iam*")
            .may_import("shared_kernel*")
            .check("iam")
        )

    def test_iam_may_import_infrastructure(self):
        """IAM may import from infrastructure (settings, database)."""
        (
            archrule("iam_may_import_infrastructure")
            .match("iam*")
            .may_import("infrastructure*")
            .check("iam")
        )
