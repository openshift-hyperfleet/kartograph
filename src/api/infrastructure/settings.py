"""Application settings using pydantic-settings.

Settings are loaded from environment variables with sensible defaults
for development. Production deployments should set all values explicitly.
"""

from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Valid SSL modes for asyncpg connections
SslMode = Literal["disable", "allow", "prefer", "require", "verify-ca", "verify-full"]


class DatabaseSettings(BaseSettings):
    """Database connection settings.

    Environment variables:
        KARTOGRAPH_DB_HOST: Database host (default: localhost)
        KARTOGRAPH_DB_PORT: Database port (default: 5432)
        KARTOGRAPH_DB_DATABASE: Database name (default: kartograph)
        KARTOGRAPH_DB_USERNAME: Database user (default: kartograph)
        KARTOGRAPH_DB_PASSWORD: Database password (required in production)
        KARTOGRAPH_DB_GRAPH_NAME: AGE graph name (default: kartograph_graph) TODO: Single graph only for tracer bullet
        KARTOGRAPH_DB_POOL_MIN_CONNECTIONS: Minimum connections in pool (default: 2)
        KARTOGRAPH_DB_POOL_MAX_CONNECTIONS: Maximum connections in pool (default: 10)
    """

    model_config = SettingsConfigDict(
        env_prefix="KARTOGRAPH_DB_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    host: str = Field(default="localhost", description="Database host")
    port: int = Field(default=5432, description="Database port")
    database: str = Field(default="kartograph", description="Database name")
    username: str = Field(default="kartograph", description="Database username")
    password: SecretStr = Field(
        default=SecretStr(""),
        description="Database password",
    )
    graph_name: str = Field(
        default="kartograph_graph",
        description="Name of the AGE graph",
    )
    pool_min_connections: int = Field(
        default=2,
        description="Minimum connections in pool",
        ge=1,
        le=100,
    )
    pool_max_connections: int = Field(
        default=10,
        description="Maximum connections in pool",
        ge=1,
        le=100,
    )
    ssl_mode: SslMode = Field(
        default="prefer",
        description="SSL mode for asyncpg connections (disable, allow, prefer, require, verify-ca, verify-full)",
    )

    @model_validator(mode="after")
    def validate_pool_settings(self) -> "DatabaseSettings":
        """Validate pool max >= min."""
        if self.pool_max_connections < self.pool_min_connections:
            raise ValueError(
                f"pool_max_connections ({self.pool_max_connections}) must be >= "
                f"pool_min_connections ({self.pool_min_connections})"
            )
        return self


class CORSSettings(BaseSettings):
    """CORS (Cross-Origin Resource Sharing) settings.

    Environment variables:
        KARTOGRAPH_CORS_ORIGINS: Comma-separated list of allowed origins
            (default: empty, which disables CORS)
        KARTOGRAPH_CORS_ALLOW_CREDENTIALS: Allow credentials (default: true)
        KARTOGRAPH_CORS_ALLOW_METHODS: Comma-separated list of allowed methods
            (default: GET,POST,PUT,DELETE,OPTIONS,PATCH)
        KARTOGRAPH_CORS_ALLOW_HEADERS: Comma-separated list of allowed headers
            (default: *)
    """

    model_config = SettingsConfigDict(
        env_prefix="KARTOGRAPH_CORS_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    origins: list[str] = Field(
        default_factory=list,
        description="List of allowed origins for CORS",
    )
    allow_credentials: bool = Field(
        default=True,
        description="Allow credentials in CORS requests",
    )
    allow_methods: list[str] = Field(
        default_factory=lambda: ["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
        description="Allowed HTTP methods for CORS",
    )
    allow_headers: list[str] = Field(
        default_factory=lambda: ["*"],
        description="Allowed headers for CORS",
    )

    @property
    def is_enabled(self) -> bool:
        """Check if CORS is enabled (has at least one origin configured)."""
        return len(self.origins) > 0


class SpiceDBSettings(BaseSettings):
    """SpiceDB authorization service settings.

    Environment variables:
        SPICEDB_ENDPOINT: gRPC endpoint (default: localhost:50051)
        SPICEDB_PRESHARED_KEY: Pre-shared authentication key (required)
        SPICEDB_USE_TLS: Use TLS for connection (default: true for production)
        SPICEDB_CERT_PATH: Path to custom TLS root certificate (for self-signed certs)
    """

    model_config = SettingsConfigDict(
        env_prefix="SPICEDB_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    endpoint: str = Field(
        default="localhost:50051", description="SpiceDB gRPC endpoint"
    )
    preshared_key: SecretStr = Field(
        default=SecretStr(""),
        description="Pre-shared key for authentication",
    )
    use_tls: bool = Field(
        default=True,
        description="Use TLS for connection (true for production, false for local dev)",
    )
    cert_path: str | None = Field(
        default=None,
        description="Path to custom TLS root certificate (for self-signed certs)",
    )


class Settings(BaseSettings):
    """Main application settings aggregating all configuration sections."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Application metadata
    app_name: str = Field(default="Kartograph API", description="Application name")
    debug: bool = Field(default=False, description="Debug mode")

    @property
    def database(self) -> DatabaseSettings:
        """Get database settings."""
        return get_database_settings()

    @property
    def spicedb(self) -> SpiceDBSettings:
        """Get SpiceDB settings."""
        return get_spicedb_settings()

    @property
    def cors(self) -> CORSSettings:
        """Get CORS settings."""
        return get_cors_settings()


@lru_cache
def get_settings() -> Settings:
    """Get cached application settings.

    Uses lru_cache to ensure settings are only loaded once.
    """
    return Settings()


@lru_cache
def get_database_settings() -> DatabaseSettings:
    """Get cached database settings.

    Uses lru_cache to ensure settings are only loaded once.
    """
    return DatabaseSettings()


@lru_cache
def get_spicedb_settings() -> SpiceDBSettings:
    """Get cached SpiceDB settings.

    Uses lru_cache to ensure settings are only loaded once.
    """
    return SpiceDBSettings()


@lru_cache
def get_cors_settings() -> CORSSettings:
    """Get cached CORS settings.

    Uses lru_cache to ensure settings are only loaded once.
    """
    return CORSSettings()


class OutboxWorkerSettings(BaseSettings):
    """Outbox worker settings.

    Environment variables:
        KARTOGRAPH_OUTBOX_ENABLED: Enable the outbox worker (default: true)
        KARTOGRAPH_OUTBOX_POLL_INTERVAL_SECONDS: Poll interval in seconds (default: 30)
        KARTOGRAPH_OUTBOX_BATCH_SIZE: Maximum entries per batch (default: 100)
    """

    model_config = SettingsConfigDict(
        env_prefix="KARTOGRAPH_OUTBOX_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    enabled: bool = Field(
        default=True,
        description="Enable the outbox worker",
    )
    poll_interval_seconds: int = Field(
        default=30,
        description="How often to poll for unprocessed entries",
        ge=1,
        le=3600,
    )
    batch_size: int = Field(
        default=100,
        description="Maximum entries to process per batch",
        ge=1,
        le=1000,
    )
    max_retries: int = Field(
        default=5,
        description="Maximum retry attempts before moving to DLQ",
        ge=1,
        le=100,
    )


@lru_cache
def get_outbox_worker_settings() -> OutboxWorkerSettings:
    """Get cached outbox worker settings.

    Uses lru_cache to ensure settings are only loaded once.
    """
    return OutboxWorkerSettings()


class IAMSettings(BaseSettings):
    """IAM (Identity and Access Management) settings.

    Environment variables:
        KARTOGRAPH_IAM_DEFAULT_TENANT_NAME: Default tenant name for single-tenant mode (default: default)
        KARTOGRAPH_IAM_DEFAULT_WORKSPACE_NAME: Default root workspace name (default: None, uses tenant name)
    """

    model_config = SettingsConfigDict(
        env_prefix="KARTOGRAPH_IAM_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    default_tenant_name: str = Field(
        default="default",
        description="Default tenant name for single-tenant mode",
    )

    default_workspace_name: str | None = Field(
        default=None,
        description="Default root workspace name (if None, uses tenant name)",
    )


@lru_cache
def get_iam_settings() -> IAMSettings:
    """Get cached IAM settings.

    Uses lru_cache to ensure settings are only loaded once.
    """
    return IAMSettings()


class OIDCSettings(BaseSettings):
    """OIDC (OpenID Connect) SSO settings.

    Environment variables:
        KARTOGRAPH_OIDC_ISSUER_URL: OIDC issuer URL (default: http://localhost:8080/realms/kartograph)
        KARTOGRAPH_OIDC_CLIENT_ID: OIDC client ID for the API (default: kartograph-api)
        KARTOGRAPH_OIDC_CLIENT_SECRET: OIDC client secret (required)
        KARTOGRAPH_OIDC_SWAGGER_CLIENT_ID: OIDC client ID for Swagger UI (default: kartograph-swagger)
        KARTOGRAPH_OIDC_USER_ID_CLAIM: Claim to use for user ID (default: sub)
        KARTOGRAPH_OIDC_USERNAME_CLAIM: Claim to use for username (default: preferred_username)
        KARTOGRAPH_OIDC_AUDIENCE: Expected audience claim (default: None, uses client_id)
    """

    model_config = SettingsConfigDict(
        env_prefix="KARTOGRAPH_OIDC_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    issuer_url: str = Field(
        default="http://localhost:8080/realms/kartograph",
        description="OIDC issuer URL (e.g., Keycloak realm URL)",
    )
    client_id: str = Field(
        default="kartograph-api",
        description="OIDC client ID for the API",
    )
    client_secret: SecretStr = Field(
        default=SecretStr(""),
        description="OIDC client secret",
    )
    swagger_client_id: str = Field(
        default="kartograph-swagger",
        description="OIDC client ID for Swagger UI (public client)",
    )
    user_id_claim: str = Field(
        default="sub",
        description="JWT claim to use for user ID",
    )
    username_claim: str = Field(
        default="preferred_username",
        description="JWT claim to use for username",
    )
    audience: str | None = Field(
        default=None,
        description="Expected audience claim (defaults to client_id if None)",
    )

    @property
    def effective_audience(self) -> str:
        """Get the effective audience, defaulting to client_id if not set."""
        return self.audience if self.audience is not None else self.client_id


@lru_cache
def get_oidc_settings() -> OIDCSettings:
    """Get cached OIDC settings.

    Uses lru_cache to ensure settings are only loaded once.
    """
    return OIDCSettings()
