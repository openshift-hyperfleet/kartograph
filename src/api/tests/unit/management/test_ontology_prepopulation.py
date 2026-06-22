"""Unit tests for ontology prepopulation rules."""

from __future__ import annotations

import pytest

from management.domain.ontology_prepopulation import (
    PrepopulationValidationError,
    relationship_readiness_key,
    validate_ontology_prepopulation,
)
from management.domain.value_objects import (
    EdgeTypeDefinition,
    NodeTypeDefinition,
    OntologyConfig,
)


def _bootstrap_ontology(
    *,
    nodes: tuple[NodeTypeDefinition, ...] = (),
    edges: tuple[EdgeTypeDefinition, ...] = (),
) -> OntologyConfig:
    return OntologyConfig(node_types=nodes, edge_types=edges)


class TestValidateOntologyPrepopulation:
    def test_allows_prepopulated_relationship_when_endpoints_are_prepopulated(
        self,
    ) -> None:
        config = _bootstrap_ontology(
            nodes=(
                NodeTypeDefinition(label="test", prepopulated=True),
                NodeTypeDefinition(label="api_endpoint", prepopulated=True),
            ),
            edges=(
                EdgeTypeDefinition(
                    label="contains",
                    source_labels=("test",),
                    target_labels=("api_endpoint",),
                    prepopulated=True,
                ),
            ),
        )

        validate_ontology_prepopulation(config)

    def test_rejects_prepopulated_relationship_when_source_not_prepopulated(
        self,
    ) -> None:
        config = _bootstrap_ontology(
            nodes=(
                NodeTypeDefinition(label="test", prepopulated=False),
                NodeTypeDefinition(label="api_endpoint", prepopulated=True),
            ),
            edges=(
                EdgeTypeDefinition(
                    label="contains",
                    source_labels=("test",),
                    target_labels=("api_endpoint",),
                    prepopulated=True,
                ),
            ),
        )

        with pytest.raises(
            PrepopulationValidationError, match="source entity type `test`"
        ):
            validate_ontology_prepopulation(config)

    def test_rejects_prepopulated_relationship_when_target_not_prepopulated(
        self,
    ) -> None:
        config = _bootstrap_ontology(
            nodes=(
                NodeTypeDefinition(label="test", prepopulated=True),
                NodeTypeDefinition(label="api_endpoint", prepopulated=False),
            ),
            edges=(
                EdgeTypeDefinition(
                    label="contains",
                    source_labels=("test",),
                    target_labels=("api_endpoint",),
                    prepopulated=True,
                ),
            ),
        )

        with pytest.raises(
            PrepopulationValidationError, match="target entity type `api_endpoint`"
        ):
            validate_ontology_prepopulation(config)

    def test_rejects_prepopulated_relationship_when_endpoint_type_missing(self) -> None:
        config = _bootstrap_ontology(
            nodes=(NodeTypeDefinition(label="api_endpoint", prepopulated=True),),
            edges=(
                EdgeTypeDefinition(
                    label="contains",
                    source_labels=("test",),
                    target_labels=("api_endpoint",),
                    prepopulated=True,
                ),
            ),
        )

        with pytest.raises(
            PrepopulationValidationError, match="source entity type `test`"
        ):
            validate_ontology_prepopulation(config)


class TestRelationshipReadinessKey:
    def test_builds_design_artifacts_style_key(self) -> None:
        edge = EdgeTypeDefinition(
            label="contains",
            source_labels=("test",),
            target_labels=("api_endpoint",),
        )

        assert relationship_readiness_key(edge) == "test|contains|api_endpoint"
