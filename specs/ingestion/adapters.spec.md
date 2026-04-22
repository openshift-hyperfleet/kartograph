# Adapters

## Purpose
Adapters connect Kartograph to external data sources. Each adapter implements a common extraction port, handles source-specific pagination and authentication, and produces raw content for packaging into a JobPackage. The adapter framework is dlt (data load tool), used for its Extract phase only.

## Requirements

### Requirement: Adapter Port
The system SHALL define a common adapter interface that all data source adapters implement.

#### Scenario: Extract contract
- GIVEN an adapter for a specific data source type (e.g., GitHub)
- THEN it implements the `IDatasourceAdapter` port
- AND the extract method accepts credentials and checkpoint state
- AND it returns raw extracted data and updated checkpoint state

#### Scenario: Domain isolation
- GIVEN the adapter port definition
- THEN it lives in the Ingestion domain layer
- AND the domain layer does not import dlt or any adapter framework

### Requirement: GitHub Adapter
The system SHALL support GitHub repositories as a data source.

#### Scenario: Repository tree extraction
- GIVEN a GitHub data source with valid credentials
- WHEN an extraction is triggered
- THEN the adapter fetches the repository tree via the GitHub Trees API
- AND identifies files that have been added or modified since the last sync

#### Scenario: Content fetching
- GIVEN files identified as changed
- WHEN content is fetched
- THEN the adapter retrieves raw file content via the GitHub API
- AND only changed files are fetched (not the entire repository)

#### Scenario: Incremental sync via checkpoint
- GIVEN a previous checkpoint state (e.g., a commit SHA)
- WHEN the adapter runs
- THEN it extracts only changes since the checkpoint
- AND updates the checkpoint with the current position

#### Scenario: Full refresh
- GIVEN no previous checkpoint state (or a full_refresh sync mode)
- WHEN the adapter runs
- THEN it extracts all content from the repository

#### Scenario: Credential handling
- GIVEN encrypted credentials stored by the Management context
- WHEN the adapter runs
- THEN plaintext credentials are retrieved via the `ICredentialReader` shared kernel port
- AND the adapter receives decrypted credentials at runtime
- AND the adapter uses them for data source API authentication

### Requirement: Pluggable Credential Backend
The system SHALL consume credentials through a shared kernel port, not a specific encryption implementation.

#### Scenario: Port-based credential retrieval
- GIVEN the `ICredentialReader` port in the shared kernel
- WHEN the Ingestion context needs credentials for an adapter
- THEN it retrieves them via the port (not by importing the Management context directly)
- AND the port abstracts the credential backend (Fernet, Vault, or other providers)

#### Scenario: Backend independence
- GIVEN a credential stored via Fernet encryption (current implementation)
- AND a future migration to an external secrets manager (e.g., HashiCorp Vault)
- WHEN the backend changes
- THEN the Ingestion context requires no code changes (port contract unchanged)

### Requirement: dlt Framework Integration
The system SHALL use dlt as the adapter framework, restricted to its Extract phase.

#### Scenario: In-process execution
- GIVEN a sync trigger
- WHEN the adapter runs
- THEN dlt executes in-process as a Python library (no Docker, no subprocess)

#### Scenario: State persistence via database
- GIVEN a Kubernetes deployment with ephemeral pods
- WHEN an adapter needs checkpoint state
- THEN dlt restores state from a dedicated `dlt_internal` database schema
- AND state is persisted back after successful extraction

#### Scenario: Extracted data on disk
- GIVEN a completed dlt extraction
- THEN extracted data is available as files in the pipeline working directory
- AND the JobPackager reads these files to assemble the package
