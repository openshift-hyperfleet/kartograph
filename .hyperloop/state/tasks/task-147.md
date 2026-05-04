---
id: task-147
title: UI Data Source Connection — adapter selection, configuration, credential handling
spec_ref: specs/ui/experience.spec.md@e77913c2cc6d8b719291e2dbb6870519a94d50da
status: in_progress
phase: merge
deps:
- task-146
round: 0
branch: hyperloop/task-147
pr: https://github.com/openshift-hyperfleet/kartograph/pull/621
pr_title: 'feat(ui): add guided data source connection flow with adapter selection
  and credentials'
pr_description: "## What and Why\n\nOnce a knowledge graph exists, users need to connect\
  \ data sources to populate it.\nThis task builds the guided data source setup flow:\
  \ adapter type selection (e.g.,\nGitHub), an adapter-specific configuration form\
  \ with smart defaults, and secure\ncredential handling (plaintext never persisted\
  \ in browser, encrypted server-side).\n\nThis is the primary onboarding path from\
  \ \"I have a KG\" to \"my data is being ingested.\"\n\n## Spec Requirements Satisfied\n\
  \n`specs/ui/experience.spec.md@e77913c2cc6d8b719291e2dbb6870519a94d50da`:\n\n- **Requirement:\
  \ Data Source Connection — Scenario: Adapter type selection**\n  \"user selects\
  \ adapter type first; form adapts to show adapter-specific fields\"\n\n- **Requirement:\
  \ Data Source Connection — Scenario: Connection configuration**\n  \"minimum required\
  \ fields per adapter; system infers defaults where possible\n  (e.g. data source\
  \ name from repo name)\"\n\n- **Requirement: Data Source Connection — Scenario:\
  \ Credential handling**\n  \"credentials encrypted and stored server-side; plaintext\
  \ never persisted in browser\"\n\n- **Requirement: Backend API Alignment — Scenario:\
  \ Resource operations succeed end-to-end**\n  Data source creation: `POST /knowledge-graphs/{kg_id}/data-sources`\n\
  \  Data source listing: `GET /knowledge-graphs/{kg_id}/data-sources`\n\n- **Requirement:\
  \ Backend API Alignment — Scenario: Parent context is preserved**\n  `knowledge_graph_id`\
  \ is always included in create/list requests.\n\n- **Requirement: Interaction Principles\
  \ — Scenario: Mutation feedback**\n  Toast confirms data source creation and connection\
  \ errors.\n\n## Key Design Decisions\n\n- **Flow**: Multi-step wizard (3 steps)\
  \ rendered in a full-page view at\n  `/data/data-sources/new?kg_id={id}`:\n  1.\
  \ **Choose Adapter**: Card grid of available adapters (GitHub, …). Clicking one\n\
  \     advances to step 2.\n  2. **Configure Connection**: Adapter-specific form\
  \ (see below).\n  3. **Review & Save**: Summary of the configuration with \"Save\
  \ and Start Sync\" button.\n- **Adapter form registry**: A `src/ui/data/adapter-forms.ts`\
  \ map from adapter type\n  to field definition (field name, label, type, required,\
  \ placeholder, help text).\n  For GitHub: `repository_url` (required), `access_token`\
  \ (required, type=password),\n  `branch` (optional, default \"main\"), `data_source_name`\
  \ (auto-filled from repo name).\n- **Credential handling**: `access_token` and similar\
  \ secret fields use `type=\"password\"`\n  inputs. The value is sent directly in\
  \ the JSON body of `POST /data-sources` — the\n  backend encrypts it in Vault before\
  \ persisting. The browser never stores the\n  plaintext (no localStorage, no sessionStorage).\n\
  - **Name inference**: A `watch` on `repository_url` extracts the repo name and\n\
  \  pre-populates `data_source_name` (e.g., `github.com/owner/repo` → `repo`).\n\
  - **Credential masking**: After save, the data source detail view shows the token\n\
  \  field as \"••••••••\" with no way to retrieve it (only update/rotate).\n\n##\
  \ What Files Are Affected\n\n- **New**: `src/ui/pages/data/data-sources/new.vue`\n\
  - **New**: `src/ui/components/datasource/AdapterTypeSelector.vue`\n- **New**: `src/ui/components/datasource/GithubAdapterForm.vue`\n\
  - **New**: `src/ui/components/datasource/DataSourceReviewStep.vue`\n- **New**: `src/ui/data/adapter-forms.ts`\n\
  - **New**: `src/ui/composables/useDataSources.ts`\n- **New**: `src/ui/tests/unit/AdapterTypeSelector.test.ts`\n\
  - **New**: `src/ui/tests/unit/GithubAdapterForm.test.ts`\n- **New**: `src/ui/tests/unit/useDataSources.test.ts`\n\
  \n## How to Verify\n\n```bash\nmake instance-up\nsource .instances/$(basename $(pwd))/.env.instance\n\
  cd src/ui && npm run dev\n# 1. Navigate to /data/data-sources/new?kg_id={id}\n#\
  \ 2. Step 1: adapter cards shown; click GitHub → advances to step 2\n# 3. Step 2:\
  \ GitHub-specific form rendered; enter repo URL → name auto-fills\n# 4. Token field\
  \ is password type; value not readable after typing\n# 5. Step 3: Review shows config;\
  \ click Save → data source created, toast appears\n# 6. After save, KG detail page\
  \ shows the new data source in the Data Sources tab\n```\n\nUnit tests:\n```bash\n\
  cd src/ui && npm run test:unit -- datasource\n# AdapterTypeSelector: renders adapters;\
  \ click selects and advances step\n# GithubAdapterForm: name inferred from repo\
  \ URL; required field validation\n# useDataSources: POST includes kg_id; credential\
  \ field not stored in state\n```\n\n## Caveats\n\n- Only the GitHub adapter form\
  \ needs to be built now. Other adapters (Confluence,\n  GitLab, etc.) can be added\
  \ later using the same `adapter-forms.ts` registry\n  pattern.\n- The \"Start Sync\"\
  \ option in step 3 calls `POST /data-sources/{id}/sync/trigger`\n  after creation.\
  \ This begins the sync process. Redirect to the Sync Monitoring\n  view (task-148)\
  \ after triggering.\n- Access tokens submitted via the form are handled by the backend\
  \ Vault integration.\n  Confirm with the Management context team that `POST /data-sources`\
  \ accepts the\n  plaintext token in the request body and encrypts it before storage."
---
