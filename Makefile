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
	@./scripts/cleanup-openshell-sandboxes.sh
	@HOST_UID=$$(id -u) HOST_GID=$$(id -g) \
		docker compose -f compose.yaml -f compose.dev.yaml --profile build-only build agent-runtime
	@HOST_UID=$$(id -u) HOST_GID=$$(id -g) \
		docker compose -f compose.yaml build
	@HOST_UID=$$(id -u) HOST_GID=$$(id -g) \
		docker compose -f compose.yaml -f compose.dev.yaml --profile ui up -d --force-recreate api
	@HOST_UID=$$(id -u) HOST_GID=$$(id -g) \
		docker compose -f compose.yaml -f compose.dev.yaml --profile ui up -d
	@echo "Done."
	@echo "----------------------------"
	@echo "API Root: http://localhost:8000"
	@echo "API Docs: http://localhost:8000/docs/"
	@echo "Dev UI:   http://localhost:3000"
	@echo "----------------------------"

.PHONY: down
down:
	docker compose -f compose.yaml -f compose.dev.yaml down
	@echo "Stopping Graph Management sticky, worker, and extraction job containers..."
	-@docker ps -aq --filter name=kartograph-sticky- | xargs -r docker rm -f
	-@docker ps -aq --filter name=kartograph-worker- | xargs -r docker rm -f
	-@docker ps -aq --filter name=kartograph-extract- | xargs -r docker rm -f
	-@./scripts/cleanup-openshell-sandboxes.sh

.PHONY: dev-backup dev-restore dev-backup-list dev-repair-age-graphs
dev-backup:
	@./scripts/dev-data-backup.sh backup

dev-restore:
	@./scripts/dev-data-backup.sh restore $(or $(BACKUP),latest)

dev-backup-list:
	@./scripts/dev-data-backup.sh list

dev-repair-age-graphs:
	@./scripts/dev-data-backup.sh repair

.PHONY: kg-backup kg-restore kg-backup-list
kg-backup:
	@test -n "$(KG_ID)" || (echo "Usage: make kg-backup KG_ID=<knowledge-graph-id>" && exit 1)
	@./scripts/kg-data-backup.sh capture "$(KG_ID)"

kg-restore:
	@test -n "$(KG_ID)" || (echo "Usage: make kg-restore KG_ID=<knowledge-graph-id> [BACKUP=latest] [YES=1] [REPLACE=1]" && exit 1)
	@./scripts/kg-data-backup.sh restore "$(KG_ID)" $(or $(BACKUP),latest) $(if $(YES),--yes,) $(if $(REPLACE),--replace,)

kg-backup-list:
	@test -n "$(KG_ID)" || (echo "Usage: make kg-backup-list KG_ID=<knowledge-graph-id>" && exit 1)
	@./scripts/kg-data-backup.sh list "$(KG_ID)"


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


.PHONY: logs
logs:
	docker compose logs --tail 1000 --follow

# --- Isolated instance management (for agents / worktrees) ---

.PHONY: instance-up
instance-up: certs
	@./scripts/dev-instance.sh up --no-keycloak

.PHONY: instance-down
instance-down:
	@./scripts/dev-instance.sh down

.PHONY: instance-status
instance-status:
	@./scripts/dev-instance.sh status

.PHONY: instance-env
instance-env:
	@./scripts/dev-instance.sh env --no-keycloak

# --- Test targets ---

.PHONY: test-unit
test-unit:
	cd src/api && uv run pytest tests/unit -v

.PHONY: test-integration
test-integration:
	cd src/api && uv run pytest tests/integration -v -m integration

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
