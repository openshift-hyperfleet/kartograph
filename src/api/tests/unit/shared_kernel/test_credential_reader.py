"""Tests for ICredentialReader protocol."""

import inspect
from typing import Protocol

import pytest

from shared_kernel.credential_reader import ICredentialReader


class TestICredentialReaderProtocol:
    """Tests for ICredentialReader protocol definition."""

    def test_is_a_protocol(self):
        """ICredentialReader should be a typing.Protocol subclass."""
        assert issubclass(ICredentialReader, Protocol)

    def test_is_runtime_checkable(self):
        """ICredentialReader should be decorated with @runtime_checkable."""
        # runtime_checkable protocols have _is_runtime_protocol set to True
        assert getattr(ICredentialReader, "_is_runtime_protocol", False)

    def test_conforming_class_satisfies_protocol(self):
        """A class implementing retrieve should satisfy the protocol via structural subtyping."""

        class VaultCredentialReader:
            async def retrieve(self, path: str, tenant_id: str) -> dict[str, str]:
                return {}

        reader = VaultCredentialReader()
        assert isinstance(reader, ICredentialReader)

    def test_missing_retrieve_does_not_satisfy_protocol(self):
        """A class without retrieve should NOT satisfy the protocol."""

        class EmptyReader:
            pass

        reader = EmptyReader()
        assert not isinstance(reader, ICredentialReader)

    def test_retrieve_is_async(self):
        """The retrieve method should be a coroutine function."""

        class ConformingReader:
            async def retrieve(self, path: str, tenant_id: str) -> dict[str, str]:
                return {}

        reader = ConformingReader()
        assert inspect.iscoroutinefunction(reader.retrieve)

    @pytest.mark.asyncio
    async def test_retrieve_returns_dict(self):
        """Calling retrieve should return a dict[str, str]."""

        class StubReader:
            async def retrieve(self, path: str, tenant_id: str) -> dict[str, str]:
                return {"username": "admin", "password": "secret"}

        reader = StubReader()
        result = await reader.retrieve(path="secret/data/github", tenant_id="tenant-1")

        assert isinstance(result, dict)
        assert result == {"username": "admin", "password": "secret"}

    @pytest.mark.asyncio
    async def test_retrieve_raises_keyerror_when_missing(self):
        """Calling retrieve should raise KeyError when credentials are not found."""

        class StubReader:
            async def retrieve(self, path: str, tenant_id: str) -> dict[str, str]:
                raise KeyError(f"No credentials at {path} for tenant {tenant_id}")

        reader = StubReader()
        with pytest.raises(KeyError):
            await reader.retrieve(
                path="datasource/nonexistent/credentials", tenant_id="tenant-1"
            )

    def test_retrieve_signature_parameters(self):
        """The retrieve method should accept path and tenant_id string parameters."""

        class ConformingReader:
            async def retrieve(self, path: str, tenant_id: str) -> dict[str, str]:
                return {}

        sig = inspect.signature(ConformingReader.retrieve)
        params = list(sig.parameters.keys())

        assert "self" in params
        assert "path" in params
        assert "tenant_id" in params
        assert sig.parameters["path"].annotation is str
        assert sig.parameters["tenant_id"].annotation is str
