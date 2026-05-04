"""In-memory fake implementation of AuthorizationProvider.

Provides a fast, self-contained test double for the AuthorizationProvider
protocol. Implements simplified SpiceDB-like permission semantics:

- Stores explicit relationship tuples in memory.
- Computes permissions using a schema-derived relation map (workspace, group, etc.).
- Expands group#member subject relations to resolve transitive membership.

This fake is the preferred collaborator replacement in unit tests.
Integration tests against real SpiceDB are in tests/integration/.

Design follows the Domain-Oriented Observability principle: the probe
is not tested here — it is exercised by DefaultAuthorizationProbe unit tests.
"""

from __future__ import annotations

from typing import NamedTuple

from shared_kernel.authorization.protocols import CheckRequest
from shared_kernel.authorization.types import (
    RelationshipSpec,
    RelationshipTuple,
    SubjectRelation,
)


class _StoredRelationship(NamedTuple):
    """Internal stored relationship tuple."""

    resource: str  # "type:id"
    relation: str  # relation name, e.g. "admin"
    subject: str  # "type:id" or "type:id#relation"


# ---------------------------------------------------------------------------
# Permission computation map
#
# Maps (resource_type, permission) → list of relations that grant the permission.
# Derived from schema.zed.  Omitted resource types fall back to treating the
# permission name as a direct relation (1:1 lookup).
# ---------------------------------------------------------------------------
_PERMISSION_GRANTS: dict[tuple[str, str], list[str]] = {
    # workspace
    ("workspace", "view"): ["admin", "editor", "member"],
    ("workspace", "edit"): ["admin", "editor"],
    ("workspace", "manage"): ["admin"],
    ("workspace", "create_child"): ["admin", "editor"],
    # group
    ("group", "view"): ["admin", "member_relation"],
    ("group", "manage"): ["admin"],
    ("group", "member"): ["admin", "member_relation"],
    # knowledge_graph
    ("knowledge_graph", "view"): ["admin", "editor", "viewer"],
    ("knowledge_graph", "edit"): ["admin", "editor"],
    ("knowledge_graph", "manage"): ["admin"],
    # tenant
    ("tenant", "view"): ["admin", "member"],
    ("tenant", "manage"): ["admin"],
    ("tenant", "administrate"): ["admin"],
    ("tenant", "create_api_key"): ["admin", "member"],
    # api_key
    ("api_key", "view"): ["owner"],
    ("api_key", "revoke"): ["owner"],
}


