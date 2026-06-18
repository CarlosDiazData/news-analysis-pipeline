# Concurrent Scraping Specification

## Purpose

Parallelize article scraping to reduce total execution time from ~25 minutes to ≤5 minutes while respecting target server rate limits.

## Requirements

### Requirement: ThreadPoolExecutor

The scraper MUST use `ThreadPoolExecutor` with configurable `max_workers`.

#### Scenario: Concurrent processing of 100 articles

- GIVEN 100 articles with valid URLs
- WHEN scraping runs with `max_workers=5`
- THEN all articles are processed in parallel batches
- AND total time is ≤5 minutes

#### Scenario: Worker count configurable via env

- GIVEN `MAX_SCRAPE_WORKERS=3` is set
- WHEN the scraper initializes
- THEN it uses 3 workers

#### Scenario: Graceful thread shutdown on cancellation

- GIVEN a running concurrent scraping task with active ThreadPoolExecutor
- WHEN Airflow sends SIGTERM (timeout or manual cancellation)
- THEN the executor shuts down gracefully via context manager
- AND no zombie threads remain in the container

### Requirement: Retry with Exponential Backoff

The scraper MUST retry failed requests using `tenacity` with exponential backoff.

#### Scenario: Transient failure retries

- GIVEN a URL returns 429 (Too Many Requests)
- WHEN the scraper encounters this response
- THEN it retries with backoff up to the configured max

#### Scenario: Permanent failure skipped

- GIVEN a URL returns 404
- WHEN the scraper encounters this response
- THEN it logs the error and skips without retrying

### Requirement: robots.txt Compliance

The scraper MUST respect `robots.txt` via `urllib.robotparser`. The robots.txt for each domain MUST be fetched and parsed ONCE before initializing the ThreadPoolExecutor, then cached in a dictionary keyed by domain.

#### Scenario: Disallowed URL skipped

- GIVEN a URL is disallowed by the site's `robots.txt`
- WHEN the scraper encounters this URL
- THEN it skips scraping and logs a warning

#### Scenario: robots.txt fetched once for multiple articles from same domain

- GIVEN 50 articles from the same domain
- WHEN the scraping function initializes
- THEN robots.txt is fetched exactly ONCE for that domain
- AND all 50 articles use the cached parser from the domain dictionary
- AND no additional HTTP requests are made to robots.txt

### Requirement: Configurable User-Agent

The scraper MUST use a configurable `USER_AGENT` string, not the default Python `urllib` agent.

#### Scenario: Custom UA in headers

- GIVEN `USER_AGENT=NewsETL/1.0` is set
- WHEN the scraper makes an HTTP request
- THEN the `User-Agent` header is `NewsETL/1.0`
