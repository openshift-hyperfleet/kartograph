"""Domain-oriented observability for auth flow.

Follows the Domain Oriented Observability pattern from Martin Fowler.
"""

from typing import Protocol

import structlog


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
