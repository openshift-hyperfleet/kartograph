"""Prepared JobPackage metadata for sticky session workspace materialization."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PreparedJobPackageSource:
    """One materializable JobPackage snapshot for a data source."""

    package_id: str
    data_source_id: str
    data_source_name: str
    repository_folder: str
