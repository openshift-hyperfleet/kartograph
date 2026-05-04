---
id: task-147
title: "UI Data Source Connection — adapter selection, configuration, credential handling"
spec_ref: "specs/ui/experience.spec.md@e77913c2cc6d8b719291e2dbb6870519a94d50da"
status: not-started
phase: null
deps: [task-146]
round: 0
branch: null
pr: null
pr_title: "feat(ui): add guided data source connection flow with adapter selection and credentials"
pr_description: |
  ## What and Why

  Once a knowledge graph exists, users need to connect data sources to populate it.
  This task builds the guided data source setup flow: adapter type selection (e.g.,
  GitHub), an adapter-specific configuration form with smart defaults, and secure
  credential handling (plaintext never persisted in browser, encrypted server-side).

  This is the primary onboarding path from "I have a KG" to "my data is being ingested."

  ## Spec Requirements Satisfied

  `specs/ui/experience.spec.md@e77913c2cc6d8b719291e2dbb6870519a94d50da`:

  - **Requirement: Data Source Connection — Scenario: Adapter type selection**
    "user selects adapter type first; form adapts to show adapter-specific fields"

  - **Requirement: Data Source Connection — Scenario: Connection configuration**
    "minimum required fields per adapter; system infers defaults where possible
    (e.g. data source name from repo name)"

  - **Requirement: Data Source Connection — Scenario: Credential handling**
    "credentials encrypted and stored server-side; plaintext never persisted in browser"

  - **Requirement: Backend API Alignment — Scenario: Resource operations succeed end-to-end**
    Data source creation: `POST /knowledge-graphs/{kg_id}/data-sources`
    Data source listing: `GET /knowledge-graphs/{kg_id}/data-sources`

  - **Requirement: Backend API Alignment — Scenario: Parent context is preserved**
    `knowledge_graph_id` is always included in create/list requests.

  - **Requirement: Interaction Principles — Scenario: Mutation feedback**
    Toast confirms data source creation and connection errors.

  ## Key Design Decisions

  - **Flow**: Multi-step wizard (3 steps) rendered in a full-page view at
    `/data/data-sources/new?kg_id={id}`:
    1. **Choose Adapter**: Card grid of available adapters (GitHub, …). Clicking one
       advances to step 2.
    2. **Configure Connection**: Adapter-specific form (see below).
    3. **Review & Save**: Summary of the configuration with "Save and Start Sync" button.
  - **Adapter form registry**: A `src/ui/data/adapter-forms.ts` map from adapter type
    to field definition (field name, label, type, required, placeholder, help text).
    For GitHub: `repository_url` (required), `access_token` (required, type=password),
    `branch` (optional, default "main"), `data_source_name` (auto-filled from repo name).
  - **Credential handling**: `access_token` and similar secret fields use `type="password"`
    inputs. The value is sent directly in the JSON body of `POST /data-sources` — the
    backend encrypts it in Vault before persisting. The browser never stores the
    plaintext (no localStorage, no sessionStorage).
  - **Name inference**: A `watch` on `repository_url` extracts the repo name and
    pre-populates `data_source_name` (e.g., `github.com/owner/repo` → `repo`).
  - **Credential masking**: After save, the data source detail view shows the token
    field as "••••••••" with no way to retrieve it (only update/rotate).

  ## What Files Are Affected

  - **New**: `src/ui/pages/data/data-sources/new.vue`
  - **New**: `src/ui/components/datasource/AdapterTypeSelector.vue`
  - **New**: `src/ui/components/datasource/GithubAdapterForm.vue`
  - **New**: `src/ui/components/datasource/DataSourceReviewStep.vue`
  - **New**: `src/ui/data/adapter-forms.ts`
  - **New**: `src/ui/composables/useDataSources.ts`
  - **New**: `src/ui/tests/unit/AdapterTypeSelector.test.ts`
  - **New**: `src/ui/tests/unit/GithubAdapterForm.test.ts`
  - **New**: `src/ui/tests/unit/useDataSources.test.ts`

  ## How to Verify

  ```bash
  make instance-up
  source .instances/$(basename $(pwd))/.env.instance
  cd src/ui && npm run dev
  # 1. Navigate to /data/data-sources/new?kg_id={id}
  # 2. Step 1: adapter cards shown; click GitHub → advances to step 2
  # 3. Step 2: GitHub-specific form rendered; enter repo URL → name auto-fills
  # 4. Token field is password type; value not readable after typing
  # 5. Step 3: Review shows config; click Save → data source created, toast appears
  # 6. After save, KG detail page shows the new data source in the Data Sources tab
  ```

  Unit tests:
  ```bash
  cd src/ui && npm run test:unit -- datasource
  # AdapterTypeSelector: renders adapters; click selects and advances step
  # GithubAdapterForm: name inferred from repo URL; required field validation
  # useDataSources: POST includes kg_id; credential field not stored in state
  ```

  ## Caveats

  - Only the GitHub adapter form needs to be built now. Other adapters (Confluence,
    GitLab, etc.) can be added later using the same `adapter-forms.ts` registry
    pattern.
  - The "Start Sync" option in step 3 calls `POST /data-sources/{id}/sync/trigger`
    after creation. This begins the sync process. Redirect to the Sync Monitoring
    view (task-148) after triggering.
  - Access tokens submitted via the form are handled by the backend Vault integration.
    Confirm with the Management context team that `POST /data-sources` accepts the
    plaintext token in the request body and encrypts it before storage.
---
