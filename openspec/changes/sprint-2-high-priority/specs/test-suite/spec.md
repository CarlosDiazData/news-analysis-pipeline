# Delta for Test Suite

## ADDED Requirements

### Requirement: SLA Callback Tests

The test suite MUST validate the SLA miss callback writes the correct JSON line format.

#### Scenario: Callback writes valid JSON

- GIVEN a mock `SLAMiss` with known `dag_id`, `task_id`, `execution_date`
- WHEN the `sla_miss_callback` executes
- THEN it appends one valid JSON line to the log path
- AND the JSON contains `timestamp`, `dag_id`, `task_id`, `scheduled_time`, `sla_exceeded_by`
- AND `sla_exceeded_by` is computed as `datetime.now() - (execution_date + task.sla)`

#### Scenario: Callback appends without overwrite

- GIVEN an existing log file with 2 prior SLA miss lines
- WHEN a third SLA miss triggers the callback
- THEN the log file contains exactly 3 JSON lines
- AND all prior lines are preserved

### Requirement: Extract Retry Tests

The test suite MUST verify tenacity retry behavior on extract with mocked HTTP responses.

#### Scenario: Retries on transient error

- GIVEN `requests-mock` returning HTTP 429 (first call), HTTP 200 (second call)
- WHEN `extract_data_from_newsapi` executes
- THEN it succeeds after exactly one retry

#### Scenario: No retry on 404

- GIVEN `requests-mock` returning HTTP 404
- WHEN `extract_data_from_newsapi` executes
- THEN `_is_retryable` returns `False`
- AND the function raises `AirflowException` without retrying

#### Scenario: Retry on rate-limited body

- GIVEN `requests-mock` returning 200 with `{"status": "error", "code": "rateLimited"}` (first call), then 200 with `{"status": "ok"}` (retry)
- WHEN `extract_data_from_newsapi` executes
- THEN the inner function detects non-ok status and raises
- AND tenacity retries the inner call
- AND the function eventually succeeds

#### Scenario: All retries exhausted

- GIVEN `requests-mock` returning HTTP 500 for all 3 attempts
- WHEN `extract_data_from_newsapi` executes
- THEN it retries 3 times with exponential backoff
- AND raises an exception after the final attempt (reraise=True)

### Requirement: Lock File Presence Test

The test suite MUST verify `requirements.lock` exists and is in sync with `requirements.in`.

#### Scenario: Lock file exists

- GIVEN the repository root
- WHEN `os.path.exists("requirements.lock")` is checked
- THEN it SHALL return `True`

#### Scenario: Lock is in sync with .in

- GIVEN `requirements.in` and `requirements.lock` both exist
- WHEN `pip-compile --check requirements.in -o requirements.lock` runs
- THEN it SHALL exit 0 (in sync)
- AND exit non-zero if the lock is stale (requirements.in changed without regenerating the lock)
