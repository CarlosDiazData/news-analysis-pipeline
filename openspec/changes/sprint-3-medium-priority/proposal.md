# Proposal: Sprint 3 — Medium-Priority Operational Maturity

## Intent

Five medium-priority improvements that harden the news ETL pipeline: (1) create a `.dockerignore` and unblock tracking, (2) validate NewsAPI response data before downstream processing, (3) ~~respect `robots.txt` in scraping~~ (already implemented in Sprint 2 — see note), (4) make NewsAPI country/topic configurable instead of hardcoded, and (5) add type hints to all task callables.

## Pre-Existing Note: robots.txt Compliance

`dags/pipeline/scrape.py` **already implements full robots.txt compliance** — this was delivered as part of the concurrent-scraping feature in Sprint 2. The code:

- Fetches `robots.txt` once per domain BEFORE the ThreadPoolExecutor (lines 129-149)
- Caches `RobotFileParser` instances in a `dict` keyed by domain
- Checks `rp.can_fetch()` inside `_scrape_single_article` before making any HTTP request (lines 45-56)
- Skips scraping with a warning when disallowed (line 52-53)
- Logs a warning when robots.txt is unreachable and proceeds cautiously (lines 147-148)

This improvement is **already resolved**. The original analysis identified it before Sprint 2 implemented concurrent scraping. No further work needed.

## Scope

### In Scope

#### 1. `.dockerignore` + `.gitignore` fix
- Create `.dockerignore` at project root excluding: `.env` (credentials), `.git/` (1.3M), `logs/` (2.3M), `__pycache__/`, `.pytest_cache/`, `.ruff_cache/`, `airflow_home_test/`, `.github/`, `Docs/`, `openspec/` (build-time only), `data/` (mounted volume), `tests/`, `requirements.in`, `pyproject.toml`, `readme.md`, `LICENSE.txt`, `.gitignore`, `.env.example`, `init_db/` (handled by postgres container), `.atl/`, `config/` (pgadmin config — not needed at build)
- Remove `.dockerignore` from `.gitignore` line 24 so the file is tracked
- **Critical**: keep `dags/`, `Dockerfile`, `requirements.lock` in the build context (they are needed for `docker build`)
- Docker context after `.dockerignore`: `Dockerfile`, `requirements.lock`, `dags/` only (from ~4MB+ down to ~200KB)

#### 2. Data Input Validation
- Validate the NewsAPI JSON response structure immediately after the `status == "ok"` check in `_fetch_newsapi`
- Validate each article dict after extraction: reject articles missing `url` or `title` (these would fail silently downstream or in the DB upsert)
- Validate article content before scraping: skip articles without a valid `url` schema (http/https only)
- Define a lightweight schema or dataclass for the expected article shape — NOT a full Pydantic dependency (keep it lightweight)
- Log warnings for invalid/dropped articles with detail about what failed

#### 3. ~~robots.txt Compliance~~ (Already Done — see note above)

#### 4. Configurable Country/Topic
- Add `NEWS_API_COUNTRY` (default: `us`) and `NEWS_API_TOPIC` (default: `None` — optional) to `config.py`
- Update `extract_data_from_newsapi()` to read these values from config instead of hardcoding `"country": "us"`
- Add stratified resolution (Airflow Variable → env var → .env → config default) via `credentials.py` functions, matching the existing pattern for `USER_AGENT` / `MAX_SCRAPE_WORKERS`
- Add `NEWS_API_COUNTRY` and `NEWS_API_TOPIC` to `.env.example` (commented out with defaults)
- Add `NEWS_API_COUNTRY` and `NEWS_API_TOPIC` to `docker-compose.yml` airflow service environment (with defaults from `.env`)
- Keep backward compatibility: if unset, defaults to `us` and no topic filter

#### 5. Type Hints
- Add return type annotations to ALL task callables:
  - `extract_data_from_newsapi()` → `list[dict]`
  - `scrape_and_enrich_content(**context)` → `list[dict]`
  - `analyze_articles(**context)` → `list[dict]`
  - `load_data_to_postgres(**context)` → `int`
- add type hint for `context` parameter: `**context` can't be typed directly, but document the expected shape in the docstring
- Verify no existing type annotations are broken (ruff is already configured for `py311` target)

