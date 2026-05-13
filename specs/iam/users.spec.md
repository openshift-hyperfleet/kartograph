# Users

## Purpose
Users represent authenticated identities in Kartograph. User records are provisioned just-in-time from an external identity provider (OIDC/SSO) on first authentication. The user aggregate stores identity and profile information synced from the identity provider on each login.

## Requirements

### Requirement: Just-In-Time Provisioning
The system SHALL automatically create a local user record on first JWT authentication, capturing profile claims from the identity provider.

#### Scenario: First login
- GIVEN a user authenticating via JWT for the first time
- WHEN the JWT `sub` claim does not match any existing user
- THEN a new user record is created with the `sub` claim as the user ID
- AND the `preferred_username` claim is stored as the username
- AND the `name` claim is stored as the display name (nullable)
- AND the `email` claim is stored as the email address (nullable)

#### Scenario: Subsequent login (no changes)
- GIVEN a user who has previously authenticated
- AND no profile claims have changed
- WHEN the user authenticates again
- THEN the existing user record is returned without modification

#### Scenario: Subsequent login (profile changed)
- GIVEN a user who has previously authenticated
- AND any of the `preferred_username`, `name`, or `email` claims have changed in the identity provider
- WHEN the user authenticates again
- THEN the local profile fields are updated to match the new values
- AND the updated user record is returned

#### Scenario: Username fallback
- GIVEN a JWT token without a `preferred_username` claim
- WHEN the user is provisioned
- THEN the `sub` claim is used as the username

#### Scenario: Optional profile claims
- GIVEN a JWT token without `name` or `email` claims
- WHEN the user is provisioned
- THEN the corresponding fields are stored as null
- AND the user record is still created successfully

### Requirement: External Identity Format
The system SHALL accept arbitrary external identity formats from the identity provider.

#### Scenario: UUID-format identity
- GIVEN an identity provider that uses UUID-format subject identifiers
- WHEN the user authenticates
- THEN the identifier is stored as-is (not converted to ULID)

### Requirement: Username Uniqueness
The system SHALL enforce global uniqueness of usernames.

#### Scenario: Unique username
- GIVEN a new user with a unique username
- WHEN the user is provisioned
- THEN the user record is created

#### Scenario: Duplicate username
- GIVEN two SSO users with the same `preferred_username`
- WHEN both attempt to authenticate
- THEN the second provisioning fails with a provisioning conflict error
- AND the error does not expose database internals

### Requirement: User Lookup
The system SHALL provide a batch endpoint for resolving user IDs to profile information.

#### Scenario: Batch resolve by IDs
- GIVEN a list of user IDs
- WHEN the caller requests `GET /iam/users?ids={id1},{id2},{id3}`
- THEN the response contains the profile for each user that exists: `id`, `username`, `name`, `email`
- AND IDs that do not match any user are omitted from the response (no error)

#### Scenario: Search by text
- GIVEN a `search` query parameter (e.g., `GET /iam/users?search=alice`)
- WHEN the endpoint is called
- THEN users whose `username`, `name`, or `email` contain the search string (case-insensitive) are returned
- AND results are limited to 20 users
- AND the `search` and `ids` parameters are mutually exclusive

#### Scenario: Empty request
- GIVEN a request with neither `ids` nor `search` parameter
- WHEN the endpoint is called
- THEN a 422 validation error is returned

#### Scenario: Large batch
- GIVEN a request with more than 100 IDs
- WHEN the endpoint is called
- THEN a 422 validation error is returned indicating the maximum batch size

#### Scenario: Authentication required
- GIVEN an unauthenticated request
- WHEN the endpoint is called
- THEN a 401 response is returned

#### Scenario: Tenant scoping
- GIVEN an authenticated user in a tenant
- WHEN they request user profiles
- THEN only users who are members of the same tenant are returned
- AND IDs for users outside the tenant are omitted (treated as not found)

### Requirement: Multi-Tenant Access
The system SHALL allow a single user to be a member of multiple tenants.

#### Scenario: Cross-tenant membership
- GIVEN a user provisioned via JWT
- WHEN the user is added as a member of tenants A and B
- THEN the user can access both tenants using the same identity
- AND the active tenant is determined per-request
