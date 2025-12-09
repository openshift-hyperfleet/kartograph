.PHONY: all
all: 


.PHONY: dev
dev:
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


.PHONY: docker logs
logs:
	docker compose logs --tail 1000 --follow

