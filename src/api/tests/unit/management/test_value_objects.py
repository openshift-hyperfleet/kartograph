"""Unit tests for Management domain value objects."""

from __future__ import annotations

import pytest
from ulid import ULID

from management.domain.exceptions import InvalidScheduleError
from management.domain.value_objects import (
    BaseId,
    DataSourceId,
    KnowledgeGraphId,
    Ontology,
    OntologyEdgeType,
    OntologyNodeType,
    Schedule,
    ScheduleType,
)


class TestKnowledgeGraphId:
    """Tests for KnowledgeGraphId value object."""

    def test_generate_creates_valid_ulid(self):
        """generate() should produce a valid ULID string."""
        kg_id = KnowledgeGraphId.generate()
        assert isinstance(kg_id.value, str)
        # Should not raise
        ULID.from_str(kg_id.value)

    def test_generate_creates_unique_ids(self):
        """Each call to generate() should produce a unique ID."""
        ids = {KnowledgeGraphId.generate().value for _ in range(100)}
        assert len(ids) == 100

    def test_from_string_roundtrips(self):
        """from_string(id.value) should reconstruct the same ID."""
        original = KnowledgeGraphId.generate()
        restored = KnowledgeGraphId.from_string(original.value)
        assert restored == original
        assert restored.value == original.value

    def test_from_string_rejects_invalid_ulid(self):
        """from_string() should raise ValueError for non-ULID strings."""
        with pytest.raises(ValueError, match="Invalid KnowledgeGraphId"):
            KnowledgeGraphId.from_string("not-a-ulid")

    def test_str_returns_value(self):
        """str() should return the raw ULID string."""
        kg_id = KnowledgeGraphId.generate()
        assert str(kg_id) == kg_id.value

    def test_is_frozen(self):
        """KnowledgeGraphId should be immutable."""
        kg_id = KnowledgeGraphId.generate()
        with pytest.raises(AttributeError):
            kg_id.value = "something"

    def test_equality_by_value(self):
        """Two IDs with the same value should be equal."""
        value = str(ULID())
        id1 = KnowledgeGraphId(value=value)
        id2 = KnowledgeGraphId(value=value)
        assert id1 == id2

    def test_inequality_different_values(self):
        """Two IDs with different values should not be equal."""
        id1 = KnowledgeGraphId.generate()
        id2 = KnowledgeGraphId.generate()
        assert id1 != id2

    def test_is_subclass_of_base_id(self):
        """KnowledgeGraphId should extend BaseId."""
        assert issubclass(KnowledgeGraphId, BaseId)


class TestDataSourceId:
    """Tests for DataSourceId value object."""

    def test_generate_creates_valid_ulid(self):
        """generate() should produce a valid ULID string."""
        ds_id = DataSourceId.generate()
        assert isinstance(ds_id.value, str)
        ULID.from_str(ds_id.value)

    def test_generate_creates_unique_ids(self):
        """Each call to generate() should produce a unique ID."""
        ids = {DataSourceId.generate().value for _ in range(100)}
        assert len(ids) == 100

    def test_from_string_roundtrips(self):
        """from_string(id.value) should reconstruct the same ID."""
        original = DataSourceId.generate()
        restored = DataSourceId.from_string(original.value)
        assert restored == original

    def test_from_string_rejects_invalid_ulid(self):
        """from_string() should raise ValueError for non-ULID strings."""
        with pytest.raises(ValueError, match="Invalid DataSourceId"):
            DataSourceId.from_string("not-a-ulid")

    def test_str_returns_value(self):
        """str() should return the raw ULID string."""
        ds_id = DataSourceId.generate()
        assert str(ds_id) == ds_id.value

    def test_is_frozen(self):
        """DataSourceId should be immutable."""
        ds_id = DataSourceId.generate()
        with pytest.raises(AttributeError):
            ds_id.value = "something"

    def test_is_subclass_of_base_id(self):
        """DataSourceId should extend BaseId."""
        assert issubclass(DataSourceId, BaseId)


