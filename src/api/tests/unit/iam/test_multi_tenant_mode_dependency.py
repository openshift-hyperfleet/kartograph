"""Unit tests for require_multi_tenant_mode dependency.

Tests the FastAPI dependency that gates tenant management routes
behind multi-tenant mode. In single-tenant mode, creating and
deleting tenants should be forbidden (403). In multi-tenant mode,
the request should pass through.
"""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from iam.dependencies.multi_tenant_mode import require_multi_tenant_mode


class TestRequireMultiTenantMode:
    """Tests for the require_multi_tenant_mode dependency function."""

    def test_raises_403_in_single_tenant_mode(self) -> None:
        """Should raise HTTPException 403 when single_tenant_mode is True."""
        with pytest.raises(HTTPException) as exc_info:
            require_multi_tenant_mode(single_tenant_mode=True)

        assert exc_info.value.status_code == 403
        assert exc_info.value.detail == (
            "Tenant management is disabled in single-tenant mode"
        )

    def test_allows_request_in_multi_tenant_mode(self) -> None:
        """Should not raise when single_tenant_mode is False."""
        # Should complete without raising HTTPException
        require_multi_tenant_mode(single_tenant_mode=False)

    def test_error_detail_mentions_single_tenant_mode(self) -> None:
        """Error message should clearly indicate the reason for rejection."""
        with pytest.raises(HTTPException) as exc_info:
            require_multi_tenant_mode(single_tenant_mode=True)

        assert "single-tenant" in exc_info.value.detail.lower()
