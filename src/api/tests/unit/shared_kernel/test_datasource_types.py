"""Unit tests for data source adapter types."""

from enum import StrEnum

from shared_kernel.datasource_types import DataSourceAdapterType


class TestDataSourceAdapterType:
    """Tests for DataSourceAdapterType enum."""

    def test_is_str_enum(self):
        """Test that DataSourceAdapterType is a StrEnum."""
        assert issubclass(DataSourceAdapterType, StrEnum)

    def test_has_github_member(self):
        """Test that GITHUB adapter type exists."""
        assert DataSourceAdapterType.GITHUB == "github"

    def test_values_are_lowercase(self):
        """Test that all adapter type values are lowercase strings."""
        for adapter_type in DataSourceAdapterType:
            assert adapter_type.islower()
            assert isinstance(adapter_type, str)

    def test_has_exactly_one_member(self):
        """Test that there is exactly one adapter type defined."""
        assert len(DataSourceAdapterType) == 1