### Out of Scope
- Adding a full schema validation library (Pydantic, marshmallow, etc.) — too heavy for this pipeline
- Changing the scraping behavior or adding new error-recovery logic
- Adding `mypy` or static type checking to CI (ruff covers basic type issues; mypy is a future improvement)
- Making `pageSize` configurable (currently hardcoded to 100 — NewsAPI free tier max; no benefit to making it configurable)
- Adding per-domain rate limiting or polite scraping delays (deferred)
- Changing the robots.txt behavior (already correct)

## Capabilities

### New Capabilities
- `docker-context-safety`: `.dockerignore` excludes secrets and build-irrelevant files, reducing context from ~4MB to ~200KB; `.gitignore` no longer blocks tracking
- `input-validation`: NewsAPI response and article schema validation before downstream processing, with per-article logging of skipped records
- `configurable-newsapi-params`: Country and topic for NewsAPI queries are configurable via Airflow Variables, env vars, or `.env` without code changes

### Modified Capabilities
- `test-suite`: new test coverage for input validation logic and config resolution
- `codebase-consistency`: type hints on all task callables (remaining untyped public API surface)

## Approach

- **`.dockerignore`**: follow the standard Docker build-context exclusion pattern. Test by running `docker build` and verifying the context is small. The `.gitignore` fix is a single-line deletion (line 24). Both changes are independent and low-risk.
- **Input validation**: add a `_validate_article(article: dict) -> bool` helper in `extract.py` after the retry loop. The validation checks for: `url` must be non-empty string starting with `http`, `title` must be non-empty string. Log skipped articles with reason. The scraper silently skips articles without URLs anyway; validation makes this explicit upstream.
- **Configurable params**: follow the EXACT stratified pattern from `credentials.py resolve_user_agent()` for `resolve_newsapi_country()` and `resolve_newsapi_topic()`. Config defaults live in `config.py`. This means the configuration is consistent: check Airflow Variable, then env var, then `.env`, then built-in default.
- **Type hints**: all task callables in `extract.py`, `scrape.py`, `analyze.py`, and `load.py` get return type annotations. No other changes to function bodies.

### File-by-File Plan

| File | Action | Changes |
|------|--------|---------|
| `.dockerignore` | **New** | Exclude `.env`, `.git/`, `logs/`, `__pycache__/`, `.pytest_cache/`, `.ruff_cache/`, `airflow_home_test/`, `.github/`, `Docs/`, `openspec/`, `data/`, `tests/`, `requirements.in`, `pyproject.toml`, `readme.md`, `LICENSE.txt`, `.gitignore`, `.env.example`, `init_db/`, `.atl/`, `config/` |
| `.gitignore` | **Modified** | Remove line 24 (`.dockerignore`) |
| `dags/pipeline/config.py` | **Modified** | Add `NEWS_API_COUNTRY = "us"` and `NEWS_API_TOPIC = None` |
| `dags/pipeline/credentials.py` | **Modified** | Add `resolve_newsapi_country()` and `resolve_newsapi_topic()` following `resolve_user_agent()` pattern |
| `dags/pipeline/extract.py` | **Modified** | Add `_validate_article()` helper, add validation step after `_fetch_newsapi`, use configurable country/topic from `config.py`, add return type to `extract_data_from_newsapi` |
| `dags/pipeline/scrape.py` | **Modified** | Add return type to `scrape_and_enrich_content` (no other changes) |
| `dags/pipeline/analyze.py` | **Modified** | Add return type to `analyze_articles` (no other changes) |
| `dags/pipeline/load.py` | **Modified** | Add return type to `load_data_to_postgres` (no other changes) |
| `.env.example` | **Modified** | Add `NEWS_API_COUNTRY`, `NEWS_API_TOPIC` (commented with defaults) |
| `docker-compose.yml` | **Modified** | Add `NEWS_API_COUNTRY` and `NEWS_API_TOPIC` to airflow environment (with defaults) |
| `tests/unit/test_extract.py` | **Modified** | Add tests for `_validate_article`, validation filtering |
| `tests/unit/test_credentials.py` | **New** (if missing) or **Modified** | Tests for `resolve_newsapi_country()` and `resolve_newsapi_topic()` |

