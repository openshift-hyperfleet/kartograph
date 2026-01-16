# Kartograph Deployment

## Release Flow

```mermaid
sequenceDiagram
    participant Dev as Developer
    participant RP as Release-Please
    participant K as Konflux
    participant Q as Quay
    participant A as ArgoCD

    Dev->>RP: 1. Merge PR (feat:/fix:)
    RP->>Dev: 2. Creates release PR<br/>(bumps version)
    Dev->>RP: 3. Merge release PR
    Note over RP: Creates git tag: 1.0.0
    RP->>K: 4. Tag triggers build
    K->>Q: 5. Push image<br/>:abc123d (commit SHA)
    K->>K: 6. Component-nudge updates<br/>kustomization.yaml
    A->>A: 7. Detects kustomization change
    A->>Q: 8. Deploys using SHA: abc123d
```

## Key Points

- **Conventional commits** (feat:, fix:) trigger version bumps
- **Git tags** trigger Konflux builds (NOT every commit to main)
- **Image tag**: `abc123d` (commit SHA from the tagged release)
- **Kustomization**: Auto-updated by component-nudge after each build
- **Version tracking**: Git tag `1.0.0` points to commit `abc123d`
- **Images location**: `quay.io/redhat-user-workloads/kartograph-tenant/kartograph-api`

## Files Updated Automatically

- `deploy/apps/kartograph/overlays/stage/kustomization.yaml` - Konflux updates `newTag` with commit SHA
- `CHANGELOG.md` - Release-please generates changelog
- `src/api/pyproject.toml` - Release-please bumps version
- Git tag (e.g., `1.0.0`) - Release-please creates on merge

## Manual Operations

- Merge release PRs (quality gate before production)
- Emergency rollback (edit kustomization to pin older commit SHA)
