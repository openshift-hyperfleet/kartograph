# Contributing

## Development Setup

### System Dependencies

To build dependencies from source (such as `psycopg2`), you'll need the following system packages installed:

**Fedora/RHEL/CentOS:**
```bash
sudo dnf install gcc python3-devel libpq-devel
```

**Ubuntu/Debian:**
```bash
sudo apt-get install gcc python3-dev libpq-dev
```

**macOS:**
```bash
brew install postgresql
```

### Python Environment

Install dependencies using `uv`:

```bash
# Install uv (if not already installed)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Navigate to the API directory
cd src/api

# Install project dependencies
uv sync
```

### Pre-commit Hooks

To ensure coding standards are followed, please install the pre-commit
hooks before beginning development:

```bash
pre-commit install
```

_You can install `pre-commit` with `pip install pre-commit`._