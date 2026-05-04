---
id: task-138
title: UI Experience — Data Source Connection Flow and Schema Browser Cross-Navigation
spec_ref: specs/ui/experience.spec.md@e77913c2cc6d8b719291e2dbb6870519a94d50da
status: complete
phase: null
deps: []
round: 0
branch: hyperloop/task-138
pr: https://github.com/openshift-hyperfleet/kartograph/pull/608
pr_title: 'feat: implement data source connection guided flow and schema browser cross-navigation'
pr_description: "## What and Why\n\nThis PR implements two groups of requirements\
  \ from `specs/ui/experience.spec.md` that\nare not yet verifiably complete in the\
  \ dev-UI (`src/dev-ui/`):\n\n1. **Data Source Connection guided flow** — the spec\
  \ mandates an adapter-type-first\n   UX (the user selects an adapter type *before*\
  \ filling in connection fields, and the\n   form adapts to show adapter-specific\
  \ required fields). It also requires that credential\n   fields give the user clear\
  \ feedback that secrets are never persisted in the browser.\n\n2. **Schema Browser\
  \ cross-navigation** — when the user is viewing a node or edge type\n   in the Schema\
  \ Browser (`/graph/schema`), they must be able to jump directly to:\n   - the **Query\
  \ Console** (`/query`) with a pre-filled `MATCH` query for that type\n   - the **Graph\
  \ Explorer** (`/graph/explorer`) filtered to that type\n   (The third target — the\
  \ Ontology Editor — is deferred; the Extraction bounded context\n   required for\
  \ agent-assisted ontology work has not yet been implemented, per the\n   AIHCM-174\
  \ spike gate.)\n\n## Spec Requirements Satisfied\n\n### Requirement: Data Source\
  \ Connection (`experience.spec.md` §Data Source Connection)\n\n- **Adapter type\
  \ selection** — user selects adapter type first; form adapts to show\n  adapter-specific\
  \ fields only for the selected type (e.g. `repository_url` +\n  `access_token` for\
  \ GitHub; no irrelevant fields rendered).\n- **Connection configuration** — minimum\
  \ required fields shown with inferred defaults\n  where possible (e.g. data source\
  \ name inferred from repository URL).\n- **Credential handling** — plaintext secrets\
  \ are never persisted in the browser; the\n  form makes this visually clear (e.g.\
  \ password-type inputs, no localStorage writes).\n\n### Requirement: Schema Browser\
  \ (`experience.spec.md` §Schema Browser)\n\n- **Cross-navigation** — each type card/row\
  \ in `/graph/schema` exposes action links:\n  - \"Run Query\" → navigates to `/query?query=MATCH+%28n%3ATypeName%29+RETURN+n+LIMIT+25`\n\
  \  - \"Explore\" → navigates to `/graph/explorer?label=TypeName`\n  (The \"Edit\
  \ Ontology\" link is intentionally omitted until the Ontology Design flow is\n \
  \ unblocked by the Extraction context spike.)\n\n### Requirement: Backend API Alignment\
  \ (`experience.spec.md` §Backend API Alignment)\n\nIncidental fix: verify that the\
  \ Data Sources page passes the correct `knowledge_graph_id`\nparent context when\
  \ creating a data source, matching the backend `POST\n/management/data-sources`\
  \ contract.\n\n## Key Design Decisions\n\n- The adapter-type selector uses an existing\
  \ shadcn/vue `Select` component; it is the\n  first control rendered in the \"Add\
  \ Data Source\" dialog, and subsequent fields are\n  conditionally rendered via\
  \ `v-if=\"selectedAdapterType === 'github'\"` etc.\n- Cross-navigation links in\
  \ the Schema Browser are rendered as icon-buttons (Lucide\n  `Terminal` and `Share2`)\
  \ adjacent to each type label, consistent with the inline-actions\n  interaction\
  \ principle from the spec.\n- URL query params for cross-navigation use the existing\
  \ router conventions already\n  present in `/query/index.vue` (`?query=`) and the\
  \ globals search handler.\n\n## Files / Areas Affected\n\n- `src/dev-ui/app/pages/data-sources/index.vue`\
  \ — adapter-type step in Add dialog\n- `src/dev-ui/app/pages/graph/schema.vue` —\
  \ add cross-navigation action buttons\n- `src/dev-ui/app/components/query/SchemaPanel.vue`\
  \ — if cross-nav lives in the panel\n\n## How to Verify\n\n1. Open `/data-sources`\
  \ → \"Add Data Source\" dialog: confirm the first step is adapter\n   type selection\
  \ and that the form fields change based on the selected type.\n2. Select GitHub\
  \ adapter → fill in a repository URL → confirm the data source name is\n   auto-populated\
  \ from the URL.\n3. Open `/graph/schema` → expand any type → click the \"Run Query\"\
  \ icon → confirm the\n   Query Console opens with a pre-filled `MATCH` query for\
  \ that type.\n4. Click the \"Explore\" icon → confirm the Graph Explorer opens filtered\
  \ to that label.\n\n## Caveats and Follow-up\n\n- Ontology Design scenarios (intent\
  \ description, AI-proposed ontology, re-extraction\n  warning) are explicitly out\
  \ of scope until the Extraction bounded context is\n  implemented (AIHCM-174 spike).\n\
  - Sync Monitoring scenarios (active progress, history, logs, manual trigger) are\n\
  \  explicitly out of scope until the Ingestion bounded context is implemented."
---
