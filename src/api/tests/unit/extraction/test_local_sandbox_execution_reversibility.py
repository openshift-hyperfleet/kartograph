"""Architectural boundary tests for local Sandbox execution reversibility.

specs/extraction/local-sandbox-execution.spec.md, "Reversible Without Sandbox
Code Changes": disabling local execution mode must require only a runtime
configuration change, not changes to Sandbox lifecycle code. These tests
enforce the one-way dependency that makes that true: hosted execution's
adapters and the unchanged Sandbox lifecycle modules (`sandbox.py`,
`policy.py`, `gateway.py`, and the rest of the `openshell` package) never
import anything from `extraction.infrastructure.local_runtime`. The local
runtime package is free to depend on the hosted `openshell` helpers (it
reuses them unchanged, per spec), but nothing on the hosted path may depend
back on `local_runtime`. Only the composition root that selects between
adapters at runtime (`workload_runtime_factory.py`, `dependencies.py`) is
permitted to import both.
"""

from pytest_archon import archrule


class TestHostedSandboxLifecycleNeverImportsLocalRuntime:
    def test_openshell_package_does_not_import_local_runtime(self):
        # Scoped to the `openshell.*` package (trailing dot) rather than a
        # bare `openshell*` prefix, so this does not also sweep up the
        # unrelated sibling module `openshell_extraction_job_runner.py`,
        # which legitimately imports the composition-root factory.
        (
            archrule("openshell_no_local_runtime")
            .match("extraction.infrastructure.openshell.*")
            .should_not_import("extraction.infrastructure.local_runtime*")
            .check("extraction")
        )

    def test_remote_sticky_container_chat_agent_does_not_import_local_runtime(self):
        (
            archrule("remote_chat_agent_no_local_runtime")
            .match("extraction.infrastructure.remote_sticky_container_chat_agent")
            .should_not_import("extraction.infrastructure.local_runtime*")
            .check("extraction")
        )

    def test_container_workload_runtime_does_not_import_local_runtime(self):
        (
            archrule("container_workload_runtime_no_local_runtime")
            .match("extraction.infrastructure.container_workload_runtime")
            .should_not_import("extraction.infrastructure.local_runtime*")
            .check("extraction")
        )

    def test_in_memory_workload_runtime_does_not_import_local_runtime(self):
        (
            archrule("in_memory_workload_runtime_no_local_runtime")
            .match("extraction.infrastructure.workload_runtime")
            .should_not_import("extraction.infrastructure.local_runtime*")
            .check("extraction")
        )

    def test_vertex_inference_token_issuer_does_not_import_local_runtime(self):
        (
            archrule("vertex_inference_token_issuer_no_local_runtime")
            .match("extraction.infrastructure.vertex_inference_token_issuer")
            .should_not_import("extraction.infrastructure.local_runtime*")
            .check("extraction")
        )

    def test_ports_do_not_import_local_runtime(self):
        (
            archrule("ports_no_local_runtime")
            .match("extraction.ports*")
            .should_not_import("extraction.infrastructure.local_runtime*")
            .check("extraction")
        )


class TestLocalRuntimeMayReuseUnchangedSandboxLifecycle:
    def test_local_runtime_may_import_openshell_lifecycle_helpers(self):
        (
            archrule("local_runtime_may_import_openshell")
            .match("extraction.infrastructure.local_runtime*")
            .may_import("extraction.infrastructure.openshell*")
            .check("extraction")
        )
