FROM python:3.12-slim
WORKDIR /app
RUN pip install --no-cache-dir uv==0.11.16
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY app ./app
COPY config ./config
COPY migrations ./migrations
ENV DATABASE_URL=sqlite:////data/jobs.sqlite3
CMD [".venv/bin/uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8091"]
