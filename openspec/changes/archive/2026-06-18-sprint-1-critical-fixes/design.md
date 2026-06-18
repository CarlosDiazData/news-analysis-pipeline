# Design: Sprint 1 — Critical Fixes

## Technical Approach

Layer production-readiness onto the existing monolithic pipeline without refactoring the DAG — five surgical additions: test harness, CI automation, secure credential chain, parallel scraping, and pinned infrastructure.

## Architecture Decisions

| # | Decision | Choice | Rationale |
|---|----------|--------|-----------|
| 1 | HTTP mock strategy | `requests-mock` (pytest fixture) | Faster than vcrpy cassette management; zero disk I/O; simpler CI integration |
| 2 | DB isolation | TRUNCATE in conftest teardown (app tables only) | Explicit, predictable; avoids psycopg2 transaction complexity. MUST NOT touch Airflow internal tables if sharing same PG instance |
| 3 | Credential helper | `dags/credential_helper.py`, task-scoped | Keeps resolution outside DAG module body; no Variable/Connection reads at import-time |
| 4 | Thread model | `ThreadPoolExecutor` with context manager | I/O-bound workload; `max_workers=4` default (configurable). Async not justified — no event loop already present |
| 5 | robots.txt cache data structure | `dict[str, RobotFileParser]` keyed by domain | Fetch-once-before-pool pattern; domain extraction via `urlparse`; O(1) lookup per URL |
| 6 | pgAdmin version | `dpage/pgadmin4:8.14` | 2025-03 stable; servers.json schema unchanged; tested against PostgreSQL 13 |
| 7 | Ruff config | `pyproject.toml [tool.ruff]` | Centralized config ensures identical rules in local dev (IDE extensions) and CI. Avoids long CLI flags in workflow YAML |
| 8 | Docker build in CI | `docker build` direct (or `docker/build-push-action`) | Lighter than `docker compose build`; superior cache handling (gha backend); no compose overhead in CI runners |

## Data Flow

```
.env ─┐
env   ─┤
Conn  ─┴──▶ resolve_credentials() ──▶ task functions
                                          │
    ┌─────────────────────────────────────┘
    ▼
extract ──▶ scrape (parallel, ThreadPool) ──▶ analyze ──▶ load (PostgresHook)
                │                    │
                ├─ robots.txt cache   ├─ tenacity retry (3 attempts, 1s→4s backoff)
                ├─ urlparse → domain   └─ skip 404s immediately
                └─ apply USER_AGENT header
```

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `tests/__init__.py` | Create | Package marker |
| `tests/unit/__init__.py` | Create | Unit test marker |
| `tests/unit/test_extract.py` | Create | Mocked NewsAPI extraction |
| `tests/unit/test_scrape.py` | Create | Mocked scraping + robots.txt |
| `tests/unit/test_analyze.py` | Create | NLP output validation |
| `tests/unit/test_load.py` | Create | PostgreSQL insertion (mocked hook) |
| `tests/unit/test_dag_integrity.py` | Create | DagBag parse + cycle check |
| `tests/integration/__init__.py` | Create | Integration test marker |
| `tests/integration/test_db_load.py` | Create | Live PostgreSQL insert/read round-trip |
| `tests/conftest.py` | Create | Shared fixtures: mock_api, db_connection, truncate_teardown (app tables only, skip Airflow internals) |
| `pyproject.toml` | Create | `[tool.ruff]` config: select rules, line-length, target-version, format settings |
| `.github/workflows/ci.yml` | Create | 3-job pipeline: lint (ruff check + format), test (pytest, postgres service), build (docker build with gha cache) |
| `dags/credential_helper.py` | Create | `resolve_db_creds()` + `resolve_newsapi_key()` |
| `dags/news_etl_dag.py` | Modify | ThreadPoolExecutor, tenacity, robots.txt cache, credential helper, configurable UA |
| `docker-compose.yml` | Modify | Pin pgAdmin to 8.14, add `.pgpass` mount, add `MAX_SCRAPE_WORKERS` env |
| `Dockerfile` | Modify | Add test deps (pytest, requests-mock, tenacity) after production layer |
| `config/pgadmin/servers.json` | Modify | Remove hardcoded password, reference `.pgpass` |
| `.env.example` | Modify | Add POSTGRES_PASSWORD, PGADMIN_PASSWORD, USER_AGENT |
| `config/pgadmin/.pgpass` | Create | `postgres:5432:airflow_db:airflow:<password>` |
| `requirements.txt` | Modify | Add pytest, requests-mock, tenacity |

## Interfaces / Contracts

### Credential Helper API
```python
# dags/credential_helper.py
def resolve_db_creds(conn_id: str = "postgres_default") -> dict:
    """Returns {'host','port','dbname','user','password'}.
    Order: Airflow Connection → env vars → .env → defaults."""
    ...

def resolve_newsapi_key() -> str:
    """Order: Airflow Variable → NEWS_API_KEY env → .env → raise."""
    ...
```

### CI Matrix
```yaml
# .github/workflows/ci.yml — job dependency graph
# lint (ruff check + format) ──┐
#                               ├── test (pytest, postgres service container)
#                               └── build (docker build with cache-from)
# test and build run in parallel after lint passes.
```

### .pgpass Format
```
# One line: hostname:port:database:username:password
postgres:5432:airflow_db:airflow:<password>
```

## Testing Strategy

| Layer | What | Approach |
|-------|------|----------|
| Unit | Extract, scrape, analyze, load functions | `requests-mock` for HTTP; `unittest.mock` for PostgresHook; conftest-provided sample articles |
| Unit | DAG integrity | `airflow.models.DagBag()` — verify zero import_errors and no cycles |
| Integration | PostgreSQL round-trip | Real PostgreSQL service container; insert via `load_data_to_postgres`, verify with SELECT |
| Mock-only | All HTTP in CI | requests-mock intercepts every external call; zero network dependency |

## Dependency Graph

```
credential-mgmt ──┐
                  ├──▶ test-suite ──▶ ci-pipeline
concurrent-scrape ─┘
                                     (independent)
pgadmin-version-pin ────▶ (no deps, can run anytime)
```

Items 3, 4, and 5 are independent and parallelizable. Item 1 (tests) depends on items 3 and 4. Item 2 (CI) depends on item 1.

## Risk Mitigations Embedded in Design

- **Memory saturation**: `max_workers=4` default, configurable via `MAX_SCRAPE_WORKERS` env var; bounded at 8 in code
- **Flaky CI**: `requests-mock` guarantees deterministic HTTP; no network = no flakes
- **Scheduler overhead**: `credential_helper.py` functions called only inside `PythonOperator` callables, never at module import
- **Zombie threads**: `with ThreadPoolExecutor(...) as executor:` context manager ensures shutdown on SIGTERM
- **rate-limit hammering**: `tenacity` with exponential backoff (wait=1s→2s→4s, max 3 attempts) on 429/5xx; 404/4xx skipped immediately

## Resolved Questions

- [x] Ruff config → `pyproject.toml [tool.ruff]` for reproducibility across local + CI
- [x] Docker build in CI → `docker build` direct (lighter, better cache than compose)
