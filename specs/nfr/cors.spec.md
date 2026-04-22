# CORS

NFR: This spec describes cross-origin resource sharing policy for the API.

## Purpose
Kartograph conditionally enables CORS to allow browser-based clients (e.g., the dev UI) to interact with the API from different origins.

## Requirements

### Requirement: Configurable CORS Origins
The system SHALL enable CORS middleware only when allowed origins are configured.

#### Scenario: Origins configured
- GIVEN one or more allowed origins in the CORS configuration
- WHEN a cross-origin request is received from an allowed origin
- THEN the response includes appropriate CORS headers
- AND credentials are allowed
- AND wildcard (`*`) origins MUST NOT be used when credentials are allowed (explicit allowlist only)

#### Scenario: No origins configured
- GIVEN an empty CORS origins configuration
- WHEN the application starts
- THEN CORS middleware is not installed
- AND cross-origin requests receive no CORS headers

### Requirement: CORS Defaults
The system SHALL use permissive defaults for methods and headers when CORS is enabled.

#### Scenario: Default policy
- GIVEN CORS is enabled with configured origins
- THEN all HTTP methods are allowed
- AND all request headers are allowed
