"""Domain-oriented observability for auth flow.

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
        auth_routes_enabled: bool,
        user_id_claim: str,
        username_claim: str,
        audience: str,
    ) -> None:
        """Called when OIDC settings are loaded."""
        ...

    def oidc_configuration_failed(self, error: str) -> None:
        """Called when OIDC configuration fails."""
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
        auth_routes_enabled: bool,
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
            auth_routes_enabled=auth_routes_enabled,
            user_id_claim=user_id_claim,
            username_claim=username_claim,
            audience=audience,
        )

    def oidc_configuration_failed(self, error: str) -> None:
        """Log when OIDC configuration fails."""
        self._logger.warning(
            "oidc_configuration_failed",
            error=error,
        )

    @classmethod
    def log_settings(cls, settings: "OIDCSettings") -> None:
        """Convenience method to log OIDC settings."""
        probe = cls()
        probe.oidc_configured(
            issuer_url=settings.issuer_url,
            client_id=settings.client_id,
            swagger_client_id=settings.swagger_client_id,
            auth_routes_enabled=settings.auth_routes_enabled,
            user_id_claim=settings.user_id_claim,
            username_claim=settings.username_claim,
            audience=settings.effective_audience,
        )


class AuthFlowProbe(Protocol):
    """Observability probe for OIDC auth flow."""

    def login_initiated(self, redirect_uri: str) -> None:
        """Called when a login flow is initiated."""
        ...

    def callback_received(self, state: str) -> None:
        """Called when an OIDC callback is received."""
        ...

    def token_exchange_success(self, user_id: str) -> None:
        """Called when token exchange succeeds."""
        ...

    def token_exchange_failed(self, error: str) -> None:
        """Called when token exchange fails."""
        ...

    def invalid_state(self, state: str) -> None:
        """Called when an invalid state parameter is received."""
        ...

    def discovery_failed(self, error: str) -> None:
        """Called when OIDC discovery fails."""
        ...


class DefaultAuthFlowProbe:
    """Default implementation of AuthFlowProbe using structlog."""

    def __init__(self) -> None:
        self._logger = structlog.get_logger(__name__)

    def login_initiated(self, redirect_uri: str) -> None:
        """Log when a login flow is initiated."""
        self._logger.info(
            "oidc_login_initiated",
            redirect_uri=redirect_uri,
        )

    def callback_received(self, state: str) -> None:
        """Log when an OIDC callback is received."""
        self._logger.info(
            "oidc_callback_received",
            state_prefix=state[:8] if len(state) >= 8 else state,
        )

    def token_exchange_success(self, user_id: str) -> None:
        """Log when token exchange succeeds."""
        self._logger.info(
            "oidc_token_exchange_success",
            user_id=user_id,
        )

    def token_exchange_failed(self, error: str) -> None:
        """Log when token exchange fails."""
        self._logger.warning(
            "oidc_token_exchange_failed",
            error=error,
        )

    def invalid_state(self, state: str) -> None:
        """Log when an invalid state parameter is received."""
        self._logger.warning(
            "oidc_invalid_state",
            state_prefix=state[:8] if len(state) >= 8 else state,
        )

    def discovery_failed(self, error: str) -> None:
        """Log when OIDC discovery fails."""
        self._logger.error(
            "oidc_discovery_failed",
            error=error,
        )
