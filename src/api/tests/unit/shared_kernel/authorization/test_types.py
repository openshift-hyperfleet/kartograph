"""Unit tests for authorization types and utilities."""

from shared_kernel.authorization.types import (
    Permission,
    RelationType,
    ResourceType,
    format_resource,
    format_subject,
)


class TestResourceType:
    """Tests for ResourceType enum."""

    def test_has_user_type(self):
        """Test that USER resource type exists."""
        assert ResourceType.USER == "user"

    def test_has_group_type(self):
        """Test that GROUP resource type exists."""
        assert ResourceType.GROUP == "group"

    def test_has_workspace_type(self):
        """Test that WORKSPACE resource type exists."""
        assert ResourceType.WORKSPACE == "workspace"

    def test_has_tenant_type(self):
        """Test that TENANT resource type exists."""
        assert ResourceType.TENANT == "tenant"

    def test_resource_types_are_lowercase(self):
        """Test that all resource types are lowercase strings."""
        for resource_type in ResourceType:
            assert resource_type.islower()
            assert isinstance(resource_type, str)


class TestRelationType:
    """Tests for RelationType enum."""

    def test_has_member_relation(self):
        """Test that MEMBER relation exists."""
        assert RelationType.MEMBER == "member"

    def test_has_owner_relation(self):
        """Test that OWNER relation exists."""
        assert RelationType.OWNER == "owner"

    def test_has_admin_relation(self):
        """Test that ADMIN relation exists."""
        assert RelationType.ADMIN == "admin"

    def test_has_parent_relation(self):
        """Test that PARENT relation exists."""
        assert RelationType.PARENT == "parent"

    def test_has_workspace_relation(self):
        """Test that WORKSPACE relation exists."""
        assert RelationType.WORKSPACE == "workspace"

    def test_relation_types_are_lowercase(self):
        """Test that all relation types are lowercase strings."""
        for relation_type in RelationType:
            assert relation_type.islower()
            assert isinstance(relation_type, str)


class TestPermission:
    """Tests for Permission enum."""

    def test_has_view_permission(self):
        """Test that VIEW permission exists."""
        assert Permission.VIEW == "view"

    def test_has_edit_permission(self):
        """Test that EDIT permission exists."""
        assert Permission.EDIT == "edit"

    def test_has_delete_permission(self):
        """Test that DELETE permission exists."""
        assert Permission.DELETE == "delete"

    def test_has_manage_permission(self):
        """Test that MANAGE permission exists."""
        assert Permission.MANAGE == "manage"

    def test_permissions_are_lowercase(self):
        """Test that all permissions are lowercase strings."""
        for permission in Permission:
            assert permission.islower()
            assert isinstance(permission, str)


class TestFormatResource:
    """Tests for format_resource utility function."""

    def test_formats_group_resource(self):
        """Test formatting a group resource identifier."""
        result = format_resource(ResourceType.GROUP, "abc123")
        assert result == "group:abc123"

    def test_formats_user_resource(self):
        """Test formatting a user resource identifier."""
        result = format_resource(ResourceType.USER, "alice")
        assert result == "user:alice"

    def test_formats_workspace_resource(self):
        """Test formatting a workspace resource identifier."""
        result = format_resource(ResourceType.WORKSPACE, "ws-xyz")
        assert result == "workspace:ws-xyz"

    def test_formats_with_ulid(self):
        """Test formatting with ULID identifier."""
        ulid = "01ARZ3NDEKTSV4RRFFQ69G5FAV"
        result = format_resource(ResourceType.GROUP, ulid)
        assert result == f"group:{ulid}"

    def test_preserves_resource_id_case(self):
        """Test that resource ID case is preserved."""
        result = format_resource(ResourceType.GROUP, "MixedCase123")
        assert result == "group:MixedCase123"


class TestFormatSubject:
    """Tests for format_subject utility function."""

    def test_formats_user_subject(self):
        """Test formatting a user subject identifier."""
        result = format_subject(ResourceType.USER, "alice")
        assert result == "user:alice"

    def test_formats_group_subject(self):
        """Test formatting a group subject identifier."""
        result = format_subject(ResourceType.GROUP, "admins")
        assert result == "group:admins"

    def test_formats_with_ulid(self):
        """Test formatting subject with ULID identifier."""
        ulid = "01ARZ3NDEKTSV4RRFFQ69G5FAV"
        result = format_subject(ResourceType.USER, ulid)
        assert result == f"user:{ulid}"

    def test_preserves_subject_id_case(self):
        """Test that subject ID case is preserved."""
        result = format_subject(ResourceType.USER, "AliceSmith")
        assert result == "user:AliceSmith"
