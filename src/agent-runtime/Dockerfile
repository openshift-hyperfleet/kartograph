FROM registry.access.redhat.com/ubi9/python-312:latest

USER 0

WORKDIR /app

COPY --from=ghcr.io/astral-sh/uv:0.9.18 /uv /uvx /bin/

COPY pyproject.toml uv.lock /app/
COPY kartograph_agent_runtime /app/kartograph_agent_runtime

RUN uv sync --frozen --no-dev

# OpenShell sandboxes require a dedicated non-root identity in the image.
RUN groupadd -r -g 65532 sandbox \
    && useradd -r -u 65532 -g sandbox -d /sandbox -s /bin/bash sandbox \
    && mkdir -p /sandbox /workspace \
    && chown sandbox:sandbox /sandbox /workspace \
    && chmod -R a+rX /app

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1

EXPOSE 8787

HEALTHCHECK --interval=15s --timeout=3s --start-period=30s --retries=5 \
  CMD pgrep -f "python -m kartograph_agent_runtime" >/dev/null || exit 1

CMD ["/app/.venv/bin/python", "-m", "kartograph_agent_runtime"]
