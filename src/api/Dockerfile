# Build stage - using Red Hat UBI9 Python image
FROM registry.access.redhat.com/ubi9/python-312@sha256:d7b4607a07e0e831e7ea9a66d91dc39251ae3ce17bad540f2d19e44407073f9b AS builder

# Install build dependencies for psycopg2 compilation
USER 0
RUN dnf install -y \
    gcc \
    python3-devel \
    libpq-devel \
    && dnf clean all
USER 1001

# Copy uv binary from official image
COPY --from=ghcr.io/astral-sh/uv:0.9.18 /uv /uvx /bin/

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


# OpenShell CLI for extraction workload runtime (static binary from GitHub releases).
FROM registry.access.redhat.com/ubi9/ubi-minimal:latest AS openshell

ARG OPENSHELL_VERSION=0.0.83

RUN microdnf install -y ca-certificates gzip tar \
    && curl -fsSL -o /tmp/openshell-x86_64-unknown-linux-musl.tar.gz \
      "https://github.com/NVIDIA/OpenShell/releases/download/v${OPENSHELL_VERSION}/openshell-x86_64-unknown-linux-musl.tar.gz" \
    && curl -fsSL -o /tmp/openshell-checksums-sha256.txt \
      "https://github.com/NVIDIA/OpenShell/releases/download/v${OPENSHELL_VERSION}/openshell-checksums-sha256.txt" \
    && (cd /tmp && grep " openshell-x86_64-unknown-linux-musl.tar.gz$" openshell-checksums-sha256.txt | sha256sum -c -) \
    && tar xzf /tmp/openshell-x86_64-unknown-linux-musl.tar.gz -C /usr/local/bin \
    && chmod 755 /usr/local/bin/openshell \
    && rm -f /tmp/openshell-x86_64-unknown-linux-musl.tar.gz /tmp/openshell-checksums-sha256.txt \
    && microdnf clean all

# Production stage - using Red Hat UBI9 Python image
FROM registry.access.redhat.com/ubi9/python-312@sha256:d7b4607a07e0e831e7ea9a66d91dc39251ae3ce17bad540f2d19e44407073f9b
# It is important to use the image that matches the builder, as the path to the
# Python executable must be the same

# Copy uv binary for dev mode support
COPY --from=ghcr.io/astral-sh/uv:0.9.18 /uv /uvx /bin/

# Copy the application from the builder
USER 0
COPY --from=builder --chown=1001:0 /app /app
COPY --from=openshell /usr/local/bin/openshell /usr/local/bin/openshell
COPY scripts/api-entrypoint-openshift.sh /usr/local/bin/kartograph-api-entrypoint
RUN chmod 755 /usr/local/bin/kartograph-api-entrypoint /usr/local/bin/openshell

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

# Default entrypoint waits for OpenShell when configured; override in compose/dev.
CMD ["/usr/local/bin/kartograph-api-entrypoint"]
