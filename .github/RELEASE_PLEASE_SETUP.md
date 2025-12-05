# Release Please Setup Instructions

This repository uses [release-please](https://github.com/googleapis/release-please) to automate versioning and releases based on conventional commits.

## Required Setup

### 1. Create a Personal Access Token (PAT)

You need to create a fine-grained Personal Access Token with the following permissions:

1. Go to GitHub Settings → Developer settings → Personal access tokens → Fine-grained tokens
2. Click "Generate new token"
3. Configure:
   - **Token name**: `release-please-kartograph`
   - **Repository access**: Only select repositories → `openshift-hyperfleet/kartograph`
   - **Permissions**:
     - Repository permissions:
       - **Contents**: Read and write
       - **Pull requests**: Read and write
       - **Metadata**: Read-only (automatically included)
4. Generate token and copy it

### 2. Add Token as Repository Secret

1. Go to repository Settings → Secrets and variables → Actions
2. Click "New repository secret"
3. Name: `RELEASE_PLEASE_TOKEN`
4. Value: Paste the PAT you created
5. Click "Add secret"

### 3. Enable Auto-merge

1. Go to repository Settings → General
2. Scroll to "Pull Requests" section
3. Enable "Allow auto-merge"
4. Save changes

### 4. Configure Branch Protection (Optional but Recommended)

1. Go to Settings → Branches
2. Add rule for `main` branch:
   - Require status checks to pass before merging
   - Select your CI checks (pytest, ruff, mypy)
   - Require branches to be up to date before merging

## How It Works

1. Push conventional commits to `main` (e.g., `feat:`, `fix:`, `BREAKING CHANGE:`)
2. Release-please creates/updates a release PR with:
   - Version bump in `src/api/pyproject.toml`
   - Updated `CHANGELOG.md`
3. CI runs on the release PR
4. After CI passes, the PR auto-merges
5. A GitHub release is created with a git tag

## Commit Types → Version Bumps

- `feat:` → MINOR version bump (0.1.0 → 0.2.0)
- `fix:` → PATCH version bump (0.1.0 → 0.1.1)
- `feat!:` or `BREAKING CHANGE:` → MAJOR version bump (0.1.0 → 1.0.0)
- `chore:`, `docs:`, `ci:`, etc. → No version bump (included in next release)
