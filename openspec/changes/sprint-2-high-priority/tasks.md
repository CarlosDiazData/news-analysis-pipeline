# Tasks: Sprint 2 — High-Priority Operational Maturity

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | 295–320 (~150 hand-written + ~70 lockfile + ~75 deps) |
| 400-line budget risk | Medium |
| Chained PRs recommended | Yes |
| Suggested split | PR 1 (Commit A: dep lock) → PR 2 (Commit B: retry) → PR 3 (Commit C: SLA) |
| Delivery strategy | feature-branch-chain |
| Chain strategy | feature-branch-chain |

Decision needed before apply: Yes (resolved: feature-branch-chain)
Chained PRs recommended: Yes
Chain strategy: feature-branch-chain
400-line budget risk: Medium (resolved: 3 PRs via feature-branch-chain)

### Suggested Work Units

| Unit | Goal | Likely PR | Notes |
|------|------|-----------|-------|
| 1 | Atomic rename: requirements.in (pin airflow 2.11.2), requirements.lock, Dockerfile, ci.yml | PR 1 | Base: tracker. Dependency rename MUST be one commit — partial breaks CI. |
| 2 | Extract retry: tenacity on _fetch_newsapi + _is_retryable + tests | PR 2 | Base: pr-1 (sequential). |
| 3 | SLA callback + DAG wiring + tests for SLA and lockfile | PR 3 | Base: pr-2 (sequential). |

## Phase 1: Dependency Locking (Commit A — Atomic)

- [x] 1.1 Rename `requirements.txt` → `requirements.in`; pin `apache-airflow==2.11.2`. [dep-lock: Airflow Version Pin]
- [x] 1.2 Run `pip-compile requirements.in -o requirements.lock` and commit it. [dep-lock: Requirements Split]
- [x] 1.3 Update `Dockerfile` lines 15-16: `COPY requirements.lock`, `pip install -r /opt/airflow/requirements.lock`. [dep-lock: Dockerfile Installs from Lock]
- [x] 1.4 Update `ci.yml` line 71: `pip install -r requirements.lock`; add `cache-dependency-path: requirements.lock` to `setup-python@v5`. [ci-pipeline]

## Phase 2: Extract Retry (Commit B)

- [x] 2.1 Add tenacity imports and `_is_retryable` helper to `dags/pipeline/extract.py` (True for all except HTTP 404). [extract-retry: Skip Non-Retryable Errors]
- [x] 2.2 Create `_fetch_newsapi(endpoint, params)` inner function with `@retry(stop_after_attempt(3), wait_exponential(multiplier=1, min=1, max=4), retry=retry_if_exception(_is_retryable), reraise=True)` — includes `requests.get()` + `raise_for_status()` + `response.json()` + `data.get("status") != "ok"` check. [extract-retry]
- [x] 2.3 Update outer `extract_data_from_newsapi`: resolve key once, call `_fetch_newsapi`, wrap `RequestException` + `RuntimeError` → `AirflowException`. [extract-retry: All retries exhausted]
- [x] 2.4 Add `TestExtractRetry` class in `tests/unit/test_extract.py`: 429→200, 503×2→200, ConnectionError retry, 404 no-retry, rateLimited body, all-exhausted. [test-suite: Extract Retry Tests]

## Phase 3: SLA Monitoring (Commit C)

- [x] 3.1 Create `dags/pipeline/sla_callbacks.py` with `on_sla_miss(dag, task_list, blocking_task_list, slas, blocking_tis)` — iterates `slas`, computes `sla_exceeded_by`, appends JSON line to `/opt/airflow/logs/sla_misses.log`. [sla-monitoring: Structured SLA Miss Log]
- [x] 3.2 Wire into `dags/news_etl_dag.py`: import `on_sla_miss`; add `sla_miss_callback=on_sla_miss` to `DAG(...)`; add `sla=timedelta(hours=9)` to `load_postgres_task`. [sla-monitoring: Load Task SLA Deadline]
- [x] 3.3 Create `tests/unit/test_sla_callbacks.py`: JSON schema, append-not-overwrite, `sla_exceeded_by` computation, multiple misses. [test-suite: SLA Callback Tests]
- [x] 3.4 Create `tests/unit/test_lockfile.py`: `os.path.exists("requirements.lock")` and `pip-compile --check` (skipif unavailable). [test-suite: Lock File Presence Test]

## Phase 4: Integration Verification

- [x] 4.1 Extend DAG integrity test: assert `load_task.sla == timedelta(hours=9)` and `dag.sla_miss_callback is on_sla_miss`. [sla-monitoring]
- [x] 4.2 Run `pytest tests/ -v --tb=short` — verify zero regressions, all 5 spec areas pass.
