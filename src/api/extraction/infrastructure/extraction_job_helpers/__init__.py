"""Bundled helper scripts copied into agentic-ci extraction job workspaces."""

from pathlib import Path

HELPERS_DIR = Path(__file__).resolve().parent
HELPERS_CONTAINER_DIR = "helpers"
HELPER_SCRIPT_NAMES = ("workload-mutations.sh",)
