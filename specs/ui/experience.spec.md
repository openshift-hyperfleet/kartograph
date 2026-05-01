# User Experience

## Purpose
The Kartograph UI enables platform admins and developers to go from "I have a data source" to "I can query a knowledge graph" with minimal friction. The interface is organized around user goals — not bounded contexts — and defaults to exploration for returning users while guiding new users through setup.

## Requirements

### Requirement: Backend API Alignment
The system SHALL successfully complete all resource operations by correctly integrating with the backend REST API.

#### Scenario: Resource operations succeed end-to-end
- GIVEN a user performs any create, read, update, or delete operation via the UI
- WHEN the operation is submitted
- THEN the corresponding backend API call succeeds (2xx response)
- AND the UI reflects the updated state without requiring a manual refresh

#### Scenario: Parent context is preserved
- GIVEN a resource that is scoped to a parent (e.g., a knowledge graph within a workspace)
- WHEN the user creates or lists that resource
- THEN the UI includes the parent context required by the API
- AND the operation succeeds

### Requirement: Navigation Structure
The system SHALL organize navigation around user goals, not internal architecture.

#### Scenario: Primary navigation
- GIVEN an authenticated user
- THEN the sidebar presents navigation grouped as:
  - **Explore** — Query Console, Schema Browser, Graph Explorer, Mutations Console
  - **Data** — Knowledge Graphs, Data Sources (with sync status)
  - **Connect** — API Keys, MCP Integration
  - **Settings** — Workspaces, Groups, Tenants

#### Scenario: Default landing
- GIVEN a returning user with existing knowledge graphs
- WHEN they open Kartograph
- THEN they land on the Explore section (Query Console or home dashboard)

#### Scenario: New user landing
- GIVEN a user with no knowledge graphs
- WHEN they open Kartograph
- THEN they are guided toward the setup flow with a prompt to create their first knowledge graph

### Requirement: Tenant and Workspace Context
The system SHALL provide ambient context for tenant and workspace selection.

#### Scenario: Tenant selector
- GIVEN a user who belongs to multiple tenants
- THEN a tenant selector is available in the sidebar
- AND switching tenants refreshes all data in the UI

#### Scenario: Workspace guidance
- GIVEN a user entering a tenant for the first time
- WHEN no personal workspace exists
- THEN the UI suggests creating one or joining an existing team workspace

### Requirement: Knowledge Graph Creation
The system SHALL guide users through creating a knowledge graph before adding data sources.

#### Scenario: Create knowledge graph
- GIVEN a user in a workspace
- WHEN the user creates a knowledge graph
- THEN they provide a name and description
- AND the knowledge graph is created within the current workspace
- AND the user is prompted to add their first data source

### Requirement: Data Source Connection
The system SHALL provide a guided flow for connecting external data sources to a knowledge graph.

#### Scenario: Adapter type selection
- GIVEN a user adding a data source to a knowledge graph
- WHEN the flow begins
- THEN the user selects an adapter type first (e.g., GitHub)
- AND the form adapts to show adapter-specific fields

#### Scenario: Connection configuration
- GIVEN a selected adapter type (e.g., GitHub)
- WHEN the user configures the connection
- THEN they provide the minimum required fields (e.g., repository URL, access token)
- AND the system infers defaults where possible (e.g., data source name from repo name)

#### Scenario: Credential handling
- GIVEN credentials provided during data source setup
- WHEN the data source is saved
- THEN credentials are encrypted and stored server-side
- AND the plaintext is never persisted in the browser

### Requirement: Ontology Design
The system SHALL support an agent-assisted ontology design flow when connecting a data source.

#### Scenario: Intent description
- GIVEN a user who has connected a data source
- WHEN the connection is saved
- THEN the user is prompted to describe (in free text) what problems or questions they want to solve with this data

#### Scenario: Agent-proposed ontology
- GIVEN a free-text intent description and a connected data source
- WHEN the user submits their intent
- THEN the system performs a lightweight scan of the data source
- AND an AI agent explores the scanned data and proposes an ontology (node types, edge types, properties)
- AND the proposed ontology is presented to the user for review

#### Scenario: Ontology review and approval
- GIVEN a proposed ontology
- WHEN the user reviews it
- THEN they can approve the ontology as-is
- OR iterate by editing individual types and relationships
- AND extraction begins only after the user explicitly approves

#### Scenario: Individual type editing
- GIVEN a proposed or existing ontology
- WHEN the user edits a specific type
- THEN they can modify the label, description, required properties, and optional properties
- AND they can add or remove relationship types
- AND they can specify exact property requirements (e.g., "documentation_page must have source_url")

#### Scenario: Ontology change after initial extraction
- GIVEN a knowledge graph with completed extraction
- WHEN the user modifies the ontology
- THEN the system warns that this will trigger a full re-extraction
- AND the user must confirm before the change is applied

### Requirement: Sync Monitoring
The system SHALL show sync progress and status for each data source.

#### Scenario: Active sync progress
- GIVEN a data source with a sync in progress
- WHEN the user views the data source
- THEN they see the current sync status (ingesting, extracting, applying)
- AND a progress indicator appropriate to the current phase

