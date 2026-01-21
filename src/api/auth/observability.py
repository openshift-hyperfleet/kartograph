"""Domain-oriented observability for auth configuration.

Follows the Domain Oriented Observability pattern from Martin Fowler.
"""

from typing import TYPE_CHECKING, Protocol

import structlog

if TYPE_CHECKING:
    from infrastructure.settings import OIDCSettings


class OIDCConfigProbe(Protocol):
    """Observability probe for OIDC configuration events."""

    def oidc_configured(
        self,
        issuer_url: str,
        client_id: str,
        swagger_client_id: str,
        user_id_claim: str,
        username_claim: str,
        audience: str,
    ) -> None:
        """Called when OIDC settings are loaded."""
        ...


class DefaultOIDCConfigProbe:
    """Default implementation of OIDCConfigProbe using structlog."""

    def __init__(self) -> None:
        self._logger = structlog.get_logger(__name__)

    def oidc_configured(
        self,
        issuer_url: str,
        client_id: str,
        swagger_client_id: str,
        user_id_claim: str,
        username_claim: str,
        audience: str,
    ) -> None:
        """Log OIDC configuration (non-sensitive details only)."""
        self._logger.info(
            "oidc_configured",
            issuer_url=issuer_url,
            client_id=client_id,
            swagger_client_id=swagger_client_id,
            user_id_claim=user_id_claim,
            username_claim=username_claim,
            audience=audience,
        )

    @classmethod
    def log_settings(cls, settings: "OIDCSettings") -> None:
        """Convenience method to log OIDC settings."""
        probe = cls()
        probe.oidc_configured(
            issuer_url=settings.issuer_url,
            client_id=settings.client_id,
            swagger_client_id=settings.swagger_client_id,
            user_id_claim=settings.user_id_claim,
            username_claim=settings.username_claim,
            audience=settings.effective_audience,
        )
