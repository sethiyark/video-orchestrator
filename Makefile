.PHONY: setup dev dev-api dev-ui test worker dashboard lint format render-sample run-sample-pipeline demo-script test-llm

setup:
	cd backend && uv sync --group dev
	cd frontend && npm ci

# API :8091 and dashboard :3091. Ctrl+C stops both.
dev:
	@echo "API        http://127.0.0.1:8091/docs"
	@echo "Dashboard  http://127.0.0.1:3091"
	@trap 'kill 0' INT TERM EXIT; \
	(cd backend && uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8091) & \
	(cd frontend && npm run dev) & \
	wait

dev-api:
	cd backend && uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8091

dev-ui:
	cd frontend && npm run dev

test:
	cd backend && uv run pytest
	cd backend && uv run ruff check app tests migrations
	cd backend && uv run ruff format --check app tests migrations
	cd frontend && npm run typecheck

lint:
	cd backend && uv run ruff check app tests migrations
	cd frontend && npm run typecheck

format:
	cd backend && uv run ruff format app tests migrations
	cd frontend && npm run format

worker:
	cd backend && TEMPORAL_TARGET=$${TEMPORAL_TARGET:-127.0.0.1:7233} uv run python -m app.orchestrator.worker

dashboard: dev-ui

render-sample:
	@echo "Phase 6: Remotion sample render is not implemented yet"

run-sample-pipeline:
	@echo "Phase 3–7: DNS sample pipeline is not implemented yet"

demo-script:
	@echo "Phase 3: demo-script is not implemented yet"

test-llm:
	@echo "Phase 2: make test-llm is not implemented yet"
