FROM python:3.12-slim

WORKDIR /app

RUN pip install --no-cache-dir fastapi uvicorn python-jose[cryptography] cryptography

COPY oidc_provider.py .

EXPOSE 8180

CMD ["python", "-m", "uvicorn", "oidc_provider:create_oidc_app", "--factory", "--host", "0.0.0.0", "--port", "8180"]
