# Credentials

## Purpose
Credentials for external data source connections are encrypted at rest using Fernet symmetric encryption. The system stores encrypted credential blobs keyed by a logical path and tenant, with support for key rotation.

## Requirements

### Requirement: Credential Encryption
The system SHALL encrypt credentials before storing them.

#### Scenario: Store credentials
- GIVEN raw credentials as a key-value dictionary
- WHEN the credentials are stored
- THEN they are encrypted using Fernet symmetric encryption
- AND stored with a composite key of (path, tenant_id)

#### Scenario: Retrieve credentials
- GIVEN stored encrypted credentials
- WHEN the credentials are retrieved by path and tenant
- THEN they are decrypted and returned as the original key-value dictionary

#### Scenario: Credentials not found
- GIVEN a path with no stored credentials
- WHEN retrieval is attempted
- THEN a not-found error is raised

### Requirement: Tenant Isolation
The system SHALL scope credentials by both path and tenant for defense-in-depth isolation.

#### Scenario: Same path, different tenants
- GIVEN credentials stored at path "datasource/abc/credentials" for tenant A
- WHEN tenant B attempts to retrieve credentials at the same path
- THEN the retrieval fails (credentials are scoped to tenant A)

### Requirement: Key Rotation
The system SHALL support encryption key rotation without re-encrypting existing credentials.

#### Scenario: Key rotation
- GIVEN credentials encrypted with an older key
- WHEN the system is configured with a new primary key and the old key as a fallback
- THEN new credentials are encrypted with the new key
- AND existing credentials encrypted with the old key can still be decrypted

### Requirement: Credential Lifecycle
The system SHALL delete credentials when the associated data source is deleted.

#### Scenario: Data source deletion
- GIVEN a data source with stored credentials
- WHEN the data source is deleted
- THEN the associated encrypted credentials are deleted

#### Scenario: Knowledge graph cascade
- GIVEN a knowledge graph with data sources that have credentials
- WHEN the knowledge graph is deleted
- THEN all data sources and their credentials are deleted
