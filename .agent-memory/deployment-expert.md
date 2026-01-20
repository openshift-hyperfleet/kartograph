# Deployment Expert Memory

## Learnings

### 2026-01-20
- Pattern: Keycloak dev mode (`start-dev --import-realm`) for local development
- Action: Added Keycloak 26.0.5 to compose.yaml with realm auto-import
- Context: OIDC SSO support for Kartograph (AIHCM-131 Step 6)

### 2026-01-20
- Pattern: compose.yaml overlay files for production variants
- Action: Created compose.keycloak.yaml for production Keycloak with Postgres backend
- Context: Air-gapped/production deployments need persistent Keycloak storage
