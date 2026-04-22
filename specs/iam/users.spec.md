# Users

## Purpose
Users represent authenticated identities in Kartograph. User records are provisioned just-in-time from an external identity provider (OIDC/SSO) on first authentication. The user aggregate is intentionally minimal — it stores only the identity mapping, not permissions or memberships.

## Requirements

### Requirement: Just-In-Time Provisioning
The system SHALL automatically create a local user record on first JWT authentication.

#### Scenario: First login
- GIVEN a user authenticating via JWT for the first time
- WHEN the JWT `sub` claim does not match any existing user
- THEN a new user record is created with the `sub` claim as the user ID
- AND the `preferred_username` claim is stored as the username

#### Scenario: Subsequent login
- GIVEN a user who has previously authenticated
- WHEN the user authenticates again
- THEN the existing user record is returned without modification

### Requirement: Username Synchronization
The system SHALL keep the local username in sync with the identity provider.

#### Scenario: Username changed in SSO
- GIVEN a user whose `preferred_username` has changed in the identity provider
- WHEN the user authenticates
- THEN the local username is updated to match the new value

#### Scenario: Username fallback
- GIVEN a JWT token without a `preferred_username` claim
- WHEN the user is provisioned
- THEN the `sub` claim is used as the username

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
- THEN the second provisioning fails with a database error

### Requirement: Multi-Tenant Access
The system SHALL allow a single user to be a member of multiple tenants.

#### Scenario: Cross-tenant membership
- GIVEN a user provisioned via JWT
- WHEN the user is added as a member of tenants A and B
- THEN the user can access both tenants using the same identity
- AND the active tenant is determined per-request