class TestScheduleType:
    """Tests for ScheduleType enum."""

    def test_manual_value(self):
        assert ScheduleType.MANUAL == "manual"
        assert ScheduleType.MANUAL.value == "manual"

    def test_cron_value(self):
        assert ScheduleType.CRON == "cron"
        assert ScheduleType.CRON.value == "cron"

    def test_interval_value(self):
        assert ScheduleType.INTERVAL == "interval"
        assert ScheduleType.INTERVAL.value == "interval"

    def test_is_str_enum(self):
        """ScheduleType members should be usable as strings."""
        assert isinstance(ScheduleType.MANUAL, str)


class TestSchedule:
    """Tests for Schedule value object."""

    def test_manual_schedule_without_value(self):
        """MANUAL schedule with no value should be valid."""
        schedule = Schedule(schedule_type=ScheduleType.MANUAL)
        assert schedule.schedule_type == ScheduleType.MANUAL
        assert schedule.value is None

    def test_cron_schedule_with_value(self):
        """CRON schedule with a cron expression should be valid."""
        schedule = Schedule(schedule_type=ScheduleType.CRON, value="0 * * * *")
        assert schedule.schedule_type == ScheduleType.CRON
        assert schedule.value == "0 * * * *"

    def test_interval_schedule_with_value(self):
        """INTERVAL schedule with an interval expression should be valid."""
        schedule = Schedule(schedule_type=ScheduleType.INTERVAL, value="PT1H")
        assert schedule.schedule_type == ScheduleType.INTERVAL
        assert schedule.value == "PT1H"

    def test_cron_schedule_without_value_raises(self):
        """CRON schedule without a value should raise InvalidScheduleError."""
        with pytest.raises(
            InvalidScheduleError, match="cron schedule requires a value"
        ):
            Schedule(schedule_type=ScheduleType.CRON)

    def test_cron_schedule_with_empty_string_raises(self):
        """CRON schedule with empty string should raise InvalidScheduleError."""
        with pytest.raises(
            InvalidScheduleError, match="cron schedule requires a value"
        ):
            Schedule(schedule_type=ScheduleType.CRON, value="")

    def test_interval_schedule_without_value_raises(self):
        """INTERVAL schedule without a value should raise InvalidScheduleError."""
        with pytest.raises(
            InvalidScheduleError, match="interval schedule requires a value"
        ):
            Schedule(schedule_type=ScheduleType.INTERVAL)

    def test_interval_schedule_with_empty_string_raises(self):
        """INTERVAL schedule with empty string should raise InvalidScheduleError."""
        with pytest.raises(
            InvalidScheduleError, match="interval schedule requires a value"
        ):
            Schedule(schedule_type=ScheduleType.INTERVAL, value="")

    def test_manual_schedule_with_value_raises(self):
        """MANUAL schedule with a value should raise InvalidScheduleError."""
        with pytest.raises(
            InvalidScheduleError, match="MANUAL schedule must not have a value"
        ):
            Schedule(schedule_type=ScheduleType.MANUAL, value="0 * * * *")

    def test_manual_schedule_with_empty_string_normalizes_to_none(self):
        """MANUAL schedule with empty string should normalize value to None."""
        schedule = Schedule(schedule_type=ScheduleType.MANUAL, value="")
        assert schedule.value is None

    def test_is_frozen(self):
        """Schedule should be immutable."""
        schedule = Schedule(schedule_type=ScheduleType.MANUAL)
        with pytest.raises(AttributeError):
            schedule.schedule_type = ScheduleType.CRON

    def test_equality(self):
        """Two schedules with same type and value should be equal."""
        s1 = Schedule(schedule_type=ScheduleType.CRON, value="0 * * * *")
        s2 = Schedule(schedule_type=ScheduleType.CRON, value="0 * * * *")
        assert s1 == s2

    def test_inequality_different_type(self):
        """Schedules with different types should not be equal."""
        s1 = Schedule(schedule_type=ScheduleType.MANUAL)
        s2 = Schedule(schedule_type=ScheduleType.CRON, value="0 * * * *")
        assert s1 != s2


