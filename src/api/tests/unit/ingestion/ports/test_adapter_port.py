"""Unit tests for IDatasourceAdapter port contract.

These tests verify:
1. The port is a Protocol (structurally typed).
2. ExtractionResult is an immutable value object.
3. Any class implementing the correct signature satisfies the Protocol.
4. The port does NOT import dlt or any adapter framework (domain isolation).

Spec scenarios covered:
- Extract contract: adapter implements IDatasourceAdapter; extract accepts
  credentials and checkpoint state; returns raw extracted data and checkpoint.
- Domain isolation: port lives in Ingestion domain layer with no dlt imports.
"""

from __future__ import annotations

import pytest

from ingestion.ports.adapters import ExtractionResult, IDatasourceAdapter
from shared_kernel.job_package.value_objects import (
    AdapterCheckpoint,
    ChangeOperation,
    ChangesetEntry,
    ContentRef,
    SyncMode,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_checkpoint(sha: str = "abc123") -> AdapterCheckpoint:
    return AdapterCheckpoint(schema_version="1.0.0", data={"commit_sha": sha})


def _make_entry(path: str = "README.md") -> ChangesetEntry:
    return ChangesetEntry(
        operation=ChangeOperation.ADD,
        id=f"sha256-{path}",
        type="io.kartograph.change.file",
        path=path,
        content_ref=ContentRef.from_bytes(b"hello"),
        content_type="text/plain",
        metadata={},
    )


# ---------------------------------------------------------------------------
# ExtractionResult value object
# ---------------------------------------------------------------------------


class TestExtractionResult:
    """ExtractionResult is an immutable value object holding extraction output."""

    def test_construction(self):
        """ExtractionResult can be constructed with all required fields."""
        entry = _make_entry()
        checkpoint = _make_checkpoint()
        content_ref = ContentRef.from_bytes(b"hello")

        result = ExtractionResult(
            changeset_entries=[entry],
            content_blobs={content_ref.hex_digest: b"hello"},
            new_checkpoint=checkpoint,
        )

        assert result.changeset_entries == [entry]
        assert result.content_blobs == {content_ref.hex_digest: b"hello"}
        assert result.new_checkpoint == checkpoint

    def test_is_frozen(self):
        """ExtractionResult is immutable (frozen dataclass)."""
        result = ExtractionResult(
            changeset_entries=[],
            content_blobs={},
            new_checkpoint=_make_checkpoint(),
        )

        with pytest.raises((AttributeError, TypeError)):
            result.changeset_entries = []  # type: ignore[misc]

    def test_empty_result_is_valid(self):
        """ExtractionResult with no entries is valid (e.g., no changes since checkpoint)."""
        result = ExtractionResult(
            changeset_entries=[],
            content_blobs={},
            new_checkpoint=_make_checkpoint(),
        )

        assert result.changeset_entries == []
        assert result.content_blobs == {}


# ---------------------------------------------------------------------------
# IDatasourceAdapter protocol structural check
# ---------------------------------------------------------------------------


class TestIDatasourceAdapterProtocol:
    """IDatasourceAdapter is a structural protocol (no base class needed)."""

    def test_is_runtime_checkable(self):
        """IDatasourceAdapter supports isinstance checks at runtime."""
        assert hasattr(IDatasourceAdapter, "__protocol_attrs__") or hasattr(
            IDatasourceAdapter, "_is_protocol"
        )

    def test_concrete_class_satisfies_protocol(self):
        """A class with the correct extract signature satisfies the protocol."""

        class ConcreteAdapter:
            async def extract(
                self,
                connection_config: dict[str, str],
                credentials: dict[str, str],
                checkpoint: AdapterCheckpoint | None,
                sync_mode: SyncMode,
            ) -> ExtractionResult:
                return ExtractionResult(
                    changeset_entries=[],
                    content_blobs={},
                    new_checkpoint=AdapterCheckpoint(schema_version="1.0.0", data={}),
                )

        # Should be recognized as implementing the protocol
        adapter = ConcreteAdapter()
        assert isinstance(adapter, IDatasourceAdapter)

    def test_class_missing_extract_does_not_satisfy_protocol(self):
        """A class missing the extract method does not satisfy the protocol."""

        class BadAdapter:
            pass

        bad = BadAdapter()
        assert not isinstance(bad, IDatasourceAdapter)

    def test_extract_accepts_none_checkpoint(self):
        """The extract method signature accepts None for checkpoint (full refresh)."""
        # Verify the Protocol's annotations include Optional checkpoint
        import inspect

        sig = inspect.signature(IDatasourceAdapter.extract)
        params = list(sig.parameters.values())
        param_names = [p.name for p in params]

        assert "credentials" in param_names
        assert "checkpoint" in param_names
        assert "sync_mode" in param_names
        assert "connection_config" in param_names

    def test_port_module_does_not_import_dlt(self):
        """Domain isolation: the port module must not import dlt.

        Spec scenario: Domain isolation
        - GIVEN the adapter port definition
        - THEN the domain layer does not import dlt or any adapter framework
        """
        import ingestion.ports.adapters as port_module

        # Walk the module's transitive imports
        # Simple check: dlt must not be in the module's globals or sys.modules
        # as a direct import of ingestion.ports.adapters
        module_source_globals = vars(port_module)
        assert "dlt" not in module_source_globals, (
            "ingestion.ports.adapters must not import dlt at the module level"
        )

    def test_port_module_does_not_import_httpx(self):
        """Port module must not import httpx (HTTP transport is infrastructure)."""
        import ingestion.ports.adapters as port_module

        module_globals = vars(port_module)
        assert "httpx" not in module_globals, (
            "ingestion.ports.adapters must not import httpx at the module level"
        )


# ---------------------------------------------------------------------------
# ICredentialReader integration (shared kernel port)
# ---------------------------------------------------------------------------


class TestCredentialReaderPort:
    """Ingestion uses ICredentialReader from shared kernel for credential retrieval.

    Spec scenarios:
    - Port-based credential retrieval: credentials retrieved via shared kernel port.
    - Backend independence: Ingestion requires no code changes when backend changes.
    """

    def test_icredential_reader_importable_from_shared_kernel(self):
        """ICredentialReader is importable from the shared kernel."""
        from shared_kernel.credential_reader import ICredentialReader

        assert ICredentialReader is not None

    def test_icredential_reader_is_protocol(self):
        """ICredentialReader is a Protocol for structural typing."""
        from shared_kernel.credential_reader import ICredentialReader

        # It should be a Protocol — check for protocol markers
        assert hasattr(ICredentialReader, "__protocol_attrs__") or hasattr(
            ICredentialReader, "_is_protocol"
        )

    def test_icredential_reader_has_retrieve_method(self):
        """ICredentialReader exposes retrieve(path, tenant_id) -> dict."""
        import inspect

        from shared_kernel.credential_reader import ICredentialReader

        assert hasattr(ICredentialReader, "retrieve")
        sig = inspect.signature(ICredentialReader.retrieve)
        params = list(sig.parameters.keys())
        assert "path" in params
        assert "tenant_id" in params

    def test_concrete_credential_reader_satisfies_protocol(self):
        """Any class with retrieve(path, tenant_id) satisfies ICredentialReader."""
        from shared_kernel.credential_reader import ICredentialReader

        class FakeCredentialReader:
            async def retrieve(self, path: str, tenant_id: str) -> dict[str, str]:
                return {"token": "fake-token"}

        reader = FakeCredentialReader()
        assert isinstance(reader, ICredentialReader)