class InMemoryAuthorizationProvider:
    """In-memory fake implementing the AuthorizationProvider protocol.

    Stores relationships as explicit ``(resource, relation, subject)`` triples.
    Permission computation follows the schema-derived rules in
    ``_PERMISSION_GRANTS`` and expands ``group:<id>#member`` subject relations
    by checking stored group membership.

    Thread-safety: NOT thread-safe. Intended for single-threaded test use only.
    """

    def __init__(self) -> None:
        self._relationships: list[_StoredRelationship] = []

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_resource_type(resource: str) -> str:
        """Extract the type prefix from 'type:id'."""
        return resource.split(":", 1)[0]

    @staticmethod
    def _parse_resource_id(resource: str) -> str:
        """Extract the ID from 'type:id'."""
        return resource.split(":", 1)[1]

    def _is_group_member(self, group_id: str, user_subject: str) -> bool:
        """Return True if user_subject has admin or member_relation in group:group_id.

        In the SpiceDB schema, ``group.member = admin + member_relation``.
        Both roles make a user a group member for the purpose of expanding
        ``group:<id>#member`` subject references.
        """
        group_resource = f"group:{group_id}"
        for rel in self._relationships:
            if (
                rel.resource == group_resource
                and rel.relation in ("admin", "member_relation")
                and rel.subject == user_subject
            ):
                return True
        return False

    def _check_direct_or_group(
        self,
        resource: str,
        relation: str,
        subject: str,
    ) -> bool:
        """Check if (resource, relation, subject) is granted directly or via group expansion."""
        for rel in self._relationships:
            if rel.resource != resource or rel.relation != relation:
                continue

            # Direct match
            if rel.subject == subject:
                return True

            # Group#member expansion: subject_str == "group:<id>#member"
            if rel.subject.startswith("group:") and rel.subject.endswith("#member"):
                group_id = rel.subject[len("group:") : -len("#member")]
                if self._is_group_member(group_id, subject):
                    return True

        return False

    def _matches_filter(
        self,
        rel: _StoredRelationship,
        resource_type: str,
        resource_id: str | None,
        relation: str | None,
        subject_type: str | None,
        subject_id: str | None,
    ) -> bool:
        """Return True if the stored relationship matches all specified filter criteria."""
        stored_resource_type = self._parse_resource_type(rel.resource)
        if stored_resource_type != resource_type:
            return False
        if (
            resource_id is not None
            and self._parse_resource_id(rel.resource) != resource_id
        ):
            return False
        if relation is not None and rel.relation != relation:
            return False
        if subject_type is not None:
            stored_subject_type = (
                rel.subject.split(":", 1)[0] if ":" in rel.subject else ""
            )
            if stored_subject_type != subject_type:
                return False
        if subject_id is not None:
            # Extract id portion from "type:id" or "type:id#relation"
            raw_id_part = (
                rel.subject.split(":", 1)[1] if ":" in rel.subject else rel.subject
            )
            stored_id = raw_id_part.split("#", 1)[0]
            if stored_id != subject_id:
                return False
        return True

    # ------------------------------------------------------------------
    # AuthorizationProvider protocol implementation
    # ------------------------------------------------------------------

    async def write_relationship(
        self,
        resource: str,
        relation: str,
        subject: str,
    ) -> None:
        """Store a relationship tuple (idempotent — duplicates are not inserted)."""
        entry = _StoredRelationship(
            resource=resource, relation=relation, subject=subject
        )
        if entry not in self._relationships:
            self._relationships.append(entry)

    async def write_relationships(
        self,
        relationships: list[RelationshipSpec],
    ) -> None:
        """Store multiple relationship tuples atomically."""
        for rel in relationships:
            await self.write_relationship(rel.resource, rel.relation, rel.subject)

    async def check_permission(
        self,
        resource: str,
        permission: str,
        subject: str,
    ) -> bool:
        """Check if a subject has a permission on a resource.

        Uses the schema-derived permission → relation map.  Falls back to
        treating the permission name as a direct relation when no mapping exists.
        """
        resource_type = self._parse_resource_type(resource)
        key = (resource_type, permission)
        granting_relations = _PERMISSION_GRANTS.get(key, [permission])

        for granting_relation in granting_relations:
            if self._check_direct_or_group(resource, granting_relation, subject):
                return True
        return False

    async def bulk_check_permission(
        self,
        requests: list[CheckRequest],
    ) -> set[str]:
        """Return the set of resource identifiers that passed permission checks."""
        permitted: set[str] = set()
        for req in requests:
            if await self.check_permission(req.resource, req.permission, req.subject):
                permitted.add(req.resource)
        return permitted

    async def delete_relationship(
        self,
        resource: str,
        relation: str,
        subject: str,
    ) -> None:
        """Remove a specific relationship tuple."""
        entry = _StoredRelationship(
            resource=resource, relation=relation, subject=subject
        )
        self._relationships = [r for r in self._relationships if r != entry]

    async def delete_relationships(
        self,
        relationships: list[RelationshipSpec],
    ) -> None:
        """Remove multiple relationship tuples."""
        to_remove = {
            _StoredRelationship(r.resource, r.relation, r.subject)
            for r in relationships
        }
        self._relationships = [r for r in self._relationships if r not in to_remove]

    async def delete_relationships_by_filter(
        self,
        resource_type: str,
        resource_id: str | None = None,
        relation: str | None = None,
        subject_type: str | None = None,
        subject_id: str | None = None,
    ) -> None:
        """Remove all relationships matching the filter criteria.

        Raises:
            ValueError: If no filter parameter beyond resource_type is provided.
            ValueError: If subject_id is provided without subject_type.
        """
        if not any([resource_id, relation, subject_type, subject_id]):
            raise ValueError(
                "At least one filter parameter beyond resource_type must be specified"
            )
        if subject_id and not subject_type:
            raise ValueError(
                "subject_type must be provided when subject_id is specified"
            )

        self._relationships = [
            r
            for r in self._relationships
            if not self._matches_filter(
                r, resource_type, resource_id, relation, subject_type, subject_id
            )
        ]

    async def lookup_subjects(
        self,
        resource: str,
        relation: str,
        subject_type: str,
        optional_subject_relation: str | None = None,
    ) -> list[SubjectRelation]:
        """Find all subjects with an explicit relationship to a resource.

        Returns subjects whose stored subject string starts with ``subject_type:``.
        Does not expand computed permissions.
        """
        results: list[SubjectRelation] = []
        seen: set[str] = set()

        for rel in self._relationships:
            if rel.resource != resource or rel.relation != relation:
                continue

            # Filter by subject_type prefix
            if not rel.subject.startswith(f"{subject_type}:"):
                continue

            # Extract subject id (strip type prefix, optional #relation suffix)
            id_part = rel.subject[len(subject_type) + 1 :]
            subject_id = id_part.split("#", 1)[0]

            if subject_id in seen:
                continue
            seen.add(subject_id)

            results.append(
                SubjectRelation(
                    subject_id=subject_id,
                    relation=optional_subject_relation or relation,
                )
            )

        return results

    async def lookup_resources(
        self,
        resource_type: str,
        permission: str,
        subject: str,
    ) -> list[str]:
        """Find all resources of a type that a subject has a permission on.

        Returns resource IDs (without type prefix).
        """
        found: list[str] = []
        seen: set[str] = set()

        key = (resource_type, permission)
        granting_relations = _PERMISSION_GRANTS.get(key, [permission])

        for rel in self._relationships:
            if self._parse_resource_type(rel.resource) != resource_type:
                continue
            if rel.relation not in granting_relations:
                continue

            resource_id = self._parse_resource_id(rel.resource)

            # Direct match
            granted = False
            if rel.subject == subject:
                granted = True
            # Group#member expansion
            elif rel.subject.startswith("group:") and rel.subject.endswith("#member"):
                group_id = rel.subject[len("group:") : -len("#member")]
                if self._is_group_member(group_id, subject):
                    granted = True

            if granted and resource_id not in seen:
                seen.add(resource_id)
                found.append(resource_id)

        return found

    async def read_relationships(
        self,
        resource_type: str,
        resource_id: str | None = None,
        relation: str | None = None,
        subject_type: str | None = None,
        subject_id: str | None = None,
    ) -> list[RelationshipTuple]:
        """Return only the explicitly-stored relationship tuples matching the filter.

        Unlike check_permission / lookup_resources, this does NOT expand computed
        permissions. It returns raw stored tuples only.

        Raises:
            ValueError: If subject_id is provided without subject_type.
        """
        if subject_id and not subject_type:
            raise ValueError(
                "subject_type must be provided when subject_id is specified"
            )

        return [
            RelationshipTuple(
                resource=r.resource,
                relation=r.relation,
                subject=r.subject,
            )
            for r in self._relationships
            if self._matches_filter(
                r, resource_type, resource_id, relation, subject_type, subject_id
            )
        ]
