# Local Sandbox Execution

## Purpose
A temporary execution mode for environments where the in-cluster OpenShell Sandbox provider is unavailable (for example, stage before the Agent Sandbox CRD/controller is installed). When enabled, GMA sticky sessions and extraction jobs dispatch Sandbox execution to a local agent running on the requesting user's own machine instead of an in-cluster provider. Sandbox creation, policy application, and teardown are identical to hosted execution — only physical placement differs. "Sandbox" here refers to the same construct existing specs call a sticky container (`extraction/sticky-session-runtime.spec.md`) or extraction job worker container — the OpenShell CLI and this spec use "Sandbox" because that is the literal `openshell sandbox` resource; no new execution substrate is introduced. This mode is meant to be disabled, without code changes to Sandbox lifecycle logic, once hosted execution becomes available.

## Requirements

### Requirement: Local Execution Mode Selection
The system SHALL support a runtime configuration selecting between hosted (in-cluster) and local (user-machine) Sandbox execution per environment.

#### Scenario: Environment configured for local execution
- GIVEN an environment configured for local Sandbox execution
- WHEN a GMA sticky session or extraction job requires a Sandbox
- THEN the system dispatches a local runtime work request instead of creating an in-cluster Sandbox

#### Scenario: Environment configured for hosted execution
- GIVEN an environment configured for hosted Sandbox execution (the default)
- WHEN a GMA sticky session or extraction job requires a Sandbox
- THEN the system creates the Sandbox in-cluster as it does today
- AND no local runtime work request is created

### Requirement: Local Agent Authentication Reuses Existing API Keys
The system SHALL authenticate local agents using the existing Identity-context API key mechanism (`iam/api-keys.spec.md`). The system SHALL NOT introduce a new credential type or issuance flow for local agents.

#### Scenario: Local agent authenticates with an API key
- GIVEN a user has created a standard Kartograph API key
- WHEN their local agent presents that key in the `X-API-Key` header while polling for work
- THEN the request is authenticated as that user, using the same authentication path already used for programmatic API access

#### Scenario: Revoked key stops dispatch
- GIVEN a user revokes their API key (by themselves or via a tenant admin, per `iam/api-keys.spec.md`)
- WHEN their local agent next polls or attempts to claim work using that key
- THEN authentication fails with a 401 response
- AND no work is dispatched to that agent

#### Scenario: No local agent has ever polled
- GIVEN a user has no local agent currently polling for work
- WHEN a GMA sticky session or extraction job for that user would require local dispatch
- THEN the system surfaces an actionable error instructing the user to run and authenticate a local agent
- AND no local runtime work request is created

### Requirement: Local Agent Presence Tracking
The system SHALL track, per user, whether a local agent is currently polling, to distinguish "no agent available" from "agent is slow to claim" when surfacing errors. This is liveness bookkeeping only, not a credential — ownership stays in the Extraction context.

#### Scenario: Presence recorded on poll
- GIVEN a local agent authenticates and polls for work
- WHEN the poll request is received
- THEN the system records the current timestamp as that user's last-seen time

#### Scenario: Absence detected
- GIVEN a user's last-seen time is older than the presence timeout
- WHEN dispatch is attempted for that user
- THEN the system surfaces an actionable "no local agent connected" error immediately, without waiting for the claim timeout

### Requirement: Outbound-Only Local Agent Connectivity
The system SHALL NOT require inbound network connectivity to a user's machine for any part of local execution, including sandbox dispatch and chat turn delivery. The local agent SHALL be the only party that initiates network connections between the hosted API and the local machine.

#### Scenario: Work delivered via long poll
- GIVEN a registered local agent
- WHEN it has no pending work
- THEN it holds an outbound long-poll connection open against the hosted API
- AND the hosted API never initiates a connection to the local agent or to any port on the local agent's host

### Requirement: Local Runtime Work Request Lifecycle
The system SHALL track local runtime work requests through `pending`, `claimed`, `completed`, and `failed` states, scoped to exactly one user, knowledge graph, and session or extraction job. Work requests carry one of three kinds: `sandbox_start`, `chat_turn`, or `sandbox_stop`.

#### Scenario: Claim by polling agent
- GIVEN a pending local runtime work request for a user
- WHEN that user's local agent polls for work
- THEN the request transitions to `claimed`
- AND is not offered to any other polling connection

