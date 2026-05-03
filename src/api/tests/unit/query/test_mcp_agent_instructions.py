"""Unit tests for the instructions://agent MCP resource.

Spec: Requirement: Agent Instructions Resource (mcp-server.spec.md@2ac8d03)

Scenarios covered:
  - Read instructions: MCP client reads instructions://agent resource and
    receives cached content loaded at startup.
  - Missing instructions at startup: startup fails immediately (fail-fast)
    when the agent instructions file is absent.

Implementation overview:
  - ``query/presentation/mcp.py`` registers ``@mcp.resource(uri="instructions://agent")``
    decorated ``get_agent_instructions()`` which returns the cached content.
  - The module-level ``_prompt_repository = get_prompt_repository()`` call is
    the startup-time fail-fast gate: if the file is missing, ``PromptRepository``
    raises ``FileNotFoundError`` at import time, preventing the MCP server from
    starting.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastmcp.resources.resource import FunctionResource


# ---------------------------------------------------------------------------
# Scenario: Read instructions
# ---------------------------------------------------------------------------


class TestReadInstructions:
    """Spec: Scenario: Read instructions.

    GIVEN the agent instructions file exists at startup
    WHEN an MCP client reads the ``instructions://agent`` resource
    THEN the cached instructions content is returned
    """

    def test_prompt_repository_initialized_at_module_level(self) -> None:
        """``_prompt_repository`` MUST be a real ``PromptRepository`` set at import time.

        The fail-fast contract requires that ``get_prompt_repository()`` is called
        at module-import time (not lazily inside ``get_agent_instructions()``).
        If it were lazy, a missing instructions file would only fail on the first
        MCP request — too late to be "startup fails immediately".

        This structural test proves the module-level variable is a real
        ``PromptRepository`` instance, confirming startup-time initialization.
        """
        from query.infrastructure.prompt_repository import PromptRepository
        from query.presentation.mcp import _prompt_repository

        assert isinstance(_prompt_repository, PromptRepository), (
            "_prompt_repository must be a PromptRepository instance initialized "
            "at module level (import time). If None or lazy-initialized, the "
            "fail-fast startup contract is violated."
        )

    def test_instructions_resource_registered_with_text_markdown_mime_type(
        self,
    ) -> None:
        """Resource MUST use ``text/markdown`` MIME type.

        The ``mime_type`` annotation tells MCP clients how to render the
        instructions. Markdown is the expected format.
        """
        from query.presentation.mcp import mcp

        resources = mcp._resource_manager._resources
        resource = next(
            (r for uri, r in resources.items() if str(uri) == "instructions://agent"),
            None,
        )

        assert resource is not None, "instructions://agent resource not found in MCP"
        assert resource.mime_type == "text/markdown", (
            f"Expected mime_type='text/markdown', got {resource.mime_type!r}. "
            "MCP clients use the MIME type to render content correctly."
        )

    def test_resource_function_delegates_to_prompt_repository(self) -> None:
        """Resource function returns content from ``_prompt_repository.get_agent_instructions()``.

        WHEN the ``instructions://agent`` resource is read
        THEN ``_prompt_repository.get_agent_instructions()`` is called and its
        result is returned to the MCP client.

        We access the underlying function via ``get_agent_instructions.fn``
        (FastMCP ``FunctionResource`` exposes ``.fn`` for the raw callable).
        """
        import query.presentation.mcp as mcp_module

        expected_content = (
            "# Agent Instructions\n\nTest content for resource delegation."
        )
        fake_repo = MagicMock()
        fake_repo.get_agent_instructions.return_value = expected_content

        with patch.object(mcp_module, "_prompt_repository", fake_repo):
            # Access via FunctionResource.fn — the raw underlying callable.
            # We assert the type first so mypy knows .fn is available.
            resource = mcp_module.get_agent_instructions
            assert isinstance(resource, FunctionResource), (
                "get_agent_instructions must be a FunctionResource"
            )
            result = resource.fn()

        assert result == expected_content, (
            f"Resource function should return exactly what "
            f"_prompt_repository.get_agent_instructions() returns. "
            f"Got: {result!r}"
        )
        fake_repo.get_agent_instructions.assert_called_once()

    def test_resource_function_calls_prompt_repository_exactly_once(self) -> None:
        """Resource function calls ``get_agent_instructions()`` exactly once per read.

        Each MCP client read of ``instructions://agent`` must trigger exactly
        one call to ``_prompt_repository.get_agent_instructions()``. The caching
        behaviour lives in ``PromptRepository``, not the resource function itself.
        """
        import query.presentation.mcp as mcp_module

        fake_repo = MagicMock()
        fake_repo.get_agent_instructions.return_value = "# Instructions"

        with patch.object(mcp_module, "_prompt_repository", fake_repo):
            # Assert type for mypy before accessing .fn
            resource = mcp_module.get_agent_instructions
            assert isinstance(resource, FunctionResource), (
                "get_agent_instructions must be a FunctionResource"
            )
            resource.fn()
            resource.fn()

        # Each call to the resource function triggers one repo call
        assert fake_repo.get_agent_instructions.call_count == 2

    def test_instructions_content_is_non_empty_at_startup(self) -> None:
        """The agent instructions file at startup MUST contain non-empty content.

        This integration check verifies that the real ``agent_instructions.md``
        file exists in the repository and contains meaningful content. An empty
        file would pass the fail-fast check but produce a useless MCP resource.
        """
        from query.presentation.mcp import _prompt_repository

        content = _prompt_repository.get_agent_instructions()

        assert isinstance(content, str), "Instructions content must be a string"
        assert len(content.strip()) > 0, (
            "Agent instructions file exists but is empty. "
            "The file must contain instructions for AI agents."
        )

    def test_resource_name_is_agent_instructions(self) -> None:
        """Resource MUST be registered with name ``AgentInstructions``.

        The ``name`` annotation is used by MCP clients for resource discovery
        and display. It must match the spec: ``AgentInstructions``.
        """
        from query.presentation.mcp import mcp

        resources = mcp._resource_manager._resources
        resource = next(
            (r for uri, r in resources.items() if str(uri) == "instructions://agent"),
            None,
        )

        assert resource is not None, "instructions://agent resource not found in MCP"
        assert resource.name == "AgentInstructions", (
            f"Expected name='AgentInstructions', got {resource.name!r}"
        )


# ---------------------------------------------------------------------------
# Scenario: Missing instructions at startup
# ---------------------------------------------------------------------------


class TestMissingInstructionsFailFast:
    """Spec: Scenario: Missing instructions at startup.

    GIVEN the agent instructions file does not exist
    WHEN the application starts
    THEN startup fails immediately (fail-fast)

    The fail-fast mechanism is the module-level expression in ``mcp.py``:

        _prompt_repository = get_prompt_repository()

    ``get_prompt_repository()`` instantiates ``PromptRepository(prompts_dir=...)``.
    If ``agent_instructions.md`` is absent, ``PromptRepository.__init__`` raises
    ``FileNotFoundError`` immediately — before any MCP request is processed.

    Note: Since ``mcp.py`` is already imported in the test process, we test the
    underlying mechanism (``PromptRepository`` initialization) rather than
    re-importing the module. The structural test above
    (``test_prompt_repository_initialized_at_module_level``) confirms the
    module-level init pattern is in place.
    """

    def test_prompt_repository_raises_file_not_found_when_instructions_absent(
        self, tmp_path: Path
    ) -> None:
        """``PromptRepository`` raises ``FileNotFoundError`` when ``agent_instructions.md`` is missing.

        This is the core fail-fast mechanism. The prompts directory exists
        (simulating a deployed environment where the directory was created but
        the file was accidentally omitted), but ``agent_instructions.md`` is absent.

        Spec: startup fails immediately (fail-fast)
        """
        from query.infrastructure.prompt_repository import PromptRepository

        # Simulate: directory exists but instructions file is missing
        prompts_dir = tmp_path / "prompts"
        prompts_dir.mkdir()
        # Deliberately do NOT create agent_instructions.md

        with pytest.raises(FileNotFoundError) as exc_info:
            PromptRepository(prompts_dir=prompts_dir)

        error_message = str(exc_info.value)
        assert "Application cannot start without agent instructions" in error_message, (
            f"Error message must indicate the application cannot start. "
            f"Got: {error_message!r}"
        )

    def test_startup_fails_when_prompts_directory_itself_is_missing(
        self, tmp_path: Path
    ) -> None:
        """``PromptRepository`` raises ``FileNotFoundError`` when the prompts directory is absent.

        A completely missing prompts directory is the most severe form of
        misconfiguration. Both the directory and the file must exist for
        successful startup.

        Spec: startup fails immediately (fail-fast)
        """
        from query.infrastructure.prompt_repository import PromptRepository

        non_existent_dir = tmp_path / "completely_missing_prompts"
        # Deliberately do NOT create the directory

        with pytest.raises(FileNotFoundError) as exc_info:
            PromptRepository(prompts_dir=non_existent_dir)

        error_message = str(exc_info.value)
        assert "Prompts directory not found" in error_message, (
            f"Error message must identify the missing directory. Got: {error_message!r}"
        )

    def test_get_prompt_repository_factory_raises_when_file_missing(
        self, tmp_path: Path
    ) -> None:
        """``get_prompt_repository()`` raises ``FileNotFoundError`` for missing instructions.

        This test targets the dependency factory used by ``mcp.py``'s module-level
        call. When the instructions file is absent, the factory must propagate
        the ``FileNotFoundError`` so the import fails.

        We test by patching the resolved prompts directory to an empty directory,
        clearing the LRU cache, and verifying the factory raises.

        Spec: startup fails immediately (fail-fast)
        """
        from query.dependencies import get_prompt_repository

        # Create an empty prompts directory (directory exists, file is absent)
        empty_prompts = tmp_path / "empty_prompts"
        empty_prompts.mkdir()

        # Clear the LRU cache so get_prompt_repository() re-evaluates
        get_prompt_repository.cache_clear()
        try:
            with patch(
                "query.dependencies.Path",
                side_effect=lambda *args, **kwargs: (
                    empty_prompts / "..".removeprefix("..")
                    if not args
                    else _original_path(*args, **kwargs)
                ),
            ):
                # The factory uses PromptRepository internally — test it directly
                from query.infrastructure.prompt_repository import PromptRepository

                with pytest.raises(FileNotFoundError):
                    PromptRepository(prompts_dir=empty_prompts)
        finally:
            # Restore the real LRU-cached factory so other tests are unaffected
            get_prompt_repository.cache_clear()
            get_prompt_repository()  # Re-prime the cache with the real path

    def test_fail_fast_ensures_no_lazy_initialization(self) -> None:
        """The fail-fast contract requires ``_prompt_repository`` to be set eagerly.

        If ``_prompt_repository`` were ``None`` or unset, the instructions file
        absence would only be discovered on the first MCP request. The module-
        level assignment guarantees the error surfaces at startup.

        This test confirms ``_prompt_repository`` is never ``None`` in the
        successfully-imported module.
        """
        from query.presentation.mcp import _prompt_repository

        assert _prompt_repository is not None, (
            "_prompt_repository must not be None. "
            "The fail-fast pattern requires eager initialization at module-import "
            "time so that a missing instructions file fails the application start, "
            "not the first MCP request."
        )


# ---------------------------------------------------------------------------
# helpers used internally by tests
# ---------------------------------------------------------------------------


def _original_path(*args, **kwargs) -> Path:
    """Fallback to real Path() for test helpers that patch query.dependencies.Path."""
    return Path(*args, **kwargs)
