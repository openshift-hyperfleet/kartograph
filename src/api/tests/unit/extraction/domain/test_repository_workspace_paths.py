"""Unit tests for repository workspace folder naming."""

from extraction.domain.repository_workspace_paths import (
    repository_folder_for_data_source,
)


def test_repository_folder_slugifies_data_source_name() -> None:
    folder = repository_folder_for_data_source(
        name="Hyperfleet API",
        data_source_id="01JTESTDATASOURCE00000001",
    )
    assert folder == "hyperfleet-api"


def test_repository_folder_falls_back_to_id_when_name_empty() -> None:
    folder = repository_folder_for_data_source(name="   ", data_source_id="ds-abc")
    assert folder == "ds-abc"
