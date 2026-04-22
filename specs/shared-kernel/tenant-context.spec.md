# Tenant Context

## Purpose
Tenant context resolution determines which tenant a request operates within. In multi-tenant mode, the caller provides an `X-Tenant-ID` header. In single-tenant mode, the system auto-selects the default tenant and auto-provisions user access.

## Requirements

### Requirement: Multi-Tenant Header Resolution
The system SHALL resolve tenant identity from the `X-Tenant-ID` request header in multi-tenant mode.

#### Scenario: Valid header
- GIVEN a request with a valid ULID in the `X-Tenant-ID` header
- AND the authenticated user has `view` permission on that tenant
- WHEN the tenant context is resolved
- THEN the request proceeds with the specified tenant

#### Scenario: Missing header
- GIVEN a request without an `X-Tenant-ID` header in multi-tenant mode
- WHEN the tenant context is resolved
- THEN the request is rejected with a 400 error

#### Scenario: Invalid ULID format
- GIVEN an `X-Tenant-ID` header with an invalid ULID value
- WHEN the tenant context is resolved
- THEN the request is rejected with a 400 error

#### Scenario: ULID case insensitivity
- GIVEN an `X-Tenant-ID` header with a lowercase ULID
- WHEN the tenant context is resolved
- THEN the ULID is normalized to uppercase
- AND the request proceeds normally

#### Scenario: Unauthorized tenant access
- GIVEN a valid tenant ID for a tenant the user is not a member of
- WHEN the tenant context is resolved
- THEN the request is rejected with a 403 error

### Requirement: Single-Tenant Auto-Selection
The system SHALL auto-select the default tenant when running in single-tenant mode.

#### Scenario: Auto-select default tenant
- GIVEN the system is in single-tenant mode
- AND a request arrives without an `X-Tenant-ID` header
- WHEN the tenant context is resolved
- THEN the default tenant is selected automatically

#### Scenario: Auto-provision member access
- GIVEN a user authenticating for the first time in single-tenant mode
- AND the user does not have `view` permission on the default tenant
- WHEN the tenant context is resolved
- THEN the user is automatically added as a `member` of the default tenant

#### Scenario: Bootstrap admin auto-provision
- GIVEN a user whose username is in the bootstrap admin list
- AND the user does not yet have access to the default tenant
- WHEN the tenant context is resolved
- THEN the user is automatically added as an `admin` of the default tenant

#### Scenario: Default tenant missing
- GIVEN single-tenant mode is enabled but the default tenant does not exist
- WHEN the tenant context is resolved
- THEN the request fails with a 500 error

### Requirement: MCP Authentication
The system SHALL authenticate MCP (Model Context Protocol) requests via API key or Bearer token.

#### Scenario: API key authentication
- GIVEN an MCP request with a valid `X-API-Key` header
- WHEN the request is authenticated
- THEN the tenant is resolved from the API key's tenant scope (no header needed)
- AND the auth context is set for downstream MCP tools

#### Scenario: Bearer token fallback
- GIVEN an MCP request with a Bearer token but no API key
- WHEN the request is authenticated
- THEN the JWT is validated
- AND the tenant is resolved from the `X-Tenant-ID` header

#### Scenario: Authentication failure
- GIVEN an MCP request with no valid credentials
- WHEN the request is authenticated
- THEN a 401 response is returned

#### Scenario: Service unavailability
- GIVEN an MCP request when the authentication backend is unreachable
- WHEN the request is authenticated
- THEN a 503 response is returned