#### Scenario: Sync history
- GIVEN a data source with completed syncs
- WHEN the user views the data source
- THEN they see a history of sync runs with status (completed, failed), timestamps, and duration

#### Scenario: Sync logs
- GIVEN a sync run (in progress or completed)
- WHEN the user requests logs
- THEN detailed logs for that run are displayed

#### Scenario: Manual sync trigger
- GIVEN a data source the user has manage permission on
- WHEN the user triggers a sync
- THEN a new sync run begins and progress is shown

### Requirement: Get Started Querying (MCP Connection)
The system SHALL make it easy for users to connect AI agents to their knowledge graph via MCP.

#### Scenario: API key creation inline
- GIVEN a user on the MCP integration page who has no active API keys
- WHEN they view the page
- THEN they are prompted to create an API key inline

#### Scenario: Copy-paste connection command
- GIVEN an active API key
- WHEN the user views the MCP integration page
- THEN they see a ready-to-paste configuration snippet for their tool (e.g., Claude Code)
- AND the snippet includes the MCP endpoint URL and API key placeholder
- AND a copy button is provided

#### Scenario: Secret shown once
- GIVEN a newly created API key
- WHEN the key is created
- THEN the plaintext secret is shown exactly once
- AND the user can copy it
- AND the secret is not retrievable after leaving the page

### Requirement: Query Console
The system SHALL provide a Cypher query editor with schema-aware assistance.

#### Scenario: Query editing
- GIVEN the query console
- THEN the editor provides Cypher syntax highlighting, autocomplete based on the current schema, and linting

#### Scenario: Query execution
- GIVEN a Cypher query in the editor
- WHEN the user executes it (button or Ctrl/Cmd+Enter)
- THEN results are displayed as a table with execution time and row count

#### Scenario: Query history
- GIVEN previously executed queries
- THEN the user can browse, re-execute, or insert past queries from a history panel

#### Scenario: Knowledge graph context
- GIVEN a query console
- THEN the user can optionally select a specific knowledge graph to scope queries
- AND when unscoped, queries span all knowledge graphs the user can access in the tenant

### Requirement: Schema Browser
The system SHALL provide a browsable view of the graph ontology.

#### Scenario: Type listing
- GIVEN type definitions exist in the graph
- WHEN the user opens the schema browser
- THEN node types and edge types are listed with search and filtering

#### Scenario: Type detail
- GIVEN a specific type
- WHEN the user expands it
- THEN description, required properties, and optional properties are shown

#### Scenario: Cross-navigation
- GIVEN a type in the schema browser
- THEN the user can navigate directly to the query console (pre-filled query), graph explorer (filtered by type), or ontology editor for that type

### Requirement: Graph Explorer
The system SHALL provide an interactive node browser with neighbor traversal.

#### Scenario: Node search
- GIVEN the graph explorer
- WHEN the user searches by type, name, or slug
- THEN matching nodes are displayed as cards with their properties

#### Scenario: Neighbor exploration
- GIVEN a node in the explorer
- WHEN the user expands its neighbors
- THEN connected nodes and edges are shown with labels and direction
- AND the user can drill into neighbors, building an exploration trail

### Requirement: Mutations Console
The system SHALL provide a JSONL editor for authoring and applying graph mutations directly.

#### Scenario: Empty state
- GIVEN the mutations console with no content loaded
- THEN the user is presented with two primary actions (upload file, open editor) and a set of quick-start templates (Create Node, Create Edge, Update Properties, Delete Entity)
- AND the user can drag and drop a .jsonl, .json, or .ndjson file onto the page to load it

#### Scenario: JSONL editing
- GIVEN the editor is open
- THEN the editor provides JSON syntax highlighting, line numbers, JSONL-aware linting, and autocomplete for mutation operation fields
- AND Ctrl/Cmd+Enter submits the mutations without leaving the editor

#### Scenario: Live preview
- GIVEN content in the editor
- THEN a live preview panel shows the operation count broken down by type (DEFINE, CREATE, UPDATE, DELETE) and any validation warnings
- AND parse errors are surfaced inline in the editor gutter

#### Scenario: File upload
- GIVEN a .jsonl, .json, or .ndjson file
- WHEN the user uploads it via the file picker or drag and drop
- THEN the file content is loaded into the editor
- AND files larger than 5 MB activate large-file mode: editing is disabled, a summary of operation counts is shown, and the user can submit directly

#### Scenario: Knowledge graph selection
- GIVEN the mutations console
- THEN a knowledge graph selector is displayed before the user can submit
- AND the selector lists all knowledge graphs the user has `edit` permission on within the current workspace
- AND no submission is possible until a knowledge graph is selected
- AND the selected knowledge graph is used as the target for the mutation submission

#### Scenario: Submission
- GIVEN valid mutations in the editor and a knowledge graph selected
- WHEN the user clicks Apply Mutations (or presses Ctrl/Cmd+Enter)
- THEN the mutations are submitted to the API scoped to the selected knowledge graph and a floating progress indicator appears in the bottom-right corner
- AND the indicator shows status (submitting / success / failed), operation count, and elapsed time
- AND the indicator persists when the user navigates away from the mutations console
- AND the indicator can be minimized to a compact pill or dismissed after completion

