# Extract Retry Specification

## Purpose

Add tenacity-based retry with exponential backoff to NewsAPI extraction, mirroring the proven pattern from `scrape.py` (lines 58–67).

## Requirements

### Requirement: Transient Error Retry

`extract_data_from_newsapi` MUST retry transient errors using tenacity with `stop_after_attempt(3)`, `wait_exponential(multiplier=1, min=1, max=4)`, `retry=retry_if_exception(_is_retryable)`, `reraise=True`.

#### Scenario: First attempt succeeds

- GIVEN NewsAPI returns HTTP 200 with `{"status": "ok"}`
- WHEN `extract_data_from_newsapi` calls the endpoint
- THEN it returns parsed articles on the first attempt
- AND no retry occurs

#### Scenario: Rate limit retries and succeeds

- GIVEN NewsAPI returns HTTP 429 on attempt 1, 200 on attempt 2
- WHEN `extract_data_from_newsapi` executes
- THEN it retries once with exponential backoff
- AND returns parsed articles

#### Scenario: Server error retries then succeeds

- GIVEN NewsAPI returns HTTP 503 on attempts 1 and 2, 200 on attempt 3
- WHEN `extract_data_from_newsapi` executes
- THEN it retries twice with increasing backoff
- AND returns parsed articles

#### Scenario: Connection timeout retries

- GIVEN `requests.get` raises `ConnectionError` or `Timeout`
- WHEN `extract_data_from_newsapi` executes
- THEN it retries up to 3 times
- AND raises `AirflowException` if all attempts fail

### Requirement: Skip Non-Retryable Errors

The `_is_retryable` helper MUST return `True` for all exceptions **except** HTTP 404. This includes: HTTP 429, 5xx, `ConnectionError`, `Timeout`, and custom exceptions raised by the body-status check (e.g., `RuntimeError` for `rateLimited` body).

#### Scenario: 404 raises immediately

- GIVEN NewsAPI returns HTTP 404
- WHEN `extract_data_from_newsapi` executes
- THEN `_is_retryable` returns `False`
- AND the function raises `AirflowException` without retrying

### Requirement: Retry on Error-in-Body

A private inner function (e.g., `_fetch_newsapi`) MUST be decorated with `@retry`, NOT `extract_data_from_newsapi` itself. Decorating the outer function would also retry credential resolution (`resolve_newsapi_key()`), which is a permanent error.

The inner function MUST include `requests.get()` + `raise_for_status()` + `response.json()` + `data.get("status") != "ok"` check (NewsAPI can return 200 with `{"status": "error", "code": "rateLimited"}` in body).

#### Scenario: Rate-limited body triggers retry

- GIVEN NewsAPI returns HTTP 200 with body `{"status": "error", "code": "rateLimited"}`
- WHEN the inner function checks `data.get("status") != "ok"`
- THEN it raises an exception caught by tenacity
- AND the retry decorator retries

#### Scenario: All retries exhausted

- GIVEN NewsAPI returns transient errors for all 3 attempts
- WHEN `extract_data_from_newsapi` finishes the last retry
- THEN it raises `AirflowException` with `reraise=True`
- AND the Airflow task fails