class TestOntologyNodeType:
    """Tests for OntologyNodeType value object."""

    def test_create_with_label_only(self) -> None:
        """OntologyNodeType with only a label should be valid."""
        node_type = OntologyNodeType(label="Repository")
        assert node_type.label == "Repository"
        assert node_type.description is None
        assert node_type.required_properties == []
        assert node_type.optional_properties == []

    def test_create_with_all_fields(self) -> None:
        """OntologyNodeType with all fields should store them correctly."""
        node_type = OntologyNodeType(
            label="PullRequest",
            description="A GitHub pull request",
            required_properties=["title", "number"],
            optional_properties=["body", "merged_at"],
        )
        assert node_type.label == "PullRequest"
        assert node_type.description == "A GitHub pull request"
        assert node_type.required_properties == ["title", "number"]
        assert node_type.optional_properties == ["body", "merged_at"]

    def test_equality_by_value(self) -> None:
        """Two OntologyNodeType instances with same values should be equal."""
        n1 = OntologyNodeType(
            label="Issue",
            required_properties=["title"],
        )
        n2 = OntologyNodeType(
            label="Issue",
            required_properties=["title"],
        )
        assert n1 == n2

    def test_inequality_different_label(self) -> None:
        """OntologyNodeType instances with different labels should not be equal."""
        n1 = OntologyNodeType(label="Issue")
        n2 = OntologyNodeType(label="PullRequest")
        assert n1 != n2

    def test_is_frozen(self) -> None:
        """OntologyNodeType should be immutable (frozen dataclass)."""
        node_type = OntologyNodeType(label="Repo")
        with pytest.raises((AttributeError, TypeError)):
            node_type.label = "changed"  # type: ignore[misc]

    def test_required_properties_defaults_to_empty_list(self) -> None:
        """required_properties should default to empty list, not None."""
        node_type = OntologyNodeType(label="Commit")
        assert isinstance(node_type.required_properties, list)
        assert node_type.required_properties == []

    def test_optional_properties_defaults_to_empty_list(self) -> None:
        """optional_properties should default to empty list, not None."""
        node_type = OntologyNodeType(label="Commit")
        assert isinstance(node_type.optional_properties, list)
        assert node_type.optional_properties == []


class TestOntologyEdgeType:
    """Tests for OntologyEdgeType value object."""

    def test_create_with_label_from_to(self) -> None:
        """OntologyEdgeType with label, from_type, to_type should be valid."""
        edge_type = OntologyEdgeType(
            label="CREATED_BY",
            from_type="PullRequest",
            to_type="User",
        )
        assert edge_type.label == "CREATED_BY"
        assert edge_type.from_type == "PullRequest"
        assert edge_type.to_type == "User"
        assert edge_type.description is None
        assert edge_type.required_properties == []
        assert edge_type.optional_properties == []

    def test_create_with_all_fields(self) -> None:
        """OntologyEdgeType with all fields should store them correctly."""
        edge_type = OntologyEdgeType(
            label="HAS_ISSUE",
            from_type="Repository",
            to_type="Issue",
            description="A repository contains issues",
            required_properties=["created_at"],
            optional_properties=["closed_at"],
        )
        assert edge_type.description == "A repository contains issues"
        assert edge_type.required_properties == ["created_at"]
        assert edge_type.optional_properties == ["closed_at"]

    def test_equality_by_value(self) -> None:
        """Two OntologyEdgeType instances with same values should be equal."""
        e1 = OntologyEdgeType(
            label="HAS_COMMIT",
            from_type="PullRequest",
            to_type="Commit",
        )
        e2 = OntologyEdgeType(
            label="HAS_COMMIT",
            from_type="PullRequest",
            to_type="Commit",
        )
        assert e1 == e2

    def test_inequality_different_label(self) -> None:
        """OntologyEdgeType instances with different labels should not be equal."""
        e1 = OntologyEdgeType(label="CREATED_BY", from_type="PR", to_type="User")
        e2 = OntologyEdgeType(label="ASSIGNED_TO", from_type="PR", to_type="User")
        assert e1 != e2

    def test_is_frozen(self) -> None:
        """OntologyEdgeType should be immutable (frozen dataclass)."""
        edge_type = OntologyEdgeType(label="HAS", from_type="A", to_type="B")
        with pytest.raises((AttributeError, TypeError)):
            edge_type.label = "changed"  # type: ignore[misc]


