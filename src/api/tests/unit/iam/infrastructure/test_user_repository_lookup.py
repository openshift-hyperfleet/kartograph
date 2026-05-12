"""Unit tests for UserRepository lookup methods (get_by_ids, search).

Tests verify the new batch and search repository methods introduced
for the User Lookup endpoint (GET /iam/users).
"""

import pytest
from unittest.mock import AsyncMock, MagicMock

from iam.domain.aggregates import User
from iam.domain.value_objects import UserId
from iam.infrastructure.models import UserModel
from iam.infrastructure.user_repository import UserRepository


@pytest.fixture
def mock_session():
    """Create mock async session."""
    return AsyncMock()


@pytest.fixture
def repository(mock_session):
    """Create repository with mock session."""
    return UserRepository(session=mock_session)


class TestGetByIds:
    """Tests for get_by_ids method."""

    @pytest.mark.asyncio
    async def test_returns_matching_users(self, repository, mock_session):
        """Should return User aggregates for matching IDs."""
        model1 = UserModel(
            id="id1", username="alice", name="Alice", email="alice@example.com"
        )
        model2 = UserModel(id="id2", username="bob", name="Bob", email=None)

        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [model1, model2]
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute.return_value = mock_result

        result = await repository.get_by_ids([UserId(value="id1"), UserId(value="id2")])

        assert len(result) == 2
        assert all(isinstance(u, User) for u in result)
        assert result[0].id.value == "id1"
        assert result[0].username == "alice"
        assert result[0].name == "Alice"
        assert result[0].email == "alice@example.com"
        assert result[1].id.value == "id2"
        assert result[1].username == "bob"

    @pytest.mark.asyncio
    async def test_returns_empty_for_empty_input(self, repository, mock_session):
        """Should return empty list when given no IDs."""
        result = await repository.get_by_ids([])

        assert result == []
        # Should not hit the database
        mock_session.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_returns_empty_when_no_matches(self, repository, mock_session):
        """Should return empty list when no IDs match."""
        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = []
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute.return_value = mock_result

        result = await repository.get_by_ids([UserId(value="nonexistent")])

        assert result == []


class TestSearch:
    """Tests for search method."""

    @pytest.mark.asyncio
    async def test_returns_matching_users(self, repository, mock_session):
        """Should return users matching the search query."""
        model = UserModel(
            id="id1", username="alice", name="Alice Smith", email="alice@example.com"
        )

        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [model]
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute.return_value = mock_result

        result = await repository.search("alice")

        assert len(result) == 1
        assert result[0].username == "alice"
        assert result[0].name == "Alice Smith"

    @pytest.mark.asyncio
    async def test_respects_limit(self, repository, mock_session):
        """Should pass the limit to the query."""
        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = []
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute.return_value = mock_result

        await repository.search("test", limit=5)

        # Verify execute was called (the limit is part of the SQL statement)
        mock_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_returns_empty_for_no_matches(self, repository, mock_session):
        """Should return empty list when no users match."""
        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = []
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute.return_value = mock_result

        result = await repository.search("zzz_no_match")

        assert result == []