#### Scenario: Claim revalidates authorization
- GIVEN a pending local runtime work request tied to a knowledge graph
- WHEN a local agent claims it
- THEN the system re-checks that the authenticated user still holds edit permission on that knowledge graph, the same SpiceDB check already enforced on session and job endpoints
- AND rejects the claim with a failed request if that permission no longer holds, even if it held when the request was created

#### Scenario: Claim timeout
- GIVEN a pending local runtime work request
- WHEN no registered agent for that user claims it within the claim timeout
- THEN the request transitions to `failed`
- AND the originating session or job surfaces an actionable timeout error

#### Scenario: Heartbeat loss fails the claim
- GIVEN a claimed local runtime work request
- WHEN the claiming agent stops sending heartbeats past the heartbeat timeout
- THEN the request transitions to `failed`
- AND the originating session or job is notified so its caller can create a new work request or surface the failure to the user

### Requirement: Unchanged Sandbox Lifecycle Semantics
The system SHALL create, apply policy to, and tear down local Sandboxes using the same operations used for hosted execution (`sandbox.py`, `policy.py`), differing only in which OpenShell gateway/provider they target. This requirement governs sandbox lifecycle only; chat turn delivery is governed separately below, since it uses a different transport for local execution.

#### Scenario: Same sandbox image and policy
- GIVEN a local runtime work request of kind `sandbox_start` is claimed
- WHEN the local agent starts the Sandbox
- THEN it uses the same sandbox image, OpenShell policy file, and enforcement mode that hosted execution would have used for the same session mode or job type

### Requirement: Chat Turn Relay Through the Local Agent
For local sticky sessions, the system SHALL deliver chat turns to the Sandbox by dispatching a `chat_turn` work request to the local agent already running that session's Sandbox, rather than the hosted API calling the Sandbox's forwarded port directly. The local agent SHALL perform the direct call to its own local Sandbox (both are on the same machine) and return the complete response as the work request's result.

#### Scenario: Turn delivered without inbound reachability
- GIVEN a GMA sticky session with a Sandbox running on a user's local agent
- WHEN the user sends a chat message
- THEN the system creates a `chat_turn` work request instead of calling `runtime_base_url` directly
- AND the local agent claims it, calls its own local Sandbox's forwarded port, and submits the assistant's complete response as the work request's result

#### Scenario: Buffered response, not streamed
- GIVEN a `chat_turn` work request is being processed by a local agent
- WHEN the Sandbox produces its response
- THEN the hosted API receives the complete response once the local agent submits it
- AND token-by-token streaming to the end user is not available for local execution (an accepted limitation of this temporary mode; see Known Limitations)

### Requirement: Local Execution Always Requests Hard Landlock Enforcement
The system SHALL request `hard_requirement` Landlock enforcement for every local Sandbox, regardless of the `soft`/`hard_requirement` setting used elsewhere, and SHALL treat any policy-apply failure as a failed work request rather than proceeding with degraded enforcement.

#### Scenario: Policy apply fails closed
- GIVEN a local agent's host cannot satisfy `hard_requirement` Landlock enforcement
- WHEN it claims a `sandbox_start` work request and applies policy
- THEN the underlying OpenShell policy-apply call fails
- AND the local agent reports the work request as `failed`
- AND does not start the Sandbox with softened enforcement

#### Scenario: Policy apply succeeds
- GIVEN a local agent's host satisfies `hard_requirement` Landlock enforcement
- WHEN it claims a `sandbox_start` work request
- THEN policy apply succeeds and the Sandbox starts normally

### Requirement: Downscoped, Short-Lived Vertex Credential Injection
For local execution, the system SHALL mint a Google Cloud access token scoped by both a short lifetime (matched to expected run duration) and a Credential Access Boundary restricting usable permissions to Vertex AI inference calls only, instead of transmitting the long-lived Vault-backed service account credential material. The system SHALL inject the minted token into the local Sandbox via the OpenShell `google-vertex-ai` provider's `service_account_token` credential (verified to accept a bearer token directly, with no private key or refresh material, via `openshell provider profile export google-vertex-ai`).

