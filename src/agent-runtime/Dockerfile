FROM registry.access.redhat.com/ubi9/python-312:latest

WORKDIR /runtime

COPY --from=ghcr.io/astral-sh/uv:0.9.18 /uv /uvx /bin/

COPY pyproject.toml uv.lock /runtime/
COPY kartograph_agent_runtime /runtime/kartograph_agent_runtime

RUN uv sync --frozen --no-dev

ENV PATH="/runtime/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1

EXPOSE 8787

HEALTHCHECK --interval=15s --timeout=3s --start-period=10s --retries=5 \
  CMD /runtime/.venv/bin/python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8787/health').read()" || exit 1

CMD ["/runtime/.venv/bin/python", "-m", "kartograph_agent_runtime"]
