.PHONY: setup system-deps dev dev-api dev-ui dev-local-mac dev-local-cuda test worker dashboard lint format render-sample run-sample-pipeline demo-script test-llm

setup: system-deps
	cd backend && uv sync --group dev --extra llm --extra audio --extra embeddings --extra images
	corepack enable
	cd frontend && corepack prepare && pnpm install --frozen-lockfile

# OS packages Python cannot install: espeak-ng backs Kokoro's phonemizer.
# Installs through Homebrew when present; otherwise prints what to install.
system-deps:
	@if command -v espeak-ng >/dev/null 2>&1; then \
		echo "espeak-ng already installed"; \
	elif command -v brew >/dev/null 2>&1; then \
		brew install espeak-ng; \
	else \
		echo "espeak-ng is missing; install it with your OS package manager (e.g. sudo apt install espeak-ng)"; \
	fi

# API :8091 and dashboard :3091. Ctrl+C stops both.
dev:
	@echo "API        http://127.0.0.1:8091/docs"
	@echo "Dashboard  http://127.0.0.1:3091"
	@trap 'kill 0' INT TERM EXIT; \
	(cd backend && uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8091) & \
	(cd frontend && pnpm dev) & \
	wait

dev-api:
	cd backend && uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8091

dev-ui:
	cd frontend && pnpm dev

# Real local inference with a hardware profile. API :8091 and dashboard :3091.
# Prepare weights first:
#   cd backend && MODEL_CONFIG=config/models.mac.yaml .venv/bin/python -m app.models.cli download all
dev-local-mac:
	@echo "API        http://127.0.0.1:8091/docs  (local, models.mac.yaml)"
	@echo "Dashboard  http://127.0.0.1:3091"
	@trap 'kill 0' INT TERM EXIT; \
	(cd backend && MODEL_CONFIG=config/models.mac.yaml PIPELINE_MODE=local .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8091) & \
	(cd frontend && pnpm dev) & \
	wait

dev-local-cuda:
	@echo "API        http://127.0.0.1:8091/docs  (local, models.cuda-8gb.yaml)"
	@echo "Dashboard  http://127.0.0.1:3091"
	@trap 'kill 0' INT TERM EXIT; \
	(cd backend && MODEL_CONFIG=config/models.cuda-8gb.yaml PIPELINE_MODE=local .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8091) & \
	(cd frontend && pnpm dev) & \
	wait

test:
	cd backend && uv run pytest
	cd backend && uv run ruff check app tests migrations
	cd backend && uv run ruff format --check app tests migrations
	cd frontend && pnpm typecheck

lint:
	cd backend && uv run ruff check app tests migrations
	cd frontend && pnpm typecheck

format:
	cd backend && uv run ruff format app tests migrations
	cd frontend && pnpm format

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
