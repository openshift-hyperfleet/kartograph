"""Application settings using pydantic-settings.

Settings are loaded from environment variables with sensible defaults
for development. Production deployments should set all values explicitly.
"""

from functools import lru_cache

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


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

    @model_validator(mode="after")
    def validate_pool_settings(self) -> "DatabaseSettings":
        """Validate pool max >= min."""
        if self.pool_max_connections < self.pool_min_connections:
            raise ValueError(
                f"pool_max_connections ({self.pool_max_connections}) must be >= "
                f"pool_min_connections ({self.pool_min_connections})"
            )
        return self

    @property
    def connection_string(self) -> str:
        """Generate a connection string (without password for logging)."""
        return f"postgresql://{self.username}@{self.host}:{self.port}/{self.database}"


class SpiceDBSettings(BaseSettings):
    """SpiceDB authorization service settings.

    Environment variables:
        SPICEDB_ENDPOINT: gRPC endpoint (default: localhost:50051)
        SPICEDB_PRESHARED_KEY: Pre-shared authentication key (required)
        SPICEDB_USE_TLS: Use TLS for connection (default: true for production)
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
        default=SecretStr("changeme"),
        description="Pre-shared key for authentication",
    )
    use_tls: bool = Field(
        default=False,
        description="Use TLS for connection (true for production, false for local dev)",
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