#### Scenario: Token minted per dispatch
- GIVEN a local runtime work request of kind `sandbox_start` is claimed
- WHEN the local agent requests Vertex credentials for the Sandbox
- THEN the hosted API mints an access token restricted by a Credential Access Boundary to Vertex AI inference permissions, with a lifetime matched to expected run duration
- AND the underlying service-account private key material never leaves the cluster

#### Scenario: Token expiry ends access
- GIVEN a minted Vertex access token has reached its expiry
- WHEN the local Sandbox attempts further Vertex calls
- THEN the calls fail authentication
- AND no refresh capability is available to the local Sandbox

### Requirement: Session and Job Waiting Visibility
The system SHALL surface a distinct waiting state while local runtime work is pending or claimed. For sessions, this is recorded directly on the session. For extraction jobs, this is derived by joining to the associated work request without changing the job's own status enum.

#### Scenario: Waiting state shown for a session
- GIVEN a GMA session has dispatched a local runtime work request
- WHEN the user views session status before the local agent claims it
- THEN the session's `runtime_context.local_runtime` reports a `waiting_for_local_runner` phase

#### Scenario: Waiting state shown for a job
- GIVEN an extraction job has dispatched a local runtime work request
- WHEN the user views job status before the local agent claims it
- THEN the job's own status remains `pending`
- AND the job status read path additionally reports `waiting_for_local_runner` derived from the associated work request

#### Scenario: Claim timeout surfaced
- GIVEN a local runtime work request times out unclaimed
- WHEN the user views session or job status
- THEN the status reflects the failure with an actionable message referencing local agent connectivity

### Requirement: Reversible Without Sandbox Code Changes
Disabling local execution mode SHALL require only a runtime configuration change, not changes to Sandbox lifecycle code.

#### Scenario: Revert to hosted mode
- GIVEN local execution mode is disabled after having been enabled
- WHEN a GMA sticky session or extraction job next requires a Sandbox
- THEN it is created in-cluster using the existing hosted adapter
- AND the local-runtime adapter module is not invoked (verified by an architectural boundary test, in the style of the existing `pytest-archon` bounded-context tests)

## Data Model

- `local_runtime_agent_presence`: `user_id` (String(255), primary key), `tenant_id` (String(26)), `last_seen_at` (timestamptz). Upserted on every poll. Liveness bookkeeping only — not a credential; owned by Extraction.
- `local_runtime_work_requests`: `id` (String(26), ULID, primary key), `tenant_id` (String(26)), `user_id` (String(255)), `knowledge_graph_id` (String(26)), `session_id` (String(26), nullable), `job_id` (String(26), nullable), `kind` (String(32), `CHECK kind IN ('sandbox_start','chat_turn','sandbox_stop')`), `status` (String(16), `CHECK status IN ('pending','claimed','completed','failed')`), `payload` (JSONB, not null, default `'{}'`), `result` (JSONB, nullable), `failure_reason` (String, nullable), `claimed_by_user_id` (String(255), nullable — the claiming agent is always the same user the request is scoped to; recorded for audit), `claimed_at` (timestamptz, nullable), `heartbeat_at` (timestamptz, nullable), `completed_at` (timestamptz, nullable), `credential_expires_at` (timestamptz, nullable), `created_at`, `updated_at` (timestamptz, not null).

Indexes: composite `(user_id, status)` for the long-poll query; `(session_id, status)` and `(job_id, status)` for read-path status derivation.

## Write Paths
- `ExtractionAgentSessionService` and extraction job dispatch write a `local_runtime_work_requests` row of kind `sandbox_start` (via a new local-execution implementation of the existing `IStickySessionRuntimeManager` / `IExtractionJobRunner` ports — see Traceability) instead of calling the in-cluster OpenShell provider, when local execution mode is configured.
- `RemoteStickyContainerChatAgent`'s local-execution counterpart writes a `chat_turn` work request per user message instead of calling `runtime_base_url` directly.
- The local agent's poll endpoint upserts `local_runtime_agent_presence` on every call, and updates `local_runtime_work_requests` on claim, heartbeat, and completion/failure.
- A new Vertex token-minting endpoint, structurally analogous to `workload_credential_issuer.py` but minting Google Cloud access tokens via Credential Access Boundary rather than Kartograph-signed JWTs, is called when a `sandbox_start` request is claimed.
- `ExtractionAgentSession.runtime_context` gains a `local_runtime` key (parallel to the existing `sticky_runtime` key) recording phase and work request id.

