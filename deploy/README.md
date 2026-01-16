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
    RP->>Dev: 2. Creates release PR<br/>(bumps version, updates kustomization)
    Dev->>RP: 3. Merge release PR
    Note over RP: Creates git tag: 1.0.0
    RP->>K: 4. Tag triggers build
    K->>Q: 5. Push images<br/>:1.0.0<br/>:1.0.0-abc123d
    A->>A: 6. Detects kustomization change
    A->>Q: 7. Deploys using tag 1.0.0
```

## Key Points

- **Conventional commits** (feat:, fix:) trigger version bumps
- **Git tags** trigger Konflux builds (NOT every commit to main)
- **Image tags**: Both `1.0.0` (mutable) and `1.0.0-abc123d` (immutable) created
- **Kustomization**: References `newTag: 1.0.0` (updated by release-please)
- **Rollback**: Change kustomization to specific `1.0.0-abc123d` tag

## Files Updated Automatically

- `deploy/apps/kartograph/overlays/stage/kustomization.yaml` - Release-please updates `newTag`
- `CHANGELOG.md` - Release-please generates changelog
- Git tag (e.g., `1.0.0`) - Release-please creates on merge

## Manual Operations

- Merge release PRs (quality gate before production)
- Emergency rollback (edit kustomization to pin specific SHA tag)