#### Scenario: Submission failure
- GIVEN a failed mutation submission
- THEN the floating indicator shows the error message
- AND the number of operations applied before failure is displayed if any were processed

#### Scenario: Template insertion
- GIVEN a template (quick-start or from the templates panel)
- WHEN the user selects it
- THEN the template content is appended to any existing editor content
- AND the editor is activated if it was not already open

#### Scenario: Deep-link to editor with pre-filled content
- GIVEN a URL with ?view=editor or ?template=<content>
- WHEN the user navigates to /graph/mutations
- THEN the editor is opened automatically
- AND the template parameter content (if present) is inserted into the editor

### Requirement: API Key Management
The system SHALL provide a UI for API key lifecycle management.

#### Scenario: Create key
- GIVEN a user with create_api_key permission
- WHEN they create a key with a name and expiration
- THEN the key is created and the secret is shown once

#### Scenario: List keys
- GIVEN the API keys page
- THEN keys are listed with status (active, expired, revoked), creation date, last used, and expiration

#### Scenario: Revoke key
- GIVEN an active or expired key
- WHEN the user revokes it
- THEN the key is marked revoked and can no longer authenticate

### Requirement: Workspace Management
The system SHALL provide a UI for workspace and member management.

#### Scenario: Create workspace
- GIVEN a user with create_child permission
- WHEN they create a workspace with a name and optional parent
- THEN the workspace is created

#### Scenario: Member management
- GIVEN a workspace the user has manage permission on
- THEN they can add, remove, and change roles for members (users and groups)

### Requirement: Design Language
The system SHALL follow the established Kartograph design language for visual consistency.

#### Scenario: Component library
- GIVEN any UI component
- THEN it uses shadcn/vue (Reka UI) primitives with Tailwind CSS
- AND variants are defined via Class Variance Authority (CVA)
- AND icons use Lucide Vue Next

#### Scenario: Color theme
- GIVEN the Kartograph color palette
- THEN colors are defined as OKLCH CSS custom properties
- AND the primary/brand color is warm amber/orange (`oklch(0.5768 0.2469 29.23)` light, `oklch(0.6857 0.1560 17.57)` dark)
- AND neutral grays form the background, card, and border palette
- AND destructive actions use a coral/red accent
- AND chart/data visualization uses a 5-color palette (amber, blue, purple, yellow, green)

#### Scenario: Typography
- GIVEN any text in the UI
- THEN the system font stack is used (no custom fonts)
- AND body text uses `text-sm` (0.875rem)
- AND section headers use uppercase `text-[11px]` with `tracking-wider`
- AND font weights are limited to regular (400), medium (500), and semibold (600)

#### Scenario: Border radius
- GIVEN any rounded element
- THEN border radius scales from a base of `0.625rem` (10px)
- AND cards use `rounded-xl`, buttons and inputs use `rounded-md`, badges use `rounded-full`

#### Scenario: Elevation
- GIVEN depth/layering
- THEN cards use `shadow-sm` and buttons use `shadow-xs`
- AND depth is minimal — the UI is predominantly flat

### Requirement: Interaction Principles
The system SHALL follow consistent interaction patterns across all pages.

#### Scenario: Progressive disclosure
- GIVEN complex information
- THEN the UI shows a summary by default
- AND detail is revealed on demand (expand, drill-in, sheet)

#### Scenario: Inline actions over navigation
- GIVEN an editable resource (workspace name, group name)
- THEN editing happens in-place or in a side panel
- AND the user is not navigated to a separate edit page

#### Scenario: Copy-to-clipboard
- GIVEN any identifier, configuration snippet, or secret
- THEN a copy button is provided
- AND a toast confirms the copy action

#### Scenario: Mutation feedback
- GIVEN a write operation (create, update, delete)
- THEN a toast notification confirms success or reports failure
- AND validation errors are shown inline on form fields

#### Scenario: Keyboard shortcuts
- GIVEN a power-user action (execute query, focus search)
- THEN a keyboard shortcut is available (Ctrl/Cmd+Enter, /)
- AND the shortcut is discoverable via tooltip or documentation

#### Scenario: Focus indicators
- GIVEN an interactive element receiving focus
- THEN a 3px ring in the primary color at 50% opacity is shown
- AND native outlines are suppressed in favor of the ring

### Requirement: Responsive Design
The system SHALL be usable on desktop and tablet screen sizes.

#### Scenario: Desktop layout
- GIVEN a desktop screen
- THEN the sidebar is visible and collapsible
- AND content uses multi-column layouts where appropriate

#### Scenario: Tablet/mobile layout
- GIVEN a narrow screen
- THEN the sidebar collapses to a sheet overlay
- AND layouts adapt to single-column

### Requirement: Dark Mode
The system SHALL support light and dark color schemes.

#### Scenario: Toggle
- GIVEN the user interface
- THEN a dark mode toggle is available in the header
- AND the preference persists across sessions
