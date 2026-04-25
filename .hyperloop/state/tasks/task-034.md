---
id: task-034
title: Implement Fernet credential key rotation without re-encryption
spec_ref: specs/management/credentials.spec.md@774c6c8e
status: not-started
phase: null
deps: []
round: 0
branch: null
pr: null
---

## Context

`specs/management/credentials.spec.md` requires that the credential store support key
rotation **without re-encrypting existing credentials**. The current `FernetSecretStore`
(in `management/infrastructure/repositories/`) uses a single Fernet key derived from a
composite of `(path, tenant_id)`. When the platform operator rotates the encryption
key, existing credentials can no longer be decrypted — violating the spec.

The spec explicitly requires:
> The system SHALL support key rotation without requiring re-encryption of existing
> credentials.

This is a distinct feature from the cascade-deletion bug tracked in task-019.

## What to implement

1. Extend the `ISecretStoreRepository` port (or the `FernetSecretStore` implementation)
   to support **versioned keys**: a current key (for encryption) plus an ordered list
   of previous keys (for decryption fallback).

2. On `store()`: always encrypt with the current key version, prefixing the ciphertext
   with the key version identifier so the correct decryption key can be selected on
   read.

3. On `retrieve()`: extract the key version from the ciphertext prefix; try the
   matching key first, then fall back through previous versions if needed.

4. Configuration: read the current key and previous keys from settings (e.g.,
   `SECRET_KEY` and `SECRET_KEY_PREVIOUS` env vars, or a list).

5. Add unit tests:
   - Credentials encrypted with old key are readable after key rotation.
   - Credentials encrypted with new key are readable.
   - Unknown key version raises a clear error.

6. No migration or re-encryption of existing credentials is required.

## Acceptance criteria

- After rotating the key, credentials stored before rotation are still retrievable.
- New credentials use the new key.
- The implementation does not require any database migration or re-encryption job.
- Unit tests cover old-key read, new-key write/read, and unknown-version error.
