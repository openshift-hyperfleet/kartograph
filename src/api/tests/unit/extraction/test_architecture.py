"""Architecture tests for the Extraction bounded context."""

import importlib

import pytest
from pytest_archon import archrule


def _subpackage_exists(name: str) -> bool:
    """Return True when package exists, False when missing."""
    try:
        importlib.import_module(name)
        return True
    except ModuleNotFoundError as e:
        if e.name == name:
            return False
        raise


_has_domain = _subpackage_exists("extraction.domain")
_has_ports = _subpackage_exists("extraction.ports")
_has_application = _subpackage_exists("extraction.application")
_has_infrastructure = _subpackage_exists("extraction.infrastructure")
_has_presentation = _subpackage_exists("extraction.presentation")

_skip_no_domain = pytest.mark.skipif(
    not _has_domain,
    reason="extraction.domain subpackage does not exist yet",
)
_skip_no_ports = pytest.mark.skipif(
    not _has_ports,
    reason="extraction.ports subpackage does not exist yet",
)
_skip_no_application = pytest.mark.skipif(
    not _has_application,
    reason="extraction.application subpackage does not exist yet",
)
_skip_no_infrastructure = pytest.mark.skipif(
    not _has_infrastructure,
    reason="extraction.infrastructure subpackage does not exist yet",
)
_skip_no_presentation = pytest.mark.skipif(
    not _has_presentation,
    reason="extraction.presentation subpackage does not exist yet",
)


@_skip_no_domain
class TestExtractionDomainLayerBoundaries:
    def test_domain_does_not_import_infrastructure(self):
        (
            archrule("extraction_domain_no_infrastructure")
            .match("extraction.domain*")
            .should_not_import("extraction.infrastructure*")
            .check("extraction")
        )

    def test_domain_does_not_import_application(self):
        (
            archrule("extraction_domain_no_application")
            .match("extraction.domain*")
            .should_not_import("extraction.application*")
            .check("extraction")
        )

    def test_domain_does_not_import_fastapi(self):
        (
            archrule("extraction_domain_no_fastapi")
            .match("extraction.domain*")
            .should_not_import("fastapi*", "starlette*")
            .check("extraction")
        )


@_skip_no_ports
class TestExtractionPortsLayerBoundaries:
    def test_ports_does_not_import_infrastructure(self):
        (
            archrule("extraction_ports_no_infrastructure")
            .match("extraction.ports*")
            .should_not_import("extraction.infrastructure*")
            .check("extraction")
        )

    def test_ports_does_not_import_application(self):
        (
            archrule("extraction_ports_no_application")
            .match("extraction.ports*")
            .should_not_import("extraction.application*")
            .check("extraction")
        )


@_skip_no_application
class TestExtractionApplicationLayerBoundaries:
    def test_application_does_not_import_infrastructure(self):
        (
            archrule("extraction_application_no_infrastructure")
            .match("extraction.application*")
            .should_not_import("extraction.infrastructure*")
            .check("extraction")
        )

    def test_application_may_import_domain_and_ports(self):
        (
            archrule("extraction_application_may_import_domain_ports")
            .match("extraction.application*")
            .may_import("extraction.domain*", "extraction.ports*")
            .check("extraction")
        )


@_skip_no_infrastructure
class TestExtractionInfrastructureLayerBoundaries:
    def test_infrastructure_does_not_import_application(self):
        (
            archrule("extraction_infrastructure_no_application")
            .match("extraction.infrastructure*")
            .should_not_import("extraction.application*")
            .check("extraction")
        )

    def test_infrastructure_may_import_domain_and_ports(self):
        (
            archrule("extraction_infrastructure_may_import_domain_ports")
            .match("extraction.infrastructure*")
            .may_import("extraction.domain*", "extraction.ports*")
            .check("extraction")
        )


@_skip_no_presentation
class TestExtractionPresentationLayerBoundaries:
    def test_presentation_does_not_import_other_contexts(self):
        (
            archrule("extraction_presentation_no_cross_context_imports")
            .match("extraction.presentation*")
            .should_not_import("graph*", "management*", "ingestion*", "query*")
            .check("extraction")
        )


class TestExtractionBoundedContextIsolation:
    def test_extraction_does_not_import_iam(self):
        (
            archrule("extraction_inner_no_iam")
            .match(
                "extraction.domain*",
                "extraction.ports*",
                "extraction.application*",
                "extraction.infrastructure*",
            )
            .should_not_import("iam*")
            .check("extraction")
        )

    def test_extraction_does_not_import_management(self):
        (
            archrule("extraction_no_management")
            .match("extraction*")
            .should_not_import("management*")
            .check("extraction")
        )

    def test_extraction_does_not_import_ingestion(self):
        (
            archrule("extraction_no_ingestion")
            .match("extraction*")
            .should_not_import("ingestion*")
            .check("extraction")
        )

    def test_extraction_does_not_import_graph(self):
        (
            archrule("extraction_no_graph")
            .match("extraction*")
            .should_not_import("graph*")
            .check("extraction")
        )

    def test_extraction_does_not_import_query(self):
        (
            archrule("extraction_no_query")
            .match("extraction*")
            .should_not_import("query*")
            .check("extraction")
        )


class TestExtractionAllowedDependencies:
    def test_extraction_may_import_shared_kernel(self):
        (
            archrule("extraction_may_import_shared_kernel")
            .match("extraction*")
            .may_import("shared_kernel*")
            .check("extraction")
        )

    def test_extraction_may_import_infrastructure(self):
        (
            archrule("extraction_may_import_infrastructure")
            .match("extraction*")
            .may_import("infrastructure*")
            .check("extraction")
        )

