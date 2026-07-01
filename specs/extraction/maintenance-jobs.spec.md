# Maintenance Jobs

## Purpose
Knowledge-graph maintenance keeps the graph aligned with upstream Git sources after the
last extraction baseline. Maintenance uses **by-files** extraction jobs only: changed files
since `last_extraction_baseline_commit` are discovered across all connected data sources,
batched by `files_per_job`, and executed through the OpenShell extraction job runtime with
diff-aware agent prompts.

Maintenance ingest uses `ingest_only` syncs (incremental JobPackages). Maintenance does
**not** run the legacy per-sync AI extraction pipeline.

## Requirements

### Requirement: Changed-File Discovery
The system SHALL discover maintenance work by comparing each Git-backed data source's
`last_extraction_baseline_commit` to its `tracked_branch_head_commit` using the Git compare
API, aggregating changed file paths across all sources on the knowledge graph.

#### Scenario: No commit delta
- GIVEN every connected source has `tracked_branch_head_commit` equal to `last_extraction_baseline_commit`
- WHEN maintenance is triggered
- THEN the run outcome is `no-changes`
- AND no ingest syncs or extraction jobs are created

#### Scenario: Cross-source file totals
- GIVEN sources A, B, and C have 1, 10, and 4 changed files respectively since baseline
- WHEN maintenance jobs are materialized with `files_per_job = 2`
- THEN 8 pending maintenance jobs are created spanning all 15 changed files

### Requirement: Maintenance Ingest
The system SHALL prepare incremental ingestion context for every source with a commit delta
using `pipeline_mode = ingest_only` and baseline `last_extraction_baseline_commit`.

#### Scenario: Ingest without legacy extraction
- GIVEN maintenance is triggered for sources with commit deltas
- WHEN ingest syncs complete
- THEN each sync run reaches `ingested` without `JobPackageProduced` extraction
- AND latest prepared JobPackages contain only incremental file changes

### Requirement: Maintenance Job Materialization
The system SHALL materialize pending extraction jobs under job set name `maintenance` using
strategy `by_files`, ignoring configured `by_instances` job sets.

#### Scenario: Job batching
- GIVEN changed files are resolved to prepared JobPackage paths
- WHEN jobs are materialized with `files_per_job = N`
- THEN each job receives at most `N` target files
- AND jobs are named under the `maintenance` job set

### Requirement: Maintenance Agent Prompt
The system SHALL provide maintenance extraction jobs with prompts that list assigned changed
files, include available unified diff hunks, and instruct the agent to update the full
knowledge graph (all entity types and relationships) to reflect the changes.

#### Scenario: Diff context in prompt
- GIVEN a maintenance job assigned two modified files with GitHub compare patches
- WHEN the OpenShell runner builds the job prompt
- THEN the prompt names both files and includes their diff content (truncated when necessary)

### Requirement: Maintenance Extraction Execution
The system SHALL execute maintenance jobs through the same OpenShell extraction job worker
pool used by graph-management extraction runs.

#### Scenario: Worker start after materialization
- GIVEN maintenance ingest has completed and jobs are materialized
- WHEN the pipeline advances
- THEN extraction workers are started for the knowledge graph
- AND pending maintenance jobs are claimed by workers

### Requirement: Scheduled Maintenance
The system SHALL execute knowledge-graph maintenance schedules stored on the knowledge graph.

#### Scenario: Daily schedule fires
- GIVEN a knowledge graph has `maintenance_schedule.enabled = true` and `next_run_at` in the past
- WHEN the maintenance scheduler polls
- THEN a maintenance pipeline is triggered for that knowledge graph
- AND `next_run_at` is advanced to the next cron occurrence

### Requirement: Pipeline Orchestration
The system SHALL orchestrate maintenance as: detect deltas → ingest_only syncs → wait for
ingest completion → materialize maintenance jobs → start extraction workers.

#### Scenario: Manual full pipeline
- GIVEN the operator triggers maintenance with `start_extraction = true`
- WHEN ingest syncs finish successfully
- THEN maintenance jobs are materialized and extraction workers start without a separate manual step

#### Scenario: Regenerate prepares sources when needed
- GIVEN changed sources have commit deltas but JobPackages are not yet prepared
- WHEN the operator regenerates maintenance jobs
- THEN the system runs `ingest_only` syncs for those sources
- AND waits for ingest completion
- AND replaces pending maintenance jobs from the refreshed JobPackages

#### Scenario: Ingest failure
- GIVEN any maintenance ingest sync fails
- WHEN the pipeline advances
- THEN the maintenance run outcome is `ingest-failed`
- AND extraction workers are not started

## Traceability
- `src/dev-ui/app/components/graph-management/GraphMaintenanceWorkspace.vue`
- `src/api/management/application/services/maintenance_pipeline_service.py`
- `src/api/infrastructure/management/maintenance_job_materializer.py`
- `src/api/extraction/infrastructure/maintenance_job_prompt.py`
