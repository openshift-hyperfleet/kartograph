"""Repository for loading prompt and instruction files."""

from functools import cache
from pathlib import Path


class PromptRepository:
    """Repository for loading prompt/instruction files from the filesystem.

    Uses Python's built-in @cache decorator for automatic memoization,
    ensuring files are read only once per process lifecycle.

    Raises FileNotFoundError at initialization if required files are missing,
    enabling fail-fast behavior at application startup.
    """

    AGENT_INSTRUCTIONS_FILENAME = "agent_instructions.md"

    def __init__(self, prompts_dir: Path):
        """Initialize repository with prompts directory.

        Args:
            prompts_dir: Path to directory containing prompt files

        Raises:
            FileNotFoundError: If prompts directory or required files don't exist
        """
        self._prompts_dir = prompts_dir

        # Pre-flight check: Validate required files exist at startup
        self._validate_required_files()

    def _get_instructions_path(self) -> Path:
        """Get path to agent instructions file.

        Returns:
            Path to agent_instructions.md
        """
        return self._prompts_dir / self.AGENT_INSTRUCTIONS_FILENAME

    def _validate_required_files(self) -> None:
        """Validate that all required prompt files exist.

        Raises:
            FileNotFoundError: If any required file is missing
        """
        if not self._prompts_dir.exists():
            raise FileNotFoundError(f"Prompts directory not found: {self._prompts_dir}")

        instructions_path = self._get_instructions_path()
        if not instructions_path.exists():
            raise FileNotFoundError(
                f"Required file not found: {instructions_path}. "
                "Application cannot start without agent instructions."
            )

    @cache
    def get_agent_instructions(self) -> str:
        """Load agent instructions from markdown file (cached).

        Reads the agent_instructions.md file from the prompts directory.
        Results are cached for the lifetime of the process.

        Returns:
            Agent instructions content as markdown string

        Raises:
            FileNotFoundError: If file is missing (should not happen after init)
        """
        return self._get_instructions_path().read_text(encoding="utf-8")
