.PHONY: all
all:


.PHONY: certs
certs:
	@echo "🔐 [Certificates] Generating self-signed certificates for SpiceDB..."
	@mkdir -p certs
	@if [ ! -f certs/spicedb-cert.pem ] || [ ! -f certs/spicedb-key.pem ]; then \
		openssl req -x509 -newkey rsa:4096 \
			-keyout certs/spicedb-key.pem \
			-out certs/spicedb-cert.pem \
			-days 365 -nodes \
			-subj "/CN=spicedb/O=Kartograph Dev" \
			-addext "subjectAltName=DNS:spicedb,DNS:localhost,IP:127.0.0.1"; \
		chmod 555 certs/spicedb-cert.pem certs/spicedb-key.pem; \
		echo "✓ Certificates generated in certs/"; \
		echo "  → Available for local tests via certs/spicedb-cert.pem"; \
	else \
		echo "✓ Certificates already exist in certs/"; \
	fi

.PHONY: dev
dev: certs
	@echo "🧰 [Development] Starting application containers..."
	docker compose -f compose.yaml build
	docker compose -f compose.yaml -f compose.dev.yaml up -d
	@echo "Done."
	@echo "----------------------------"
	@echo "API Root: http://localhost:8000"
	@echo "API Docs: http://localhost:8000/docs/"
	@echo "----------------------------"

.PHONY: down
down:
	docker compose -f compose.yaml -f compose.dev.yaml down


.PHONY: run
run:
	@echo "🖥 [Non-Development] Starting application containers..."
	docker compose -f compose.yaml build
	docker compose -f compose.yaml up -d
	@echo "Done."
	@echo "----------------------------"
	@echo "API Root: http://localhost:8000"
	@echo "API Docs: http://localhost:8000/docs/"
	@echo "----------------------------"

.PHONY: reload
reload: down run


.PHONY: logs
logs:
	docker compose logs --tail 1000 --follow

.PHONY: docs-export
docs-export:
.PHONY: docs-export
docs-export:
	@echo "📝 Exporting system properties to JSON..."
	cd src/api && uv run python ../../scripts/export_system_properties.py
	@echo "⚙️ Exporting environment variables to JSON..."
	cd src/api && uv run python ../../scripts/export_settings.py
	
.PHONY: docs
docs: docs-export
	@echo "🌐 Starting documentation dev server..."
	cd website && npm i && npm run dev

.PHONY: graph-clear
graph-clear:
	@echo "🗑️  [Graph] Clearing all nodes and edges from graph database..."
	@curl -X DELETE http://localhost:8000/util/nodes -H "Content-Type: application/json" -s | jq '.'
	@echo "✓ Graph cleared"

.PHONY: graph-load
graph-load:
	@if [ -z "$(FILE)" ]; then \
		echo "❌ Error: FILE parameter required"; \
		echo "Usage: make graph-load FILE=path/to/mutations.jsonl"; \
		exit 1; \
	fi
	@if [ ! -f "$(FILE)" ]; then \
		echo "❌ Error: File '$(FILE)' not found"; \
		exit 1; \
	fi
	@echo "📤 [Graph] Loading mutations from $(FILE)..."
	@curl -X POST http://localhost:8000/graph/mutations \
		-H "Content-Type: application/jsonlines" \
		--data-binary @$(FILE) -s | jq '.'
	@echo "✓ Mutations applied"

.PHONY: graph-stats
graph-stats:
	@echo "📊 [Graph] Fetching graph statistics..."
	@echo ""
	@echo "=== Node counts by label (top 20) ==="
	@docker compose exec -T postgres psql -U kartograph -d kartograph -t -c "\
		LOAD 'age'; \
		SET search_path = ag_catalog, \"\$$user\", public; \
		SELECT * FROM cypher('kartograph_graph', \$\$$\$$ \
			MATCH (n) \
			RETURN labels(n), count(n) \
		\$\$$\$$) as (label agtype, node_count agtype) ORDER BY node_count DESC LIMIT 20;"
	@echo ""
	@echo "=== Relationship counts by type (top 20) ==="
	@docker compose exec -T postgres psql -U kartograph -d kartograph -t -c "\
		LOAD 'age'; \
		SET search_path = ag_catalog, \"\$$user\", public; \
		SELECT * FROM cypher('kartograph_graph', \$\$$\$$ \
			MATCH ()-[r]->() \
			RETURN type(r), count(r) \
		\$\$$\$$) as (rel_type agtype, rel_count agtype) ORDER BY rel_count DESC LIMIT 20;"
