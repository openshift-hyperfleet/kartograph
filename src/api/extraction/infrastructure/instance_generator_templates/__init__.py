"""Bundled instance generator scripts for sticky session workspaces."""

from pathlib import Path

TEMPLATES_DIR = Path(__file__).resolve().parent

TEMPLATE_SCRIPT_NAMES = (
    "_entity_scanner.example.py",
    "entities_to_jsonl.py",
    "relationships_to_jsonl.py",
    "README.md",
)
