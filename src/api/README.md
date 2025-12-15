# Kartograph API

## Development

Run the API in development mode with auto-reload:

```bash
docker compose -f compose.yaml -f compose.dev.yaml up --build
```

The development version mounts the `src/api` directory as a volume, so code changes will automatically reload the server.

## Production

Run the API in production mode:

```bash
docker compose up --build
```

## Access

The API will be available at `http://localhost:8000`

API docs: `http://localhost:8000/docs`

MCP server: `http://localhost:8000/query/mcp`

Health check endpoint: `http://localhost:8000/health`
