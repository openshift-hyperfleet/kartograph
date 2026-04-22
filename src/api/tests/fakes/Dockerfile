FROM python:3.12-slim

RUN groupadd -r appuser && useradd -r -g appuser appuser

WORKDIR /app

RUN pip install --no-cache-dir fastapi uvicorn python-jose[cryptography] cryptography python-multipart

COPY --chown=appuser:appuser oidc_provider.py .

USER appuser

EXPOSE 8180

CMD ["python", "-m", "uvicorn", "oidc_provider:create_oidc_app", "--factory", "--host", "0.0.0.0", "--port", "8180"]
