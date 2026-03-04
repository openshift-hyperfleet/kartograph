"""Data source adapter type definitions.

Defines the adapter types that Kartograph supports for data source
integrations. These types are in the shared kernel because both the
Management context (configuration) and the Ingestion context (execution)
need to reference them.
"""

from enum import StrEnum


class DataSourceAdapterType(StrEnum):
    """Supported data source adapter types.

    Each value identifies an adapter implementation in the Ingestion
    bounded context. Additional adapter types will be added as
    adapters are implemented (e.g., GITLAB, JIRA_CLOUD, CONFLUENCE,
    GOOGLE_DOCS, KUBERNETES, SLACK).
    """

    GITHUB = "github"
