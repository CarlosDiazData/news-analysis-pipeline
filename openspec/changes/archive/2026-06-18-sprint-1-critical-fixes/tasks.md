# Tasks: Sprint 1 — Critical Fixes

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | ~660 (190 code + 370 tests + 100 CI) |
| 400-line budget risk | High |
| Chained PRs recommended | Yes |
| Suggested split | PR 1: code changes → PR 2: tests → PR 3: CI |
| Delivery strategy | auto-chain |
| Chain strategy | feature-branch-chain |

Decision needed before apply: No
Chained PRs recommended: Yes
Chain strategy: feature-branch-chain
400-line budget risk: High

### Suggested Work Units

| Unit | Goal | Likely PR | Notes |
|------|------|-----------|-------|
| 1 | All code changes | PR 1 | Base: feature/sprint-1-critical-fixes. credential_helper, concurrent scraping, credential integration, pgAdmin pin, config |
| 2 | Test suite | PR 2 | Base: PR 1 branch. Unit + integration tests, conftest, test deps |
| 3 | CI pipeline | PR 3 | Base: PR 2 branch. lint → test → build workflow, Docker build cache |

## Phase 1: Foundation & Core Code

- [x] 1.1 Create `dags/credential_helper.py` — `resolve_db_creds()`, `resolve_newsapi_key()` with stratified resolution (Airflow Connection → env → .env → default)
- [x] 1.2 Create `pyproject.toml` with `[tool.ruff]` config — **`target-version` MUST match exact Python version running in Airflow container (e.g. `"py311"`)** to avoid syntax discrepancies between local lint and runtime
- [x] 1.3 Update `docker-compose.yml`: pin `dpage/pgadmin4:8.14` with comment, add `.pgpass` mount, add `MAX_SCRAPE_WORKERS` env
- [x] 1.4 Create `config/pgadmin/.pgpass`, update `servers.json` to remove hardcoded password — **MUST set `chmod 600 .pgpass`** or PostgreSQL/psql will ignore it for security. Ensure volume mount preserves permissions.
- [x] 1.5 Update `.env.example` with `POSTGRES_PASSWORD`, `PGADMIN_PASSWORD`, `USER_AGENT`
- [x] 1.6 Update `requirements.txt` — add `tenacity`

## Phase 2: DAG Modifications

- [x] 2.1 Add robots.txt cache (`dict[str, RobotFileParser]` by domain) in `news_etl_dag.py` — **initialize cache dict INSIDE the task executable function, just before opening ThreadPoolExecutor context. Never at DAG module global scope.**
- [x] 2.2 Replace sequential scraping loop with `ThreadPoolExecutor` context manager (`max_workers` from env, default 4) — context manager ensures clean shutdown on SIGTERM
- [x] 2.3 Add `tenacity` retry decorator with exponential backoff (1s→2s→4s, max 3 attempts, skip 404)
- [x] 2.4 Add configurable `USER_AGENT` from env/credential helper
- [x] 2.5 Replace `os.environ.get("NEWS_API_KEY")` with `resolve_newsapi_key()` inside task callable
- [x] 2.6 Replace `PostgresHook(postgres_conn_id=DEFAULT_CONN_ID)` with `resolve_db_creds()` inside task callable
- [x] 2.7 Verify zero `Variable.get()`/`Connection.get_connection()` at module top-level — **post-Phase 2 verification: run `python dags/news_etl_dag.py` locally. MUST parse almost instantly. If it takes >1s or attempts connections/variable reads, something leaked into global scope.**

## Phase 3: Test Suite

- [x] 3.1 Create `tests/conftest.py` — shared fixtures (mock NewsAPI, mock articles, PostgresHook patches, truncate teardown) — **TRUNCATE must use `TRUNCATE TABLE app_table1, app_table2 RESTART IDENTITY CASCADE;` for fully deterministic isolation. Only app tables — NEVER touch Airflow internal tables.**
- [x] 3.2 Create `tests/unit/test_dag_integrity.py` — DagBag parse — **MUST assert `len(dagbag.import_errors) == 0`**. This is the single most important CI test.
- [x] 3.3 Create `tests/unit/test_extract.py` — mocked NewsAPI extraction (200 ok, non-200 raises, empty articles)
- [x] 3.4 Create `tests/unit/test_scrape.py` — mocked scraping (HTML extracted, robots.txt cache per domain, 404 skipped, 429 retried)
- [x] 3.5 Create `tests/unit/test_analyze.py` — sentiment/entity validation, empty content edge case
- [x] 3.6 Create `tests/unit/test_load.py` — PostgresHook mock (insert success, empty articles → 0, DB error → AirflowException)
- [x] 3.7 Create `tests/integration/test_db_load.py` — live PostgreSQL insert/read round-trip via conftest fixture
- [x] 3.8 Update `requirements.txt` — add `pytest`, `requests-mock`; update `Dockerfile` for test deps (dev stage)

## Phase 4: CI Pipeline

- [x] 4.1 Create `.github/workflows/ci.yml` — trigger on push to main and PRs targeting main
- [x] 4.2 Job `lint`: `ruff check` + `ruff format --check` with pip cache
- [x] 4.3 Job `test`: pytest with PostgreSQL service container (5432), `NEWS_API_KEY` secret
- [x] 4.4 Job `build`: `docker build` with gha cache — **use `docker/build-push-action` with modern GitHub Actions cache backend: `cache-from: type=gha` and `cache-to: type=gha,mode=max`**
- [x] 4.5 Job dependency: `lint` → `test` + `build` (parallel)