class TestOntology:
    """Tests for Ontology value object."""

    def test_empty_ontology_is_valid(self) -> None:
        """Ontology with no types is valid (empty = no approval yet)."""
        ontology = Ontology(node_types=[], edge_types=[])
        assert ontology.node_types == []
        assert ontology.edge_types == []

    def test_ontology_with_node_and_edge_types(self) -> None:
        """Ontology stores node_types and edge_types correctly."""
        node_types = [
            OntologyNodeType(label="Repository"),
            OntologyNodeType(label="PullRequest"),
        ]
        edge_types = [
            OntologyEdgeType(
                label="HAS_PR", from_type="Repository", to_type="PullRequest"
            ),
        ]
        ontology = Ontology(node_types=node_types, edge_types=edge_types)
        assert len(ontology.node_types) == 2
        assert len(ontology.edge_types) == 1
        assert ontology.node_types[0].label == "Repository"
        assert ontology.edge_types[0].label == "HAS_PR"

    def test_equality_by_value(self) -> None:
        """Two Ontology instances with same contents should be equal."""
        node = OntologyNodeType(label="Issue")
        o1 = Ontology(node_types=[node], edge_types=[])
        o2 = Ontology(node_types=[node], edge_types=[])
        assert o1 == o2

    def test_inequality_different_node_types(self) -> None:
        """Ontology instances with different node types should not be equal."""
        o1 = Ontology(node_types=[OntologyNodeType(label="A")], edge_types=[])
        o2 = Ontology(node_types=[OntologyNodeType(label="B")], edge_types=[])
        assert o1 != o2

    def test_is_frozen(self) -> None:
        """Ontology should be immutable."""
        ontology = Ontology(node_types=[], edge_types=[])
        with pytest.raises((AttributeError, TypeError)):
            ontology.node_types = []  # type: ignore[misc]

    def test_to_dict_serializes_correctly(self) -> None:
        """to_dict() should produce a JSON-serializable dictionary."""
        ontology = Ontology(
            node_types=[
                OntologyNodeType(
                    label="Repository",
                    description="A code repository",
                    required_properties=["url"],
                    optional_properties=["description"],
                )
            ],
            edge_types=[
                OntologyEdgeType(
                    label="HAS_PR",
                    from_type="Repository",
                    to_type="PullRequest",
                )
            ],
        )
        result = ontology.to_dict()
        assert isinstance(result, dict)
        assert "node_types" in result
        assert "edge_types" in result
        assert result["node_types"][0]["label"] == "Repository"
        assert result["node_types"][0]["description"] == "A code repository"
        assert result["node_types"][0]["required_properties"] == ["url"]
        assert result["edge_types"][0]["label"] == "HAS_PR"
        assert result["edge_types"][0]["from_type"] == "Repository"

    def test_from_dict_deserializes_correctly(self) -> None:
        """from_dict() should reconstruct an Ontology from a dictionary."""
        data = {
            "node_types": [
                {
                    "label": "Issue",
                    "description": "A GitHub issue",
                    "required_properties": ["title"],
                    "optional_properties": ["body"],
                }
            ],
            "edge_types": [
                {
                    "label": "CREATED_BY",
                    "from_type": "Issue",
                    "to_type": "User",
                    "description": None,
                    "required_properties": [],
                    "optional_properties": [],
                }
            ],
        }
        ontology = Ontology.from_dict(data)
        assert len(ontology.node_types) == 1
        assert ontology.node_types[0].label == "Issue"
        assert ontology.node_types[0].description == "A GitHub issue"
        assert ontology.node_types[0].required_properties == ["title"]
        assert len(ontology.edge_types) == 1
        assert ontology.edge_types[0].label == "CREATED_BY"

    def test_roundtrip_serialization(self) -> None:
        """to_dict() → from_dict() should reconstruct the same Ontology."""
        original = Ontology(
            node_types=[
                OntologyNodeType(
                    label="Commit",
                    description="A git commit",
                    required_properties=["sha"],
                    optional_properties=["message"],
                )
            ],
            edge_types=[
                OntologyEdgeType(
                    label="AUTHORED_BY",
                    from_type="Commit",
                    to_type="User",
                )
            ],
        )
        restored = Ontology.from_dict(original.to_dict())
        assert restored == original
