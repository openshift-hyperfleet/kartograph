# API Keys

## Purpose
API keys provide non-interactive authentication for programmatic access to Kartograph. They are scoped to a tenant, tracked for usage, and support soft revocation for audit trails.

## Requirements

### Requirement: API Key Creation
The system SHALL allow users with `create_api_key` permission on a tenant to generate API keys.

#### Scenario: Successful creation
- GIVEN a user with `create_api_key` permission on a tenant
- WHEN the user creates an API key with a name and expiration
- THEN a key is generated with the `karto_` prefix
- AND the plaintext secret is returned exactly once (never retrievable again)
- AND the key is stored as a bcrypt hash
- AND a 12-character prefix is stored for fast lookup

#### Scenario: Duplicate name per user
- GIVEN a user who already has an API key named "CI Pipeline" in the tenant
- WHEN the user attempts to create another key with the same name
- THEN the request is rejected with a conflict error

#### Scenario: Expiration bounds
- GIVEN a request to create an API key
- WHEN the expiration is set between 1 and 3650 days
- THEN the key is created with the specified expiration
- AND the default expiration is 30 days if unspecified

### Requirement: API Key Authentication
The system SHALL authenticate requests bearing an API key in the `X-API-Key` header.

#### Scenario: Valid key
- GIVEN a valid, non-expired, non-revoked API key
- WHEN a request includes the key in the `X-API-Key` header
- THEN the request is authenticated as the key's creator
- AND the key's `last_used_at` timestamp is updated

#### Scenario: Expired key
- GIVEN an API key that has passed its expiration time
- WHEN a request includes the key
- THEN authentication fails with a 401 response

#### Scenario: Revoked key
- GIVEN a revoked API key
- WHEN a request includes the key
- THEN authentication fails with a 401 response

#### Scenario: JWT takes precedence
- GIVEN a request with both a Bearer token and an `X-API-Key` header
- WHEN the request is authenticated
- THEN the Bearer token is used
- AND the API key is ignored

#### Scenario: Prefix collision
- GIVEN two API keys that share the same 12-character prefix
- WHEN authentication is attempted
- THEN each candidate is checked via bcrypt comparison
- AND an error-level event is logged to alert operators

### Requirement: API Key Listing
The system SHALL allow users to list API keys they have `view` permission on.

#### Scenario: List keys
- GIVEN a user viewing API keys in a tenant
- WHEN the user lists keys
- THEN keys are returned with metadata (name, prefix, created_at, expires_at, last_used_at, is_revoked)
- AND plaintext secrets are never included

#### Scenario: Filter by creator
- GIVEN an optional `user_id` filter
- WHEN the user lists keys with the filter
- THEN only keys created by that user are returned

### Requirement: API Key Revocation
The system SHALL allow key owners and tenant admins to revoke API keys.

#### Scenario: Owner revokes own key
- GIVEN a user who created an API key
- WHEN the user revokes the key
- THEN the key is marked as revoked
- AND the key remains visible in listings with `is_revoked` set to true

#### Scenario: Tenant admin revokes any key
- GIVEN a tenant admin
- WHEN the admin revokes any API key in the tenant
- THEN the key is marked as revoked

#### Scenario: Already revoked
- GIVEN a key that is already revoked
- WHEN a user attempts to revoke it again
- THEN the request is rejected with a conflict error

#### Scenario: Unauthorized revocation
- GIVEN a user who is neither the key's owner nor a tenant admin
- WHEN the user attempts to revoke the key
- THEN the request is rejected with a forbidden error

### Requirement: API Key Cascade Deletion
The system SHALL delete all API keys in a tenant when the tenant is deleted.

#### Scenario: Tenant deletion
- GIVEN a tenant with active API keys
- WHEN the tenant is deleted
- THEN all API keys in the tenant are deleted
- AND authorization relationships are cleaned up

### Requirement: API Key Name Validation
The system SHALL enforce constraints on API key names.

#### Scenario: Valid name
- GIVEN a name between 1 and 255 characters
- WHEN used to create an API key
- THEN the name is accepted

#### Scenario: Empty name
- GIVEN an empty string as key name
- WHEN used to create an API key
- THEN the request is rejected with a validation error
