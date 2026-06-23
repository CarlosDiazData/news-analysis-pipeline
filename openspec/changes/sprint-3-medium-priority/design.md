# Design: Sprint 3 — Medium-Priority Operational Maturity

## Technical Approach

Four independent, low-risk improvements on existing pipeline modules. No new dependencies; validation uses stdlib only. Configurable-params reuses the stratified resolution pattern in `credentials.py` (`resolve_user_agent`, `resolve_max_scrape_workers`). Type hints are mechanical except `load.py`, which needs a return-value fix (Decision 1).

## Architecture Decisions

### Decision: load.py return type requires a return statement

| Option | Tradeoff | Decision |
|--------|----------|----------|
| Add `-> int` only | Annotation lies — function returns `None` on success | Rejected |
| `-> int` + `return cursor.rowcount` | Truthful; XCom changes `None`→`int` | **Chosen** |

`load_data_to_postgres` has no return after `conn.commit()` (implicit `None`). Safe: terminal task, no downstream XCom consumer; existing `test_insert_success` doesn't assert the return. Contradicts proposal's "behavior unchanged" — flagged for tasks.

### Decision: Response-structure validation inside _fetch_newsapi

| Option | Tradeoff | Decision |
|--------|----------|----------|
| Validate in `extract_data_from_newsapi` | `_fetch_newsapi` already holds raw `data` | Rejected |
| Validate inside `_fetch_newsapi` after status check | Co-located; runs per-retry (cheap) | **Chosen** |

Add `isinstance(articles, list)` guard + warning after the `status == "ok"` check. Missing/non-list `articles` is malformed (not transient) — `[]` is correct, no retry trigger. Per-article `_validate_article()` stays in `extract_data_from_newsapi`.

### Decision: Config defaults in config.py, imported by resolve functions

| Option | Tradeoff | Decision |
|--------|----------|----------|
| Hardcode in resolve funcs (like `resolve_user_agent`) | Two sources of truth if config.py also holds them | Rejected |
| Constants in `config.py`, imported by resolve funcs | Single source; matches `NEWS_API_ENDPOINT` usage | **Chosen** |

Resolution STRATEGY (Airflow Variable → env → .env → default) follows `resolve_user_agent` exactly; only the default VALUE source differs.

### Decision: Topic=None omits the category param

| Option | Tradeoff | Decision |
|--------|----------|----------|
| Always send `category` (even if None) | NewsAPI may reject `category=None` | Rejected |
| Add `category` only when topic is truthy | Backward-compatible; identical request when unset | **Chosen** |

## Data Flow

```
extract_data_from_newsapi()
  ├─ resolve_newsapi_key/country/topic()   # country→"us", topic→None defaults
  ├─ build params {apiKey, country, pageSize, [category]}
  ├─ _fetch_newsapi(endpoint, params)
  │     ├─ status == "ok" check            # existing
  │     ├─ validate articles key           # NEW: isinstance + warning
  │     └─ return articles list
  ├─ filter via _validate_article()        # NEW: drop missing url/title
  └─ return list[dict]                     # type-annotated
```

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `.dockerignore` | Create | Exclude secrets/metadata/build-irrelevant; keep `dags/`, `Dockerfile`, `requirements.lock` |
| `.gitignore` | Modify | Remove line 24 (`.dockerignore`) |
| `dags/pipeline/config.py` | Modify | Add `NEWS_API_COUNTRY = "us"`, `NEWS_API_TOPIC = None` |
| `dags/pipeline/credentials.py` | Modify | Add `resolve_newsapi_country()`, `resolve_newsapi_topic()` (import defaults from config) |
| `dags/pipeline/extract.py` | Modify | `_validate_article()`, response guard in `_fetch_newsapi`, resolved country/topic, `-> list[dict]` |
| `dags/pipeline/scrape.py` | Modify | `-> list[dict]` on `scrape_and_enrich_content` |
| `dags/pipeline/analyze.py` | Modify | `-> list[dict]` on `analyze_articles` |
| `dags/pipeline/load.py` | Modify | `-> int` + `return cursor.rowcount` after commit |
| `.env.example` | Modify | Add `NEWS_API_COUNTRY`, `NEWS_API_TOPIC` (commented defaults) |
| `docker-compose.yml` | Modify | Add both vars to airflow env (with defaults) |
| `tests/unit/test_extract.py` | Modify | `_validate_article` tests + missing-articles-key scenario |
| `tests/unit/test_credentials.py` | Create | Tests for both resolve functions |

## Interfaces / Contracts

```python
def _validate_article(article: dict) -> bool:
    # True iff url is non-empty str starting http(s):// AND title is non-empty str
    ...

def resolve_newsapi_country() -> str: ...        # default: config.NEWS_API_COUNTRY
def resolve_newsapi_topic() -> str | None: ...   # default: config.NEWS_API_TOPIC (None)

# extract.py params construction — category only when topic truthy
params = {"apiKey": news_api_key, "country": resolve_newsapi_country(), "pageSize": 100}
if (topic := resolve_newsapi_topic()):
    params["category"] = topic
```

## Testing Strategy

| Layer | What to Test | Approach |
|-------|-------------|----------|
| Unit | `_validate_article` (valid, missing url, empty title, non-http, ftp) | Direct calls in `test_extract.py` |
| Unit | Response missing `articles` key → warning + `[]` | `requests-mock` malformed body |
| Unit | Validation filters 1-of-3 invalid articles | `requests-mock`, assert `len == 2` |
| Unit | `resolve_newsapi_country/topic` default + env override | `monkeypatch.setenv`, patch `_try_airflow_variable` |
| Unit | `load_data_to_postgres` returns `cursor.rowcount` | Extend `test_insert_success` with return assertion |
| Integration | DAG imports with all annotations | Existing `test_dag_integrity.py` (no changes) |

## Migration / Rollout

No data migration or feature flags. Rollback per proposal. `.gitignore` edit MUST be committed before `.dockerignore` creation to prevent tracking issues.

## Open Questions

- [ ] psycopg2 `cursor.rowcount` may return `-1` for `executemany` — if so, `return len(records)` is a safer truthful `int`. Verify during apply.
