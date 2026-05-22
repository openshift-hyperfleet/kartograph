"""Unit tests for ontology to DEFINE mutation conversion."""

from __future__ import annotations

from infrastructure.canonical_schema.ontology_mutation_builder import (
    ontology_config_to_define_operations,
)
from management.domain.value_objects import (
    EdgeTypeDefinition,
    NodeTypeDefinition,
    OntologyConfig,
)


class TestOntologyConfigToDefineOperations:
    def test_converts_node_and_edge_types(self):
        config = OntologyConfig(
            node_types=(NodeTypeDefinition(label="Repository", description="Repo"),),
            edge_types=(
                EdgeTypeDefinition(
                    label="CONTAINS",
                    description="Contains relationship",
                    source_labels=("Repository",),
                    target_labels=("Repository",),
                    properties=("weight",),
                ),
            ),
        )

        operations = ontology_config_to_define_operations(config)

        assert len(operations) == 2
        node_op = operations[0]
        edge_op = operations[1]
        assert node_op.op == "DEFINE"
        assert node_op.type == "node"
        assert node_op.label == "Repository"
        assert node_op.description == "Repo"
        assert edge_op.op == "DEFINE"
        assert edge_op.type == "edge"
        assert edge_op.label == "CONTAINS"
        assert edge_op.required_properties == {"weight"}
