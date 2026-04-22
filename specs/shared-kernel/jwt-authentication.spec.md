# JWT Authentication

## Purpose
Kartograph authenticates users via JWT tokens issued by an external OIDC provider (e.g., Keycloak). The system validates token signatures, enforces audience and issuer constraints, and extracts user identity from standard claims.

## Requirements

### Requirement: Token Validation
The system SHALL validate JWT tokens using JWKS keys fetched from the OIDC provider's discovery endpoint.

#### Scenario: Valid token
- GIVEN a JWT signed with RS256 by the configured OIDC provider
- WHEN the token has a valid signature, audience, issuer, and is not expired
- THEN the token is accepted
- AND the `sub` claim is extracted as the user identity

#### Scenario: Expired token
- GIVEN a JWT that has passed its `exp` claim
- WHEN the token is validated
- THEN validation fails with an invalid token error

#### Scenario: Wrong audience
- GIVEN a JWT with an `aud` claim that does not match the configured audience
- WHEN the token is validated
- THEN validation fails

#### Scenario: Wrong issuer
- GIVEN a JWT with an `iss` claim that does not match the configured issuer
- WHEN the token is validated
- THEN validation fails

#### Scenario: Invalid signature
- GIVEN a JWT signed with a key not in the provider's JWKS
- WHEN the token is validated
- THEN validation fails

### Requirement: User Identity Extraction
The system SHALL extract user identity from JWT claims.

#### Scenario: Standard claims
- GIVEN a valid JWT with `sub` and `preferred_username` claims
- WHEN the token is validated
- THEN the `sub` claim is used as the user ID
- AND the `preferred_username` claim is used as the username

#### Scenario: Missing username claim
- GIVEN a valid JWT without a `preferred_username` claim
- WHEN the token is validated
- THEN the `sub` claim is used as both the user ID and username

#### Scenario: Missing subject claim
- GIVEN a JWT without a `sub` claim
- WHEN the token is validated
- THEN validation fails

### Requirement: JWKS Caching
The system SHALL cache JWKS keys to avoid fetching them on every request.

#### Scenario: Cache hit
- GIVEN JWKS keys were fetched within the cache TTL (default 24 hours)
- WHEN a token is validated
- THEN cached keys are used without an HTTP request to the provider

#### Scenario: Cache expired
- GIVEN JWKS keys were fetched more than the cache TTL ago
- WHEN a token is validated
- THEN fresh keys are fetched from the provider

#### Scenario: Concurrent requests during refresh
- GIVEN multiple requests arriving while the cache is being refreshed
- WHEN JWKS keys are fetched
- THEN only one fetch occurs (lock prevents duplicate requests)

### Requirement: Authentication Priority
The system SHALL prioritize JWT Bearer tokens over API keys.

#### Scenario: Both credentials provided
- GIVEN a request with both an `Authorization: Bearer` header and an `X-API-Key` header
- WHEN the request is authenticated
- THEN the Bearer token is used
- AND the API key is ignored

#### Scenario: Invalid Bearer token with API key present
- GIVEN a request with an invalid Bearer token and a valid API key
- WHEN the request is authenticated
- THEN authentication fails immediately (Bearer is not silently skipped)

#### Scenario: No credentials
- GIVEN a request with no authentication headers
- WHEN the request is authenticated
- THEN a 401 response is returned
