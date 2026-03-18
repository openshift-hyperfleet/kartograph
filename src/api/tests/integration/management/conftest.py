"""Integration test fixtures for Management bounded context.

These fixtures require running PostgreSQL, SpiceDB, and Keycloak instances.
"""

from __future__ import annotations

import os
from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from asgi_lifespan import LifespanManager
from cryptography.fernet import Fernet
from httpx import ASGITransport, AsyncClient
from jose import jwt as jose_jwt
from pydantic import SecretStr
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from infrastructure.authorization_dependencies import get_spicedb_client
from infrastructure.database.engines import create_write_engine
from infrastructure.settings import DatabaseSettings
from shared_kernel.authorization.protocols import AuthorizationProvider
from shared_kernel.authorization.types import (
    Permission,
    ResourceType,
    format_resource,
    format_subject,
)
from tests.integration.iam.conftest import wait_for_permission

# Ensure encryption key is available for management services
os.environ.setdefault("KARTOGRAPH_MGMT_ENCRYPTION_KEY", Fernet.generate_key().decode())


@pytest.fixture(scope="session")
def mgmt_db_settings() -> DatabaseSettings:
    """Database settings for management integration tests."""
    return DatabaseSettings(
        host=os.getenv("KARTOGRAPH_DB_HOST", "localhost"),
        port=int(os.getenv("KARTOGRAPH_DB_PORT", "5432")),
        database=os.getenv("KARTOGRAPH_DB_DATABASE", "kartograph"),
        username=os.getenv("KARTOGRAPH_DB_USERNAME", "kartograph"),
        password=SecretStr(
            os.getenv("KARTOGRAPH_DB_PASSWORD", "kartograph_dev_password")
        ),
        graph_name="test_graph",
    )


@pytest_asyncio.fixture
async def mgmt_async_session(
    mgmt_db_settings: DatabaseSettings,
) -> AsyncGenerator[AsyncSession, None]:
    """Provide an async session for management integration tests."""
    engine = create_write_engine(mgmt_db_settings)
    sessionmaker = async_sessionmaker(engine, expire_on_commit=False)

    async with sessionmaker() as session:
        yield session

    await engine.dispose()


@pytest_asyncio.fixture
async def async_client():
    """Create async HTTP client for testing with lifespan support."""
    from main import app

    async with LifespanManager(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            yield client


@pytest.fixture
def spicedb_client() -> AuthorizationProvider:
    """Provide a SpiceDB client for integration tests."""
    return get_spicedb_client()


@pytest.fixture
def alice_user_id(alice_token: str) -> str:
    """Extract the actual user_id (sub claim) from alice's JWT token."""
    claims = jose_jwt.get_unverified_claims(alice_token)
    return claims["sub"]


@pytest_asyncio.fixture
async def clean_management_data(
    mgmt_async_session: AsyncSession,
) -> AsyncGenerator[None, None]:
    """Clean management tables before and after tests.

    Deletion order respects FK constraints:
    data_source_sync_runs -> data_sources -> knowledge_graphs
    """

    async def cleanup() -> None:
        try:
            async with mgmt_async_session.begin():
                await mgmt_async_session.execute(
                    text("DELETE FROM data_source_sync_runs")
                )
                await mgmt_async_session.execute(text("DELETE FROM data_sources"))
                await mgmt_async_session.execute(text("DELETE FROM knowledge_graphs"))
                # Clean outbox entries related to management
                await mgmt_async_session.execute(
                    text(
                        "DELETE FROM outbox WHERE aggregate_type IN "
                        "('KnowledgeGraph', 'DataSource')"
                    )
                )
        except Exception:
            await mgmt_async_session.rollback()
            raise

    await cleanup()
    yield
    await cleanup()


async def grant_kg_permission(
    spicedb_client: AuthorizationProvider,
    user_id: str,
    kg_id: str,
    workspace_id: str,
) -> None:
    """Set up SpiceDB relationships for a KG.

    Writes the workspace relationship on the KG and grants
    admin permission on the KG to the user.
    """
    kg_resource = format_resource(ResourceType.KNOWLEDGE_GRAPH, kg_id)
    user_subject = format_subject(ResourceType.USER, user_id)
    ws_subject = format_resource(ResourceType.WORKSPACE, workspace_id)

    # Write workspace parent relationship
    await spicedb_client.write_relationship(
        resource=kg_resource,
        relation="workspace",
        subject=ws_subject,
    )

    # Wait for view permission (inherited from workspace)
    view_ready = await wait_for_permission(
        spicedb_client,
        resource=kg_resource,
        permission=Permission.VIEW,
        subject=user_subject,
        timeout=5.0,
    )
    assert view_ready, "Timed out waiting for KG view permission"


async def grant_ds_permission(
    spicedb_client: AuthorizationProvider,
    user_id: str,
    ds_id: str,
    kg_id: str,
) -> None:
    """Set up SpiceDB relationships for a DataSource.

    Writes the knowledge_graph relationship on the DS so permissions
    inherit from the KG.
    """
    ds_resource = format_resource(ResourceType.DATA_SOURCE, ds_id)
    user_subject = format_subject(ResourceType.USER, user_id)
    kg_subject = format_resource(ResourceType.KNOWLEDGE_GRAPH, kg_id)

    # Write knowledge_graph parent relationship
    await spicedb_client.write_relationship(
        resource=ds_resource,
        relation="knowledge_graph",
        subject=kg_subject,
    )

    # Wait for view permission (inherited from KG)
    view_ready = await wait_for_permission(
        spicedb_client,
        resource=ds_resource,
        permission=Permission.VIEW,
        subject=user_subject,
        timeout=5.0,
    )
    assert view_ready, "Timed out waiting for DS view permission"
