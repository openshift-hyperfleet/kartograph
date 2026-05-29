# Sticky Session Runtime

## Purpose
Sticky session runtimes host long-lived Claude Agent SDK workloads for Graph Management chat. Each active extraction agent session receives an isolated container with mounted skills, scoped credentials, and optional JobPackage materialization for repository access.

## Requirements

### Requirement: Isolated Sticky Container per Session
The system SHALL run each active graph-management chat session in an isolated container.

#### Scenario: Session-scoped isolation
- GIVEN two users with active sessions on the same knowledge graph
- WHEN both send chat messages
- THEN each session uses a distinct sticky container lease
- AND container labels include session, user, knowledge graph, and mode identifiers

### Requirement: Claude Agent SDK Runtime
The system SHALL host Claude Agent SDK agent instances inside sticky session containers.

#### Scenario: Agent runtime image
- GIVEN a sticky session container starts
- WHEN the container initializes
- THEN it runs an agent runtime process capable of Claude Agent SDK execution
- AND is distinct from ephemeral JobPackage worker containers used for sync extraction

### Requirement: Skills Directory Mount
The system SHALL mount the platform skills directory into sticky session containers.

#### Scenario: Skills available at runtime
- GIVEN a sticky session container starts
- WHEN the agent runtime initializes
- THEN SKILL.md resources from the platform skills directory are readable inside the container

### Requirement: JobPackage Materialization
The system SHALL materialize JobPackage archives into sticky session containers when ingestion context is required.

#### Scenario: Repository files available
- GIVEN JobPackage context is ready for the knowledge graph
- WHEN a sticky container starts or refreshes ingestion context
- THEN manifest, changeset, content, and reconstructed repository files are available under the session work directory
- AND the agent can inspect data-source content without leaving the container

### Requirement: Scoped Runtime Credentials
The system SHALL inject short-lived credentials into sticky session containers using least-privilege tenant and knowledge-graph scope.

#### Scenario: Credential injection at start
- GIVEN a sticky session container is started
- WHEN runtime credentials are issued
- THEN credentials are injected as environment variables or runtime files
- AND credentials are never persisted in mutation logs or session message history
