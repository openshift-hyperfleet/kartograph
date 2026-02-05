"""Unit tests for PromptRepository."""

import pytest

from query.infrastructure.prompt_repository import PromptRepository


@pytest.fixture
def prompts_dir(tmp_path):
    """Create temporary prompts directory."""
    return tmp_path / "prompts"


@pytest.fixture
def repository(prompts_dir):
    """Create repository with temporary directory and required files."""
    prompts_dir.mkdir(parents=True, exist_ok=True)
    # Create required file for repository to initialize
    instructions_file = prompts_dir / "agent_instructions.md"
    instructions_file.write_text("# Default Instructions", encoding="utf-8")
    return PromptRepository(prompts_dir=prompts_dir)


class TestInit:
    """Tests for repository initialization."""

    def test_stores_prompts_directory(self, prompts_dir):
        """Should store prompts directory path."""
        # Setup required file
        prompts_dir.mkdir(parents=True, exist_ok=True)
        (prompts_dir / "agent_instructions.md").write_text("# Test", encoding="utf-8")

        repo = PromptRepository(prompts_dir=prompts_dir)
        assert repo._prompts_dir == prompts_dir

    def test_raises_when_prompts_directory_missing(self, tmp_path):
        """Should raise FileNotFoundError if prompts directory doesn't exist."""
        non_existent_dir = tmp_path / "does_not_exist"

        with pytest.raises(FileNotFoundError, match="Prompts directory not found"):
            PromptRepository(prompts_dir=non_existent_dir)

    def test_raises_when_agent_instructions_missing(self, prompts_dir):
        """Should raise FileNotFoundError if agent_instructions.md is missing."""
        prompts_dir.mkdir(parents=True, exist_ok=True)
        # Directory exists but file doesn't

        with pytest.raises(
            FileNotFoundError,
            match="Application cannot start without agent instructions",
        ):
            PromptRepository(prompts_dir=prompts_dir)


class TestGetAgentInstructions:
    """Tests for loading agent instructions."""

    def test_loads_agent_instructions_from_file(self, prompts_dir):
        """Should load agent instructions from markdown file."""
        # Setup
        prompts_dir.mkdir(parents=True, exist_ok=True)
        instructions_file = prompts_dir / "agent_instructions.md"
        instructions_content = "# Agent Instructions\n\nTest content here"
        instructions_file.write_text(instructions_content, encoding="utf-8")

        # Create repository (validation passes)
        repository = PromptRepository(prompts_dir=prompts_dir)

        # Execute
        result = repository.get_agent_instructions()

        # Verify
        assert result == instructions_content

    def test_caches_instructions_across_calls(self, prompts_dir):
        """Should cache instructions and not re-read file on subsequent calls."""
        # Setup
        prompts_dir.mkdir(parents=True, exist_ok=True)
        instructions_file = prompts_dir / "agent_instructions.md"
        original_content = "# Original Content"
        instructions_file.write_text(original_content, encoding="utf-8")

        # Create repository
        repository = PromptRepository(prompts_dir=prompts_dir)

        # First call - should read from file
        first_result = repository.get_agent_instructions()
        assert first_result == original_content

        # Modify file
        instructions_file.write_text("# Modified Content", encoding="utf-8")

        # Second call - should return cached value, not re-read
        second_result = repository.get_agent_instructions()
        assert second_result == original_content  # Still original!

    def test_handles_unicode_content(self, prompts_dir):
        """Should handle UTF-8 encoded content with unicode characters."""
        # Setup
        prompts_dir.mkdir(parents=True, exist_ok=True)
        instructions_file = prompts_dir / "agent_instructions.md"
        unicode_content = "# Instructions 🚀\n\nEmojis and special chars: café, naïve"
        instructions_file.write_text(unicode_content, encoding="utf-8")

        # Create repository
        repository = PromptRepository(prompts_dir=prompts_dir)

        # Execute
        result = repository.get_agent_instructions()

        # Verify
        assert result == unicode_content
        assert "🚀" in result
        assert "café" in result
