.PHONY: setup dev test worker dashboard lint format render-sample run-sample-pipeline demo-script test-llm

setup:
	cd backend && uv sync --group dev
	cd frontend && npm ci

dev:
	@echo "Terminal 1: cd backend && uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8091"
	@echo "Terminal 2: cd frontend && npm run dev"
	@echo "Optional stack: docker compose up postgres redis minio temporal temporal-ui"

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

dashboard:
	cd frontend && npm run dev

render-sample:
	@echo "Phase 6: Remotion sample render is not implemented yet"

run-sample-pipeline:
	@echo "Phase 3–7: DNS sample pipeline is not implemented yet"

demo-script:
	@echo "Phase 3: demo-script is not implemented yet"

test-llm:
	@echo "Phase 2: make test-llm is not implemented yet"
