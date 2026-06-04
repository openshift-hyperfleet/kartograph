"""Bundled deterministic instance generator scripts for sticky session workspaces."""

from pathlib import Path

TEMPLATES_DIR = Path(__file__).resolve().parent

TEMPLATE_SCRIPT_NAMES = (
    "data_source.py",
    "folder.py",
    "source_file.py",
    "json_instances_to_jsonl.py",
    "json_relationships_to_jsonl.py",
    "README.md",
)
