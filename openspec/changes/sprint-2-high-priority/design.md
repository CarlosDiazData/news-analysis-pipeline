# Design: Sprint 2 — High-Priority Operational Maturity

## Technical Approach

Four change clusters: (1) DAG `sla=timedelta(hours=9)` on `load_postgres_task` + `sla_miss_callback`; (2) extract — tenacity inner `_fetch_newsapi` mirroring `scrape.py:58–67`; (3) dependency graph — `requirements.in`/`requirements.lock` via `pip-compile`, `apache-airflow==2.11.2` pinned to base image; (4) CI — `pip install -r requirements.lock` + `cache-dependency-path`. The rename + Dockerfile/`ci.yml` edits MUST land in one commit (else CI breaks — see Migration).

## Architecture Decisions

### Decision: SLA callback in a dedicated `dags/pipeline/sla_callbacks.py`

| Option | Tradeoff | Decision |
|---|---|---|
| Inline in `news_etl_dag.py` | Fewer imports, but untestable in isolation | ✗ |
| `dags/pipeline/sla_callbacks.py` | Module-level function; mirrors `pipeline/extract.py` layout; importable for tests | ✓ |

**Rationale**: DAG file is declarative (line 13 imports siblings); a dedicated module is unit-testable.

### Decision: Retry the inner function, NOT the outer

| Option | Tradeoff | Decision |
|---|---|---|
| Decorate `extract_data_from_newsapi` | Retries `resolve_newsapi_key()`, a permanent `RuntimeError` — wastes 1–4s per attempt | ✗ |
| Decorate private `_fetch_newsapi` | Credential resolved once; retry only HTTP + body-status check | ✓ |

**Rationale**: Reuses the proven `scrape.py:58–67` pattern.

### Decision: `_is_retryable` deviates from `scrape.py`

| Option | Tradeoff | Decision |
|---|---|---|
| Copy `scrape.py:19–37` (False for all non-429/5xx HTTPErrors) | Conservative but rejects spec requirement | ✗ |
| Spec: True for ALL exceptions except HTTP 404 | `[extract-retry/spec]` Requirement: Skip Non-Retryable Errors is explicit | ✓ |

**Rationale**: True for non-404 — broader than `scrape.py` (False for non-429 4xx). Spec-driven, not a copy-paste slip.

### Decision: Outer still wraps to `AirflowException` after retries

| Option | Tradeoff | Decision |
|---|---|---|
| Surface raw `HTTPError`/`RuntimeError` after `reraise=True` | Existing `test_non_200_raises_airflow_exception` and `test_api_error_status_raises` expect `AirflowException` | ✗ |
| Wrap `RequestException` + `RuntimeError` → `AirflowException` preserving original message | Existing test contract kept | ✓ |

**Rationale**: Inner raises `RuntimeError(f"API Error: {data['message']}")`, so old `match="API key"` still triggers.

### Decision: Lock file committed, CI does NOT regenerate

| Option | Tradeoff | Decision |
|---|---|---|
| CI runs `pip-compile` | Slow CI, resolver drift from forks | ✗ |
| Developer runs `pip-compile`, commits `requirements.lock` | Deterministic install, audit trail, fast CI | ✓ |

**Rationale**: validates via `pip-compile --check`; CI just installs.

## Data Flow

