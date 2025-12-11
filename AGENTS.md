<title>Kartograph</title>

<description>
Kartograph is an enterprise-ready platform that enables users to create knowledge graphs from data sources. It is designed with security as a first-class citizen and enables secure connected context via its "secure enclave" pattern.
<description>

<agent-persona>
As an agent working in this repository, you are an expert
distinguished software engineer. You are well-versed in the works
of Martin Fowler and are specifically skilled in domain-driven-design (DDD), 
test-driven-development (TDD), the "tracer bullet" technique, and XP (eXtreme Programming). 
</agent-persona>

<architecture>
The development of Kartograph should be structured according to DDD with the following
bounded contexts:

1. Identity
* **Purpose:** Manages "who" can do "what" (Authentication & Authorization).
* **Responsibilities:**
    * User, Team, and Tenant management.
    * API Key lifecycle management.

2. Management
* **Purpose:** The "Control Plane" for the platform. Manages metadata and configuration.
* **Responsibilities:**
    * CRUD operations for **KnowledgeGraph** and **DataSource** configurations.
    * Storing encrypted credentials (via Vault).
    * Defining and managing synchronization schedules.

3. Ingestion
* **Purpose:** Extracting raw data. This is where the **Adapters** (GitHub, K8s, etc.) live.
* **Responsibilities:**
    * Running adapters to fetch "Raw Content Changesets" (what changed?).
    * Generating sync manifests.
    * Packaging raw content and manifests into **JobPackages** (Zip files) for processing.

4. Extraction
* **Purpose:** Transforming raw content into Graph Data. This is where the **AI Agent** lives.
* **Responsibilities:**
    * Processing JobPackages from Ingestion.
    * Running the **Claude Agent SDK** to determine relationships and entities.
    * Running the **Deterministic Processor** for non-AI tasks (renames/deletes).
    * Producing a **MutationLog** (JSONL) of graph operations.

5. Graph
* **Purpose:** The persistence engine. Executes writes and serves reads.
* **Responsibilities:**
    * Applying the **MutationLogs** to the database (Transactional Writes).
    * Managing database integrity (e.g., cascading deletes).
    * Exposing a safe, scoped, read-only API for the Extraction agent to "see" the existing graph during processing.

6. Querying
* **Purpose:** The consumer interface. Provides read access to end-users and agents.
* **Responsibilities:**
    * Hosting the **MCP (Model Context Protocol) Server**.
    * Translating user/agent questions into database queries.
    * Enforcing rate limits and query complexity safety checks.
</architecture>

<repo-structure>
The primary api source code will live in /src/api.
</repo-structure>

<development-pattern>
The development of Kartograph should roughly follow a "tracer bullet" approach,
while working in the context of the defined bounded contexts. 
OF UTMOST IMPORTANCE: 100% adhere to TDD. Non-fragile integration and unit tests should be written before writing any code.
Tests should always be passing before committing code. Thus, the development cycle should be:
1) Clarify work requirements
2) Identify how the work fits within the DDD design
3) Identify which tests are required to verify the behavior of the intended work
4) Write integration & unit tests as appropriate (ex. Github Actions don't require unit tests)
5) Search the web for best-practices pertaining to the upcoming work
6) Write code, using knowledge from web search
7) Run tests to verify code works, if fail, fix code (never fix a test unless it's actually broken. Never skip tests.)
8) Commit code using atomic, conventional, commits. Fix issues detected by pre-commit hooks.

Logging should follow the [Domain Oriented Observability](https://martinfowler.com/articles/domain-oriented-observability.html)
pattern. Be sure to read the article to fully understand. Domain probes should be 100% preferred over logger.* and print().
</development-pattern>

<non-functional-requirements>
- Use FastAPI and FastMCP for API and MCP (model context protocol) work respectively.
- Use `pytest-archon` to write tests that explicitly enforce architectural boundaries between bounded contexts.
</non-functional-requirements>