"""Architecture tests for shared_kernel.job_package.

Enforces that the JobPackage shared kernel module:
- Does not import from any bounded context (graph, query, iam, management, etc.)
- Does not import from infrastructure
- Does not import FastAPI or Starlette
- Uses only stdlib and approved shared packages (ulid, structlog)
"""

from pytest_archon import archrule


class TestJobPackageSharedKernelBoundaries:
    """Ensures job_package is properly isolated from bounded contexts."""

    def test_job_package_does_not_import_bounded_contexts(self):
        """shared_kernel.job_package must not import from any bounded context."""
        (
            archrule("job_package_no_bounded_contexts")
            .match("shared_kernel.job_package*")
            .should_not_import(
                "graph*",
                "query*",
                "management*",
                "ingestion*",
                "extraction*",
                "identity*",
                "iam*",
            )
            .check("shared_kernel.job_package")
        )

    def test_job_package_does_not_import_infrastructure(self):
        """shared_kernel.job_package must not import infrastructure layer."""
        (
            archrule("job_package_no_infrastructure")
            .match("shared_kernel.job_package*")
            .should_not_import("infrastructure*")
            .check("shared_kernel.job_package")
        )

    def test_job_package_does_not_import_fastapi(self):
        """shared_kernel.job_package must be framework-agnostic."""
        (
            archrule("job_package_no_fastapi")
            .match("shared_kernel.job_package*")
            .should_not_import("fastapi*", "starlette*")
            .check("shared_kernel.job_package")
        )

    def test_job_package_does_not_import_sqlalchemy(self):
        """shared_kernel.job_package must not depend on SQLAlchemy."""
        (
            archrule("job_package_no_sqlalchemy")
            .match("shared_kernel.job_package*")
            .should_not_import("sqlalchemy*")
            .check("shared_kernel.job_package")
        )