### Effort Estimation

| Improvement | Net Lines | Complexity | Risk |
|-------------|-----------|------------|------|
| `.dockerignore` + `.gitignore` | ~25 (new) + 1 (delete) | Low | Low — build context shrinks, no runtime impact |
| Input validation | ~30 (extract.py) + ~60 (tests) | Low | Low — additive, never blocks correct data |
| Configurable country/topic | ~35 (config + credentials + env) + ~5 (extract) | Low | Low — follows existing pattern exactly |
| Type hints | ~4 lines (one per callable) | Trivial | None — runtime behavior unchanged |
| **Total** | **~160 lines** | **Low** | **Low** |

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `.dockerignore` | New | Docker build context exclusions |
| `.gitignore` | Modified | Remove line 24 (`.dockerignore`) |
| `dags/pipeline/config.py` | Modified | Add `NEWS_API_COUNTRY`, `NEWS_API_TOPIC` constants |
| `dags/pipeline/credentials.py` | Modified | Add `resolve_newsapi_country()`, `resolve_newsapi_topic()` |
| `dags/pipeline/extract.py` | Modified | Input validation, configurable params, return type |
| `dags/pipeline/scrape.py` | Modified | Return type annotation only |
| `dags/pipeline/analyze.py` | Modified | Return type annotation only |
| `dags/pipeline/load.py` | Modified | Return type annotation only |
| `.env.example` | Modified | New config variables |
| `docker-compose.yml` | Modified | Pass new vars to airflow container |
| `tests/unit/test_extract.py` | Modified | Validation tests |
| `tests/unit/test_credentials.py` | Modified | (or new) Config resolution tests |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| `.dockerignore` accidentally excludes `dags/` or `Dockerfile` | Low | Explicit inclusion of `dags/` in ignore + test build; `dags/` is the primary Airflow source |
| Validation drops legitimate articles with missing optional fields | Low | Validation only requires `url` (for dedup) and `title` (for display); everything else is optional |
| `NEWS_API_TOPIC` adds a NewsAPI parameter that filters results (NewsAPI category param is `category`, not `topic`) | Med | Must use NewsAPI's actual parameter name (`category`). Document that `NEWS_API_TOPIC` maps to the `category` query param. NewsAPI category values: `business`, `entertainment`, `general`, `health`, `science`, `sports`, `technology` |
| Environment vars added to `docker-compose.yml` leak into Airflow task context | None | These are standard env vars, resolved by `os.environ.get()` inside task callables — same pattern as `USER_AGENT` |
| Type hints introduce mypy errors if enabled later | Low | Existing code is Python 3.11; `list[dict]` is valid syntax. No breaking changes |

## Rollback Plan

- **`.dockerignore` + `.gitignore`**: delete `.dockerignore`; restore `.gitignore` line 24
- **Input validation**: remove `_validate_article()` helper and the call to it in `extract_data_from_newsapi()`
- **Configurable params**: restore hardcoded `"country": "us"` in `extract_data_from_newsapi()`; remove config constants and env vars
- **Type hints**: revert the return type annotations (only cosmetic, no functional impact)

## Dependencies

- No new Python dependencies required (validation uses stdlib + existing `requests` types)
- `docker` available for build-context testing (optional)
- `.gitignore` edit must be committed before `.dockerignore` creation to prevent tracking issues

## Success Criteria

- [ ] `docker build .` shows substantially reduced context size (no `.env`, `.git/`, `logs/` in build output)
- [ ] `.dockerignore` is tracked by git (not blocked by `.gitignore`)
- [ ] `extract_data_from_newsapi()` logs a warning and drops articles missing `url` or `title` (but does not crash)
- [ ] At least one article with missing `url` in the NewsAPI response is validated and removed before downstream tasks
- [ ] `NEWS_API_COUNTRY=ar` produces `country=ar` in the NewsAPI request (verified via test mock)
- [ ] `NEWS_API_TOPIC=sports` produces `category=sports` in the NewsAPI request
- [ ] All four task callables have return type annotations
- [ ] Existing tests pass without modification (new tests added for validation + config)
- [ ] DAG loads with no import errors
