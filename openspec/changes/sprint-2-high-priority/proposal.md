# Proposal: Sprint 2 — High-Priority Operational Maturity

## Intent

Five operational maturity improvements that harden the news ETL pipeline against silent failures and unreproducible builds: (1) enforce an SLA on the load task so data is ready before the 9 AM consumption window (DAG runs at midnight → 9-hour budget), (2) emit structured SLA-miss alerts as parseable JSON lines, (3) lock Python dependencies with pip-tools for reproducible builds, (4) pin `apache-airflow==2.11.2` in requirements to match the base image and prevent transitive version drift, and (5) close the retry gap in NewsAPI extraction by mirroring the proven tenacity pattern from `scrape.py`.

## Scope

### In Scope
- `sla=timedelta(hours=9)` on `load_postgres_task` in `dags/news_etl_dag.py` (DAG runs at midnight; data consumed at 9 AM → 9-hour budget)
- DAG-level `sla_miss_callback` writing JSON lines to `./logs/sla_misses.log` (container path `/opt/airflow/logs/sla_misses.log`; volume already mounted in `docker-compose.yml`)
- JSON line schema: `timestamp`, `dag_id`, `task_id`, `scheduled_time`, `sla_exceeded_by` — where `sla_exceeded_by` is **computed** in the callback as `datetime.now() - (execution_date + task.sla)` (not a field on Airflow's `SLAMiss` model)
- Rename `requirements.txt` → `requirements.in` (loose constraints, source of truth)
- Generate `requirements.lock` via `pip-compile requirements.in -o requirements.lock`
- Dockerfile installs from `requirements.lock` (`pip install -r requirements.lock`)
- Pin `apache-airflow==2.11.2` in `requirements.in` (matches base image `apache/airflow:2.11.2-python3.11`; prevents pip-compile from resolving a newer version transitively)
- Update `.github/workflows/ci.yml` line 71: `pip install -r requirements.lock` (the rename breaks CI otherwise)
- Add tenacity retry to `extract_data_from_newsapi`: inner function must include `requests.get()` + `raise_for_status()` + `response.json()` + `data.get("status") != "ok"` check (NewsAPI can return 200 with `{"status": "error", "code": "rateLimited"}` in body). Decorator: `stop_after_attempt(3)`, `wait_exponential(multiplier=1, min=1, max=4)`, `retry_if_exception(_is_retryable)`, `reraise=True` — retry 429/5xx/ConnectionError/Timeout/rateLimited-body, skip 404
- Tests for SLA callback output, extract retry behavior, and lock-file presence

### Out of Scope
- SMTP/email alerting (log-only by decision)
- Per-task SLAs on extract/scrape/ml (load task only this sprint)
- Running `pip-compile` in CI (deferred — CI installs from the pre-generated lock, does not generate it)
- Adding a `.dockerignore` (blocked by `.gitignore` line 24 — separate cleanup)

## Capabilities

### New Capabilities
- `sla-monitoring`: SLA enforcement on the load task and structured JSON-lines logging of SLA misses to a mounted log file
- `dependency-locking`: pip-tools-based dependency pinning (`requirements.in` + `requirements.lock`) with Dockerfile installing from the lock, and `apache-airflow==2.11.2` pinned to match the base image
- `extract-retry`: tenacity-based retry with exponential backoff for the NewsAPI extraction task, mirroring the `scrape.py` pattern

### Modified Capabilities
- `ci-pipeline`: update `ci.yml` line 71 to `pip install -r requirements.lock` (required — the rename from `requirements.txt` to `requirements.in` breaks CI otherwise)
- `test-suite`: add scenarios for SLA callback output, extract retry on transient errors, and lock-file presence in the build

## Approach

- **SLA**: add `sla=timedelta(hours=9)` to the `load_postgres_task` `PythonOperator`. Define a `sla_miss_callback` in a new `dags/pipeline/sla_callbacks.py` module that serializes each miss as one JSON line and appends to `/opt/airflow/logs/sla_misses.log`. The `sla_exceeded_by` field is computed inside the callback as `datetime.now() - (execution_date + task.sla)` — Airflow's `SLAMiss` model does not expose this directly. Wire the callback via the DAG's `sla_miss_callback` argument. No SMTP.
- **Locking**: rename `requirements.txt` → `requirements.in`; pin `apache-airflow==2.11.2` (matches base image, prevents transitive version drift). Run `pip-compile` to produce `requirements.lock`. Update `Dockerfile` `COPY` and `pip install` to target `requirements.lock`. Update `ci.yml` line 71 to install from `requirements.lock`.
- **Extract retry**: extract a `_is_retryable` helper (retry 429/5xx/connection/timeout, skip 404). The retried inner function must include `requests.get()` + `raise_for_status()` + `response.json()` + check `data.get("status") != "ok"` (NewsAPI returns 200 with error body on rate limits). Decorator matches `scrape.py` lines 58-67.
- **Effort**: ~80 lines of net change across DAG, extract, Dockerfile, and requirements files; small test additions.

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `dags/news_etl_dag.py` | Modified | Add `sla` to `load_postgres_task`; add `sla_miss_callback` to DAG |
| `dags/pipeline/sla_callbacks.py` | New | JSON-lines SLA miss callback |
| `dags/pipeline/extract.py` | Modified | Add tenacity retry + `_is_retryable` helper |
| `requirements.txt` | Removed | Renamed to `requirements.in` |
| `requirements.in` | New | Loose constraints, `apache-airflow==2.11.2` pinned |
| `requirements.lock` | New | Pinned transitive deps from `pip-compile` |
| `.github/workflows/ci.yml` | Modified | Line 71: `pip install -r requirements.lock` |
| `Dockerfile` | Modified | `COPY requirements.lock`, `pip install -r requirements.lock` |
| `tests/` | Modified | SLA callback, extract retry, lock-file tests |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| `pip-compile` pulls a provider needing newer Airflow than 2.11.2 | Med | `apache-airflow==2.11.2` pinned in `requirements.in`; verify lock resolves compatible versions |
| SLA callback writes to wrong path (host vs container) | Med | Use container path `/opt/airflow/logs/sla_misses.log`; verify volume mount and airflow-user write perms |
| Extract retry masks a persistent API outage | Low | Bounded `stop_after_attempt(3)` + `reraise=True` still fails the task |
| Upstream tasks have no SLA; slow scrape eats the load budget | Low | With SLA=9h, even a 25-min scrape leaves 8.5h of margin; per-task SLAs deferred to next sprint |
| CI breaks on rename if `ci.yml` not updated | **High** | `ci.yml` line 71 update is IN scope — single line change |

## Rollback Plan

- **SLA**: remove `sla` param and `sla_miss_callback` from the DAG; delete `sla_callbacks.py`.
- **Locking**: restore `requirements.txt` and revert Dockerfile `COPY`/`pip install` lines; revert `ci.yml` line 71.
- **apache-airflow pin**: change `apache-airflow==2.11.2` back to `apache-airflow>=2.11.0` in `requirements.in`.
- **Extract retry**: remove the `@retry` decorator and `_is_retryable` helper.

## Dependencies

- `pip-tools` installed in the dev environment to run `pip-compile`
- `./logs` volume mount in `docker-compose.yml` (already present, line 55)
- Airflow 2.11.2 `sla_miss_callback` support (available since Airflow 2.x)

## Success Criteria

- [ ] `load_postgres_task` carries `sla=timedelta(hours=9)`
- [ ] An SLA miss appends one JSON line with `timestamp`, `dag_id`, `task_id`, `scheduled_time`, `sla_exceeded_by` (computed) to `./logs/sla_misses.log`
- [ ] `requirements.in` (loose) and `requirements.lock` (pinned) exist; `requirements.txt` is gone
- [ ] `requirements.in` pins `apache-airflow==2.11.2`
- [ ] Dockerfile runs `pip install -r requirements.lock`
- [ ] `.github/workflows/ci.yml` line 71 runs `pip install -r requirements.lock`
- [ ] `extract_data_from_newsapi` retries 429/5xx/connection errors AND 200-with-error-body (`rateLimited`) with exponential backoff; skips 404
- [ ] DAG loads with no import errors; existing tests pass
