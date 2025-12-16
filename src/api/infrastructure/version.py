"""Version management for Kartograph API.

Provides version information using importlib.metadata with fallback to pyproject.toml.
This follows the best practice pattern of using metadata for installed packages
while supporting development mode via direct TOML parsing.
"""

import tomllib
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path


def get_version() -> str:
    """Get the application version.

    Tries to read from installed package metadata first (production/installed mode).
    Falls back to reading from pyproject.toml in development mode.

    Returns:
        Version string (e.g., "0.1.0")
    """
    try:
        # Primary: Use importlib.metadata (works for installed packages)
        return version("kartograph-api")
    except PackageNotFoundError:
        # Fallback: Parse pyproject.toml directly (development mode)
        pyproject_path = Path(__file__).parent.parent / "pyproject.toml"

        with open(pyproject_path, "rb") as f:
            pyproject_data = tomllib.load(f)

        return pyproject_data["project"]["version"]


__version__ = get_version()
