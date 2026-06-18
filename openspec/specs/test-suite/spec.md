# Test Suite Specification

## Purpose

Define the testing framework and coverage for the news ETL pipeline to ensure reliable, regression-safe development.

## Requirements

### Requirement: Unit Tests for Core ETL Functions

The system MUST provide unit tests covering extraction, scraping, NLP analysis, and data loading.

#### Scenario: Extraction returns parsed articles

- GIVEN a mock NewsAPI response with valid articles
- WHEN `extract_data_from_newsapi` is called
- THEN it returns a list of parsed article dicts

#### Scenario: Extraction raises on API error

- GIVEN NewsAPI returns a non-200 status
- WHEN `extract_data_from_newsapi` is called
- THEN it raises `AirflowException`

#### Scenario: Scraping extracts full content

- GIVEN a mock HTML page with `<p>` elements
- WHEN `scrape_and_enrich_content` processes a URL
- THEN the article `content` field is updated

#### Scenario: NLP adds sentiment and entities

- GIVEN an article with text content
- WHEN `analyze_articles` processes it
- THEN it returns `sentiment_polarity`, `sentiment_subjectivity`, `named_entities`

#### Scenario: Load returns 0 for empty input

- GIVEN no articles from upstream
- WHEN `load_data_to_postgres` is called
- THEN it logs a warning and returns 0

### Requirement: Integration Tests with PostgreSQL

The system SHALL include integration tests using a PostgreSQL service container.

#### Scenario: Insert and read records

- GIVEN a running PostgreSQL with the `news_articles` table
- WHEN `load_data_to_postgres` inserts valid articles
- THEN the records appear with correct column values

### Requirement: No Real HTTP in Tests

Tests MUST mock or record HTTP requests using `requests-mock` or `vcrpy`.

#### Scenario: NewsAPI call is mocked

- GIVEN a `requests-mock` intercept for the NewsAPI endpoint
- WHEN `extract_data_from_newsapi` executes
- THEN no real HTTP request reaches the network

### Requirement: Airflow DAG Integrity

The test suite MUST validate that DAGs have no import errors, cyclical dependencies, or syntax issues.

#### Scenario: DAG loads successfully

- GIVEN the Airflow DagBag context
- WHEN the DAG files are parsed
- THEN len(dagbag.import_errors) SHALL be 0

#### Scenario: DAG has no cyclical dependencies

- GIVEN the parsed DAG
- WHEN task dependencies are analyzed
- THEN no cycles SHALL exist in the task graph

### Requirement: Database Clean State

Integration tests MUST ensure test isolation via table truncation or transaction rollbacks between runs.

#### Scenario: Integration test isolation

- GIVEN a completed integration test that inserted data into PostgreSQL
- WHEN the next integration test starts
- THEN the database SHALL be in a clean state (tables truncated or transaction rolled back)
- AND no residual data from previous tests SHALL affect results
