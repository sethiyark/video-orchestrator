# Observability

Sources: [`backend/app/observability.py`](../backend/app/observability.py),
[`backend/app/infra/redis.py`](../backend/app/infra/redis.py),
health in [`main.py`](../backend/app/main.py).

## Responsibility

Structured logs, Prometheus scrape, dependency probes. Redis is optional.

## Public surface

`configure_logging("json"|"text")`. JSON: UTC `ts`, level, logger, message,
optional exception.

`GET /metrics` — `prometheus_client`; multiprocess registry if available.

`GET /api/health`: `worker`, `database`, `storage` required `ok`; `redis` and
`temporal` may be `disabled`. Overall `ok` or `degraded`. Also `provider`,
`database` dialect, `approval_required`, `worker_enabled`.

`RedisGateway.ping`: unset URL → `disabled`.

## How it is called

`create_app` calls `configure_logging`. Compose sets `LOG_FORMAT=json`.

## Invariants

Do not log `HF_TOKEN` or S3 secrets. Governor `observability.log_format`
defaults JSON; `LOG_FORMAT` can override.

## Related tests

`test_health_and_system_and_metrics`.

## Known limitations

Grafana is not in Compose. Per-invocation `model_runs` table is not written
on every LLM call yet (schema may exist in control plane; pipeline uses
attempt `provenance` JSON).
