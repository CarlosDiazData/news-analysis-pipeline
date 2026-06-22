# Tasks: Sprint 3 — Medium-Priority Operational Maturity

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | ~195 |
| 400-line budget risk | Low |
| Chained PRs recommended | No |
| Suggested split | Single PR |
| Delivery strategy | ask-always |
| Chain strategy | N/A |

Decision needed before apply: No (all resolved)
Chained PRs recommended: No
Chain strategy: N/A
400-line budget risk: Low

## Phase 1: Docker Context Safety

- [x] 1.1 Remove line 24 (`.dockerignore`) from `.gitignore`
- [x] 1.2 Create `.dockerignore` excluding: `.env`, `.git/`, `logs/`, `__pycache__/`, `.pytest_cache/`, `.ruff_cache/`, `airflow_home_test/`, `.github/`, `Docs/`, `openspec/`, `data/`, `tests/`, `requirements.in`, `pyproject.toml`, `readme.md`, `LICENSE.txt`, `.gitignore`, `.env.example`, `init_db/`, `.atl/`, `config/`
- [x] 1.3 Run `docker build --no-cache .` and verify context excludes `.env` and `.git/`, includes `dags/`, `Dockerfile`, `requirements.lock`

## Phase 2: Configuration Foundation

- [x] 2.1 Add `NEWS_API_COUNTRY = "us"` and `NEWS_API_TOPIC = None` to `dags/pipeline/config.py`
- [x] 2.2 Add `resolve_newsapi_country()` and `resolve_newsapi_topic()` to `dags/pipeline/credentials.py` following `resolve_user_agent()` stratified pattern (Airflow Variable → env → .env → config default); import defaults from `config.py`
- [x] 2.3 Add `NEWS_API_COUNTRY` and `NEWS_API_TOPIC` (commented with defaults) to `.env.example`
- [x] 2.4 Add `NEWS_API_COUNTRY` and `NEWS_API_TOPIC` env vars to `docker-compose.yml` airflow service

## Phase 3: Core Implementation

- [x] 3.1 Add `_validate_article(article: dict) -> bool` helper to `dags/pipeline/extract.py`: checks `url` is non-empty str starting with `http` AND `title` is non-empty str; log warnings on failure with article index
- [x] 3.2 Add response-structure guard in `_fetch_newsapi()` after status check: `isinstance(articles, list)` → warn + return `[]` if non-list
- [x] 3.3 Import and call `resolve_newsapi_country()` and `resolve_newsapi_topic()` in `extract_data_from_newsapi()`; build params with `country` from resolved value and `category` only when topic is truthy
- [x] 3.4 Add `-> list[dict]` return type to `extract_data_from_newsapi()` in `extract.py`
- [x] 3.5 Add `-> list[dict]` return type to `scrape_and_enrich_content()` in `scrape.py`
- [x] 3.6 Add `-> list[dict]` return type to `analyze_articles()` in `analyze.py`
- [x] 3.7 Add `-> int` return type to `load_data_to_postgres()` in `load.py`; add `return len(records)` after `conn.commit()` (line 73) — **NOTE: used len(records) instead of cursor.rowcount per design open question (executemany may return -1)**

## Phase 4: Testing

- [x] 4.1 Create `tests/unit/test_credentials.py` with tests for `resolve_newsapi_country()` (default `"us"`, env override `"fr"`) and `resolve_newsapi_topic()` (default `None`, env override `"sports"`)
- [x] 4.2 Add `TestValidateArticle` class to `tests/unit/test_extract.py`: valid article returns True, missing `url` returns False, empty `title` returns False, `ftp://` url returns False, non-http url returns False
- [x] 4.3 Add integration test in `test_extract.py`: response missing `articles` key returns `[]` (no crash)
- [x] 4.4 Add integration test in `test_extract.py`: 1 of 3 articles has no `url` → returned list has 2 articles
- [x] 4.5 Modify `test_insert_success` in `tests/unit/test_load.py` to assert return value equals `len(records)`
- [x] 4.6 Run full test suite (`pytest tests/`) — verify all existing tests pass and new tests pass
- [x] 4.7 Verify DAG loads: `python -c "from dags.news_etl_dag import dag"` succeeds with no import errors
