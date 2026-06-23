# Proposal: Refactor DAG Monolith → dags/pipeline/

## Intent

`dags/news_etl_dag.py` (467 lines) bundles 6 responsibilities into a single module. Tests mock `news_etl_dag.*` paths (42 references across 5 files), coupling tests to module internals. Splitting into a `dags/pipeline/` subpackage improves testability and enables independent reasoning per pipeline stage — without requiring Docker mount changes or PYTHONPATH configuration.

## Scope

### In Scope
- Create `dags/pipeline/` package: `config.py`, `extract.py`, `scrape.py`, `analyze.py`, `load.py`, `credentials.py`
- Move `dags/credential_helper.py` → `dags/pipeline/credentials.py` (eliminates cross-directory import)
- Move functions/constants per module, keeping behavior identical
- Per-module loggers (`logging.getLogger(__name__)`) — no shared logger
- Update DAG imports: `from dags.pipeline.X import ...`
- Update 42 test mock paths to new package paths
- Strip DAG to imports + DAG definition (~80 lines)

### Out of Scope
- Any functional changes, type hints, docstrings, or linting
- DAG structure, task IDs, or scheduling changes
- CI/CD changes beyond test mock updates
- Backward-compat fallback code (clean move per module, no duplication)

## Capabilities

### New Capabilities
None — structural refactor, no new spec-level behavior.

### Modified Capabilities
None — existing specs (test-suite, concurrent-scraping, credential-management, pgadmin-version-pin, ci-pipeline) have zero requirement changes.

## Approach

4-phase incremental migration with 3 deliverable PRs. `dags/` is already in Airflow's Python path — no Docker mount or PYTHONPATH changes needed.

| # | Phase | Key Actions | Verify |
|---|-------|-------------|--------|
| 1 | Package setup | Create `dags/pipeline/` + `__init__.py`, move `credential_helper.py` → `credentials.py`, update imports in DAG and tests | DAG parses (DagBag errors = 0) |
| 2 | Module extraction | Move one module at a time (config → extract → scrape → analyze → load), update DAG imports and test mocks in lockstep | `pytest tests/unit/` after each move |
| 3 | Strip DAG | Remove all function bodies, leave only DAG definition + imports (~80 lines) | DAG integrity tests pass |
| 4 | Test cleanup | Verify zero `news_etl_dag` references in tests | `grep -r 'news_etl_dag' tests/` = empty |

### Clean Move Per Module (no fallback)
1. Move function/constant definitions to `dags/pipeline/<module>.py`
2. Update DAG import: `from dags.pipeline.extract import extract_data_from_newsapi`
3. Update all test mock paths: `news_etl_dag.X` → `dags.pipeline.<module>.X`
4. Verify with `pytest tests/unit/` after each move
5. Remove original definitions from DAG file (no duplication at any step)

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `dags/pipeline/` | New | 6 modules: config, credentials, extract, scrape, analyze, load, __init__ |
| `dags/credential_helper.py` | Removed | Moved → `dags/pipeline/credentials.py` |
| `dags/news_etl_dag.py` | Modified | Stripped to imports + DAG definition (~80 lines) |
| `tests/conftest.py` | Modified | Remove `dags/` from sys.path (no longer needed) |
| `tests/unit/test_extract.py` | Modified | 10 mock paths updated |
| `tests/unit/test_scrape.py` | Modified | 12 mock paths updated |
| `tests/unit/test_analyze.py` | Modified | 4 mock paths updated |
| `tests/unit/test_load.py` | Modified | 9 mock paths updated |
| `tests/integration/test_db_load.py` | Modified | 7 mock paths updated |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| 42 test mock paths break | High | Update in lockstep per module, `pytest` after each move |
| Credential import breaks DAG parse | Medium | Move in Phase 1 first; verify with DagBag before any module extraction |
| Circular imports within pipeline/ | Low | Modules import only stdlib + 3rd-party, never each other |
| Airflow can't find `dags/pipeline/` | Low | `dags/` is already in Airflow's Python path; subpackage is auto-discoverable |

## PR Strategy

| PR | Phases | Scope | Est. Lines |
|----|--------|-------|------------|
| #1 | Phase 1 | Package + `__init__.py` + credentials move + conftest | ~30 |
| #2 | Phase 2 | Module extraction (config→extract→scrape→analyze→load) + test mocks | ~600 |
| #3 | Phase 3–4 | Strip DAG + cleanup + verify zero references | ~140 |

## Rollback Plan

`git revert` the commits. Single command, clean rollback.

## Dependencies

- None. No external deps, no new packages, no Docker changes, no PYTHONPATH config.
- Phases 2–4 depend on Phase 1 completion.

## Success Criteria

- [ ] `dags/pipeline/` package exists with 6 modules
- [ ] DAG parses without import errors (`DagBag.import_errors == 0`)
- [ ] All existing tests pass with updated import paths
- [ ] Zero `news_etl_dag` references in `tests/`
- [ ] DAG file ≤ 100 lines (currently 467)
- [ ] Pipeline behavior unchanged: same task IDs, same DAG_ID, same schedule
