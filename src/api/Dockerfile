# Build stage - using Red Hat UBI9 Python image
FROM registry.access.redhat.com/ubi9/python-312:9.7-1765181854 AS builder

# Install build dependencies for psycopg2 compilation
USER 0
RUN dnf install -y \
    gcc \
    python3-devel \
    libpq-devel \
    && dnf clean all
USER 1001

# Copy uv binary from official image
COPY --from=ghcr.io/astral-sh/uv:0.9.17 /uv /uvx /bin/

# Enable bytecode compilation and set link mode
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

# Disable Python downloads to use the system interpreter
ENV UV_PYTHON_DOWNLOADS=0

WORKDIR /app

# Install dependencies in a cached layer
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --frozen --no-install-project --no-dev

# Copy application code
COPY . /app/

# Install the project
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev


# Production stage - using Red Hat UBI9 Python image
FROM registry.access.redhat.com/ubi9/python-312:9.7-1765181854
# It is important to use the image that matches the builder, as the path to the
# Python executable must be the same

# Copy uv binary for dev mode support
COPY --from=ghcr.io/astral-sh/uv:0.9.17 /uv /uvx /bin/

# Copy the application from the builder
COPY --from=builder --chown=1001:0 /app /app

# Place executables in the environment at the front of the path
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Use the non-root user to run our application (UID 1001 exists in UBI images)
USER 1001

# Use /app as the working directory
WORKDIR /app

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health').read()" || exit 1

# Run the application with uvicorn
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
