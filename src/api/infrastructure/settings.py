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
        KARTOGRAPH_DB_POOL_ENABLED: Enable connection pooling (default: true)
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