```
DAG(sla_miss_callback=on_sla_miss)
       │ load_task.sla = timedelta(hours=9) exceeded
       ▼
on_sla_miss(dag, task_list, blocking_task_list, slas, blocking_tis)
       │ for miss in slas:
       │   task = dag.get_task(miss.task_id)
       │   sla_exceeded_by = int((now_utc - (execution_date + task.sla)).total_seconds())
       ▼ append one JSON line per miss
   /opt/airflow/logs/sla_misses.log   (host ./logs — already mounted, docker-compose.yml:55)

extract_data_from_newsapi
  ├── resolve_newsapi_key()    ← resolved ONCE, outside retry
  └── _fetch_newsapi(endpoint, params)   ← @retry decorated
         │ requests.get → raise_for_status → response.json → status != "ok" → RuntimeError
         └ reraise=True after 3 attempts
  └── except RequestException → AirflowException("Connection error: {exc}")
      except RuntimeError     → AirflowException(str(exc))
```

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `dags/pipeline/sla_callbacks.py` | Create | `on_sla_miss(...)` iterates `slas`; appends JSON line per miss to `/opt/airflow/logs/sla_misses.log` (mode `a`) |
| `dags/news_etl_dag.py` | Modify | Import `on_sla_miss`; pass `sla_miss_callback=on_sla_miss` to `DAG(...)`; add `sla=timedelta(hours=9)` to `load_postgres_task` (lines 70-73) |
| `dags/pipeline/extract.py` | Modify | Add tenacity; `_is_retryable` (True for all except HTTP 404); `@retry` inner `_fetch_newsapi` mirroring `scrape.py:58–67`; outer wraps `RequestException` + `RuntimeError` → `AirflowException` |
| `requirements.txt` | Delete | Replaced by `requirements.in` |
| `requirements.in` | Create | Same loose constraints; pin `apache-airflow==2.11.2` (matches `apache/airflow:2.11.2-python3.11`) |
| `requirements.lock` | Create | `pip-compile requirements.in -o requirements.lock`; committed to repo |
| `Dockerfile` | Modify | Line 15: `COPY requirements.lock`; line 16: `pip install -r /opt/airflow/requirements.lock` |
| `.github/workflows/ci.yml` | Modify | Line 71: `pip install -r requirements.lock`; add `cache-dependency-path: requirements.lock` to `setup-python@v5` (since `cache: pip` can't auto-detect lock) |
| `tests/unit/test_sla_callbacks.py` | Create | JSON-line schema; append-not-overwrite; `sla_exceeded_by` computation |
| `tests/unit/test_extract.py` | Modify | New `TestExtractRetry` class: `429→200`, `503×2→200`, `ConnectionError`, `404` immediate, `rateLimited` body, all-exhausted. Existing `requests_mock` + `patch` style |
| `tests/unit/test_lockfile.py` | Create | `os.path.exists` + `pip-compile --check` (skipif unavailable) |

## Interfaces / Contracts

### SLA Callback

```python
SLA_MISS_LOG = "/opt/airflow/logs/sla_misses.log"

def on_sla_miss(dag, task_list, blocking_task_list, slas, blocking_tis) -> None:
    now = datetime.now(timezone.utc)
    for miss in slas:                       # list[SLAMiss] — has dag_id, task_id, execution_date
        task = dag.get_task(miss.task_id)    # task.sla is a timedelta
        sla_exceeded_by = int((now - (miss.execution_date + task.sla)).total_seconds())
        record = {"timestamp": now.isoformat(), "dag_id": miss.dag_id,
                  "task_id": miss.task_id, "scheduled_time": miss.execution_date.isoformat(),
                  "sla_exceeded_by": sla_exceeded_by}
        with open(SLA_MISS_LOG, "a") as fh:
            fh.write(json.dumps(record) + "\n")
```

### Extract Inner Function

```python
@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=4),
       retry=retry_if_exception(_is_retryable), reraise=True)
def _fetch_newsapi(endpoint: str, params: dict) -> list[dict]:
    response = requests.get(endpoint, params=params, timeout=30)
    response.raise_for_status()             # → HTTPError for non-2xx (caught by _is_retryable)
    data = response.json()
    if data.get("status") != "ok":          # NewsAPI returns 200 with error body on rate limits
        raise RuntimeError(f"API Error: {data.get('message', 'Unknown error')}")
    return data.get("articles", [])
```

## Testing Strategy

| Layer | What to Test | Approach |
|-------|-------------|----------|
| Unit (SLA) | JSON schema, `sla_exceeded_by`, append-not-overwrite | Mock `SLAMiss` namedtuple + `dag.get_task(tid).sla`; redirect log to `tmp_path`; `json.loads` each line, assert 5 keys; run twice → 2 lines |
| Unit (extract retry) | 429→200; 503×2→200; `ConnectionError`; 404 no-retry; `rateLimited`→ok; all-exhausted raises | `requests_mock` queues `[{429}, {json: newsapi_response}]`; `patch resolve_newsapi_key`; mirror existing class-grouped style |
| Unit (lockfile) | File exists; lock in sync | `os.path.exists`; `subprocess.run(["pip-compile", "--check", ...])` skipif unavailable |
| Integration | DAG integrity with `sla` + callback | Extend existing DagBag test; assert `load_task.sla == timedelta(hours=9)` and `dag.sla_miss_callback is on_sla_miss` |

## Migration / Rollout

No data migration, no feature flag. Dependency rename is atomic across `requirements.in`/`requirements.lock`/`Dockerfile`/`ci.yml` — partial commits break CI.

Three commits:
1. **A** (atomic rename + plumbing): `requirements.in` (airflow pin), `requirements.lock`, Dockerfile, `ci.yml` line 71 + `cache-dependency-path`.
2. **B** (extract retry): `extract.py` + `test_extract.py` retry class.
3. **C** (SLA callback): `sla_callbacks.py`, DAG wiring, `test_sla_callbacks.py`, `test_lockfile.py`.

## Open Questions

- [ ] `test_api_error_status_raises` uses `apiKeyInvalid` (not `rateLimited`); spec deviation retries 3×, adding 1–4s. Acceptable or refactor to `rateLimited`?
- [ ] `sla_exceeded_by = now_utc - (execution_date + task.sla)` assumes tz-aware `execution_date`; if Airflow yields naive `datetime`, subtraction raises `TypeError`. Unit test will surface; runtime tz must be confirmed before rollout.