## Read Paths
- Session status reads surface `waiting_for_local_runner` and failure/timeout states from `ExtractionAgentSession.runtime_context.local_runtime`.
- Extraction job status reads join to `local_runtime_work_requests` by `job_id` to derive `waiting_for_local_runner` without altering `ExtractionJobRecord.status`.
- The local agent's long-poll endpoint reads `local_runtime_work_requests` filtered to `status = 'pending' AND user_id = <authenticated user>`.

## Authorization (SpiceDB)
Local agents authenticate via existing API keys (`iam/api-keys.spec.md`), which already resolve to the key's creator through existing authentication middleware — no new authentication mechanism. Authorization of *what that user can do* reuses the existing SpiceDB knowledge-graph edit-permission check already enforced on session and job endpoints (for example `_assert_kg_edit_permission`): this check runs again at claim time (see "Claim revalidates authorization"), not merely at work-request creation time, so a permission revoked after creation blocks the claim. No new SpiceDB relations are introduced; `local_runtime_work_requests.user_id` is used only to route which pending requests a given poller may see, never as the sole authorization decision.

## Migration Plan
- New tables only (`local_runtime_agent_presence`, `local_runtime_work_requests`); no new columns on `extraction_agent_sessions` beyond the additive `runtime_context.local_runtime` key, which existing readers already treat as an open dict.
- `ExtractionJobRecord`'s `status` enum is unchanged; the waiting-for-local-runner signal is derived by joining to `local_runtime_work_requests`, not by adding a new job status value.
- Existing consumers (`ExtractionAgentSessionService`, extraction job dispatch, `RemoteStickyContainerChatAgent`) select the local adapter via the existing `ExtractionWorkloadRuntimeSettings` pattern (a new backend value), so hosted-mode consumers are unaffected when local execution mode is not configured.
- No changes required to `sandbox.py`, `policy.py`, or `gateway.py` — the local agent invokes them unchanged, pointed at a locally-registered gateway.
- No changes required to `iam/api-keys.spec.md` or its implementation — local agents are ordinary API key holders.

## Known Limitations (accepted for this temporary mode)
- **Landlock enforcement is enforced by OpenShell's own policy-apply failure, not independently attested.** The hosted API has no way to cryptographically verify a local agent's host capability beyond observing whether `openshell policy update` succeeded. A compromised or modified local agent binary could misreport success. Accepted for a temporary bridge; not acceptable for a permanent design.
- **The local agent process itself is unsandboxed** and observes plaintext Vertex tokens before injecting them into the Sandbox. Short TTLs and Credential Access Boundary scoping bound the damage of exfiltration but do not prevent a malicious local agent from re-requesting tokens for the life of a claimed work request. Mitigated by per-mint audit logging and the existing claim/heartbeat lifecycle bounding how long a request stays claimable.
- **Chat turns are delivered as complete, buffered responses, not streamed token-by-token,** since the outbound long-poll transport does not carry a live stream. This degrades perceived responsiveness relative to hosted execution but does not change correctness.
- **No per-purpose scoping exists for API keys used by local agents** — a local agent authenticates with the same permission scope as any other use of that user's API key. Blast radius is bounded by the per-request SpiceDB knowledge-graph permission check, not by the key itself. A dedicated key purpose/scope is a possible future improvement to `iam/api-keys.spec.md`, out of scope here.

## Traceability
- `src/api/extraction/ports/runtime.py`
- `src/api/extraction/infrastructure/openshell/sandbox.py`
- `src/api/extraction/infrastructure/openshell/policy.py`
- `src/api/extraction/infrastructure/openshell/gateway.py`
- `src/api/extraction/infrastructure/openshell/vertex_provider.py`
- `src/api/extraction/infrastructure/remote_sticky_container_chat_agent.py`
- `src/api/extraction/infrastructure/workload_credential_issuer.py` (pattern reference for the new Vertex token issuer — this file itself only mints Kartograph-internal JWTs today and does not gain GCP responsibilities)
- `src/api/extraction/application/agent_session_service.py`
- `specs/iam/api-keys.spec.md` (reused as-is for local agent authentication)
