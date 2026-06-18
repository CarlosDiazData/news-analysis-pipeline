# Proposal: Sprint 1 — Critical Fixes

## Intent

The pipeline works end-to-end but lacks production-readiness: zero tests, no CI, hardcoded credentials in config files, sequential scraping (~25 min for 100 articles), and floating `latest` image tags. These five issues block any team collaboration and safe deployment.

## Scope

### In Scope
- Comprehensive pytest suite (unit + integration with PostgreSQL service container)
- GitHub Actions CI (lint → test → Docker build)
- Stratified credential management: Airflow Connection → env var → `.env` → default
- Concurrent scraping with retries, backoff, robots.txt compliance, and custom User-Agent
- Pin pgAdmin to a stable version tag

### Out of Scope
- Airflow/Python version upgrades
- DAG monolith refactor (separate `src/` package)
- Lock files, type hints, pre-commit, CHANGELOG
- Alerting/SLAs
- Any code changes beyond these five items

## Capabilities

### New Capabilities
- `test-suite`: pytest unit and integration tests covering core ETL logic (standard pytest, no pytest-postgresql)
- `ci-pipeline`: GitHub Actions workflow for lint, test, and Docker build verification; PostgreSQL service container for tests; NO real HTTP calls in CI (vcrpy/requests-mock)
- `credential-management`: Stratified credential resolution (Airflow Connection → env var → `.env` → default); resolution strictly inside task execution context, never at module top-level
- `concurrent-scraping`: Parallel article scraping with retry/backoff, robots.txt compliance, and configurable User-Agent
- `pgadmin-version-pin`: Pinned pgAdmin Docker image version

### Modified Capabilities
None — all additions, no existing spec-level contract changes.

## Approach

| # | Item | Approach |
|---|------|----------|
| 1 | Test suite | pytest (standard) + PostgreSQL service container from CI; `tests/unit/` and `tests/integration/` structure; use `vcrpy` or `requests-mock` to record/replay HTTP — zero real internet calls in CI |
| 2 | CI pipeline | Single `.github/workflows/ci.yml` with 3 jobs; PostgreSQL service container for tests |
| 3 | Credentials | `python-dotenv` → **Airflow Connection** (for PostgreSQL, encrypted) → env var → `.env` → default fallback. All resolution strictly inside operator `execute()` / task function. **No `Variable.get()` or `Connection.get_connection()` at DAG module top-level.** Strip plaintext passwords from all configs. |
| 4 | Concurrent scraping | `ThreadPoolExecutor` (configurable, default 4–5). `tenacity` for retry + backoff. `urllib.robotparser`. **Configurable `USER_AGENT`** (custom identifiable string, not default Python-urllib/3.x) stored as Airflow Variable / env var. Note: for future growth beyond this sprint, consider Airflow Dynamic Task Mapping instead of ThreadPoolExecutor. |
| 5 | pgAdmin pin | Replace `latest` with `dpage/pgadmin4:8.14` (2025-03 stable) |

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `dags/news_etl_dag.py` | Modified | Add credential chain (task-scoped), concurrent scraping, retry logic, configurable User-Agent |
| `docker-compose.yml` | Modified | Remove hardcoded passwords, pin pgAdmin version |
| `config/pgadmin/servers.json` | Modified | Strip hardcoded password |
| `.env.example` | Modified | Add missing env vars (PGADMIN_PASSWORD, POSTGRES_PASSWORD, USER_AGENT) |
| `requirements.txt` | Modified | Add `pytest`, `tenacity`, `vcrpy` (or `requests-mock`) |
| `Dockerfile` | Modified | Install test deps in dev stage |
| `tests/` | New | Unit and integration test modules |
| `.github/workflows/ci.yml` | New | CI workflow definition |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| `tenacity`/`robotparser` import errors in Airflow container | Low | Pinned in `requirements.txt`, verified in Docker build job |
| Concurrent scraping triggers rate limiting | Medium | Configurable concurrency; exponential backoff handles 429s |
| CI secrets misconfiguration | Low | Documented in `.env.example`; CI job fails early with clear error |
| pgAdmin pinned version breaks existing servers.json format | Low | `dpage/pgadmin4:8.14` uses same `servers.json` schema |
| Memory saturation in Airflow worker due to concurrent threads | Medium | Cap `max_workers` at 4–5; monitor RAM consumption in container |
| False positives in CI from flaky integration tests using real HTTP calls | High | Use `vcrpy` or `requests-mock` to record/replay HTTP responses — **no real internet calls in CI** |

## Rollback Plan

`git revert` of the sprint commit. Clean, traceable, single-command rollback. No manual code rewrite needed.

## Dependencies

- PostgreSQL service container (GitHub Actions already provides this) — no external test DB needed
- `tenacity` (MIT, zero deps) — no conflict with existing packages
- `vcrpy` or `requests-mock` — for deterministic HTTP replay in CI tests
- All items are independent except: tests (#1) validate scraping (#4) and credentials (#3)

## Success Criteria

- [ ] `pytest` runs ≥15 tests with `>80%` coverage on DAG core logic
- [ ] CI passes on push: lint (ruff), test (pytest + PostgreSQL), Docker build
- [ ] Zero plaintext passwords in `docker-compose.yml`, `servers.json`, or DAG code
- [ ] 100-article scrape completes in ≤5 minutes (was ~25 min)
- [ ] pgAdmin starts with pinned version, no container pull warnings
