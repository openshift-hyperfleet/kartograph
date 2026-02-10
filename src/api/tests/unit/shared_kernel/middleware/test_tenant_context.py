"""Unit tests for the TenantContext shared value object and TenantContextProbe.

Tests the pure value object from the shared kernel and the domain probe
protocol + default implementation.
"""

from __future__ import annotations

import pytest

from shared_kernel.middleware.tenant_context import TenantContext
from shared_kernel.middleware.observability.tenant_context_probe import (
    DefaultTenantContextProbe,
)


class TestTenantContext:
    """Tests for the TenantContext value object."""

    def test_tenant_context_is_immutable(self) -> None:
        """TenantContext should be a frozen dataclass."""
        context = TenantContext(
            tenant_id="01ARZ3NDEKTSV4RRFFQ69G5FAV",
            source="header",
        )
        with pytest.raises(AttributeError):
            context.tenant_id = "something-else"  # type: ignore[misc]

    def test_tenant_context_stores_source_header(self) -> None:
        """TenantContext should store 'header' source."""
        context = TenantContext(
            tenant_id="01ARZ3NDEKTSV4RRFFQ69G5FAV",
            source="header",
        )
        assert context.source == "header"
        assert context.tenant_id == "01ARZ3NDEKTSV4RRFFQ69G5FAV"

    def test_tenant_context_stores_source_default(self) -> None:
        """TenantContext should store 'default' source for auto-selected tenants."""
        context = TenantContext(
            tenant_id="01ARZ3NDEKTSV4RRFFQ69G5FAV",
            source="default",
        )
        assert context.source == "default"

    def test_tenant_context_equality(self) -> None:
        """Two TenantContext instances with same values should be equal."""
        a = TenantContext(tenant_id="abc", source="header")
        b = TenantContext(tenant_id="abc", source="header")
        assert a == b

    def test_tenant_context_inequality(self) -> None:
        """Two TenantContext instances with different values should not be equal."""
        a = TenantContext(tenant_id="abc", source="header")
        b = TenantContext(tenant_id="abc", source="default")
        assert a != b


class TestDefaultTenantContextProbe:
    """Tests for the DefaultTenantContextProbe implementation."""

    def test_implements_protocol(self) -> None:
        """DefaultTenantContextProbe should implement TenantContextProbe protocol."""
        probe = DefaultTenantContextProbe()
        # Verify all protocol methods are callable
        assert callable(probe.tenant_resolved_from_header)
        assert callable(probe.tenant_resolved_from_default)
        assert callable(probe.tenant_header_missing)
        assert callable(probe.invalid_tenant_id_format)
        assert callable(probe.tenant_access_denied)
        assert callable(probe.tenant_authz_check_failed)
        assert callable(probe.default_tenant_not_found)
        assert callable(probe.with_context)

    def test_with_context_returns_new_instance(self) -> None:
        """with_context should return a new probe instance with context bound."""
        from shared_kernel.observability_context import ObservationContext

        probe = DefaultTenantContextProbe()
        context = ObservationContext(request_id="req-123", user_id="user-456")
        new_probe = probe.with_context(context)

        assert new_probe is not probe
        assert isinstance(new_probe, DefaultTenantContextProbe)

    def test_probe_methods_do_not_raise(self) -> None:
        """All probe methods should execute without raising exceptions."""
        probe = DefaultTenantContextProbe()

        # These should not raise
        probe.tenant_resolved_from_header(tenant_id="t1", user_id="u1")
        probe.tenant_resolved_from_default(tenant_id="t1", user_id="u1")
        probe.tenant_header_missing(user_id="u1")
        probe.invalid_tenant_id_format(raw_value="bad", user_id="u1")
        probe.tenant_access_denied(tenant_id="t1", user_id="u1")
        probe.tenant_authz_check_failed(
            tenant_id="t1", user_id="u1", error=RuntimeError("test")
        )
        probe.default_tenant_not_found()
