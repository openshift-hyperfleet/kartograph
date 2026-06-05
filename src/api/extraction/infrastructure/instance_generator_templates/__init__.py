"""Bundled instance generator scripts for sticky session workspaces."""

from pathlib import Path

TEMPLATES_DIR = Path(__file__).resolve().parent
EXAMPLES_DIR = TEMPLATES_DIR / "examples"

TEMPLATE_SCRIPT_NAMES = (
    "_entity_scanner.example.py",
    "_relationship_scanner.example.py",
    "entities_to_jsonl.py",
    "relationships_to_jsonl.py",
    "preview_instances.py",
    "scanner_common.py",
    "README.md",
    "PREPOPULATION_WORKFLOW.md",
)

EXAMPLE_SCANNER_NAMES = (
    "test_scanner.example.py",
    "api_endpoint_scanner.example.py",
    "resource_scanner.example.py",
    "adapter_scanner.example.py",
)
