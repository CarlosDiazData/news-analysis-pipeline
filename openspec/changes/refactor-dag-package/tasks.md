# Tasks: Refactor DAG Monolith → dags/pipeline/ Package

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | ~770 (380 additions + 390 deletions) |
| 400-line budget risk | High |
| Chained PRs recommended | Yes |
| Delivery strategy | ask-on-risk |

Decision needed before apply: Yes
Chained PRs recommended: Yes
Chain strategy: pending
400-line budget risk: High

### Suggested Work Units

| Unit | Goal | Likely PR | Notes |
|------|------|-----------|-------|
| 1 | Package + credentials move + config | PR #1 | ~30 lines. Creates `dags/pipeline/`, moves `credential_helper`, creates `config`, updates DAG imports. Independent slice. |
| 2 | Extract 4 modules + update 42 test mocks in lockstep | PR #2 | ~600 lines. extract → scrape → analyze → load. Clean move per module (no fallback). |
| 3 | Strip DAG bodies + verify zero old refs | PR #3 | ~140 lines. Remove function bodies, leftover imports, confirm `pytest` passes. |

## Phase 1: Package Setup (Infrastructure)

- [x] 1.1 Create `dags/pipeline/__init__.py` (empty)
- [x] 1.2 Create `dags/pipeline/config.py` — DAG_ID, NEWS_API_ENDPOINT, DEFAULT_CONN_ID, per-module logger stub
- [x] 1.3 Move `dags/credential_helper.py` → `dags/pipeline/credentials.py`; add `logging.getLogger(__name__)`; update dotenv path from `"..", ".env"` to `"../..", ".env"`
- [x] 1.4 Update `dags/news_etl_dag.py`: replace `from credential_helper import` with `from pipeline.credentials import` + `from pipeline.config import DAG_ID, NEWS_API_ENDPOINT`
- [x] 1.5 Verify: DagBag import errors = 0, `pytest tests/` passes

## Phase 2: Module Extraction (Core Implementation)

*Clean move per module: create module → update DAG import → update test mocks → remove function body from DAG → `pytest` after each step.*

- [ ] 2.1 Create `dags/pipeline/extract.py` → `extract_data_from_newsapi` + per-module logger. Update DAG import. Update `tests/unit/test_extract.py` (5 patch paths + 5 `from news_etl_dag` imports → `pipeline.extract`). Remove function body from DAG. `pytest tests/unit/test_extract.py` passes.
- [ ] 2.2 Create `dags/pipeline/scrape.py` → `_is_retryable`, `_scrape_single_article`, `scrape_and_enrich_content` + per-module logger. Update DAG import. Update `tests/unit/test_scrape.py` (4 `from news_etl_dag` imports → `pipeline.scrape`, 2 `@patch("news_etl_dag.xxx")` → `pipeline.scrape`, 1 `patch("news_etl_dag._scrape_single_article")` → `pipeline.scrape`). Remove function body from DAG. `pytest tests/unit/test_scrape.py` passes.
- [ ] 2.3 Create `dags/pipeline/analyze.py` → `analyze_articles` + per-module logger. Update DAG import. Update `tests/unit/test_analyze.py` (4 `from news_etl_dag` imports → `pipeline.analyze`). Remove function body from DAG. `pytest tests/unit/test_analyze.py` passes.
- [ ] 2.4 Create `dags/pipeline/load.py` → `load_data_to_postgres`, SQL INSERT constant + per-module logger. Update DAG import. Update `tests/unit/test_load.py` (2 `from news_etl_dag` imports + 1 `patch("news_etl_dag.get_db_connection")` → `pipeline.load`). Remove function body from DAG. `pytest tests/unit/test_load.py` passes.
- [ ] 2.5 Update `tests/integration/test_db_load.py` (3 `from news_etl_dag` imports + 4 `patch("news_etl_dag.get_db_connection")` → `pipeline.load`). `pytest tests/integration/` passes.
- [ ] 2.6 Final: `pytest tests/unit/ tests/integration/` — all pass after full Phase 2

## Phase 3: Strip DAG (Wiring)

- [ ] 3.1 Remove remaining function definitions from `dags/news_etl_dag.py` — keep only imports + DAG definition + task wiring
- [ ] 3.2 Remove unused stdlib imports: `json`, `ThreadPoolExecutor`, `as_completed`, `urlparse`, `RobotFileParser`, `BeautifulSoup`, `spacy`, `TextBlob` (moved to their respective pipeline modules)
- [ ] 3.3 Verify: DAG ≤ 100 lines, DagBag import errors = 0, task IDs unchanged

## Phase 4: Cleanup

- [ ] 4.1 Verify zero `from news_etl_dag import` / `patch("news_etl_dag.` references remain in test files
- [ ] 4.2 Final: `pytest tests/` — full suite passes
- [ ] 4.3 Confirm: same DAG_ID, same schedule, same task IDs, same behavior
