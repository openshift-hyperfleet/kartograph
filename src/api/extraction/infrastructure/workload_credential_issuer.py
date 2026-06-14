"""Stateless JWT workload credentials for extraction runtime containers."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from jose import JWTError, jwt
from jose.exceptions import ExpiredSignatureError
from ulid import ULID

from extraction.ports.runtime import ScopedWorkloadCredentials

WORKLOAD_TOKEN_ALGORITHM = "HS256"
DEFAULT_DEV_WORKLOAD_TOKEN_SIGNING_KEY = "kartograph-dev-workload-token-signing-key"


class ScopedWorkloadCredentialIssuer:
    """Issues and verifies short-lived tenant/KG scoped workload JWTs."""

    def __init__(
        self,
        *,
        signing_key: str = DEFAULT_DEV_WORKLOAD_TOKEN_SIGNING_KEY,
        default_ttl: timedelta = timedelta(minutes=15),
    ) -> None:
        normalized_key = signing_key.strip()
        if not normalized_key:
            raise ValueError("workload token signing key must not be empty")
        self._signing_key = normalized_key
        self._default_ttl = default_ttl

    def issue(
        self,
        *,
        tenant_id: str,
        knowledge_graph_id: str,
        extra_scopes: tuple[str, ...] = (),
    ) -> ScopedWorkloadCredentials:
        now = datetime.now(UTC)
        expires_at = (now + self._default_ttl).replace(microsecond=0)
        scopes = (
            f"tenant:{tenant_id}",
            f"knowledge_graph:{knowledge_graph_id}",
            "workload:extraction",
            *extra_scopes,
        )
        token = jwt.encode(
            {
                "sub": "workload",
                "jti": str(ULID()),
                "scopes": list(scopes),
                "iat": int(now.timestamp()),
                "exp": int(expires_at.timestamp()),
            },
            self._signing_key,
            algorithm=WORKLOAD_TOKEN_ALGORITHM,
        )
        return ScopedWorkloadCredentials(
            token=str(token),
            expires_at=expires_at,
            scopes=scopes,
        )

    def issue_for_sticky_session(
        self,
        *,
        tenant_id: str,
        knowledge_graph_id: str,
        session_id: str,
    ) -> ScopedWorkloadCredentials:
        """Issue chat-scoped credentials for sticky session agent containers."""
        return self.issue(
            tenant_id=tenant_id,
            knowledge_graph_id=knowledge_graph_id,
            extra_scopes=("workload:chat", f"session:{session_id}"),
        )

    def verify(self, token: str) -> ScopedWorkloadCredentials | None:
        """Return credentials when the JWT signature and expiry are valid."""
        try:
            payload = jwt.decode(
                token,
                self._signing_key,
                algorithms=[WORKLOAD_TOKEN_ALGORITHM],
                options={"require_exp": True, "require_iat": True},
            )
        except ExpiredSignatureError:
            return None
        except JWTError:
            return None

        scopes_raw = payload.get("scopes")
        if not isinstance(scopes_raw, list) or not scopes_raw:
            return None

        exp = payload.get("exp")
        if not isinstance(exp, int):
            return None

        expires_at = datetime.fromtimestamp(exp, tz=UTC)
        if expires_at <= datetime.now(UTC):
            return None

        scopes = tuple(str(scope) for scope in scopes_raw)
        return ScopedWorkloadCredentials(
            token=token,
            expires_at=expires_at,
            scopes=scopes,
        )
