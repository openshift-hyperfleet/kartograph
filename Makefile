.PHONY: all
all:


.PHONY: certs
certs:
	@echo "🔐 [Certificates] Ensuring SpiceDB certificates in Docker volume..."
	@docker volume create kartograph_spicedb_certs > /dev/null 2>&1 || true
	@docker run --rm -v kartograph_spicedb_certs:/certs alpine sh -c "\
		if [ ! -f /certs/spicedb-cert.pem ] || [ ! -f /certs/spicedb-key.pem ]; then \
			apk add --no-cache openssl > /dev/null 2>&1 && \
			openssl req -x509 -newkey rsa:4096 \
				-keyout /certs/spicedb-key.pem \
				-out /certs/spicedb-cert.pem \
				-days 365 -nodes \
				-subj '/CN=spicedb/O=Kartograph Dev' \
				-addext 'subjectAltName=DNS:spicedb,DNS:localhost,IP:127.0.0.1' && \
			chmod 644 /certs/*.pem && \
			echo '✓ Generated new certificates in Docker volume'; \
		else \
			echo '✓ Certificates already exist in Docker volume'; \
		fi"

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


.PHONY: logs
logs:
	docker compose logs --tail 1000 --follow

.PHONY: docs-export
docs-export:
	@echo "📝 Exporting system properties to JSON..."
	cd src/api && uv run python ../../scripts/export-system-properties.py

.PHONY: docs
docs: docs-export
	@echo "🌐 Starting documentation dev server..."
	cd website && npm i && npm run dev
