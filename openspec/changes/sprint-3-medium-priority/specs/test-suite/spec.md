# Delta for Test Suite

## ADDED Requirements

### Requirement: Article Validation Tests

The test suite MUST include unit tests for `_validate_article()` covering valid articles, missing `url`, missing `title`, empty strings, and non-http URLs.

#### Scenario: Valid article returns True

- GIVEN a dict with `url: "https://example.com/a"` and `title: "Test"`
- WHEN `_validate_article()` is called
- THEN it SHALL return `True`

#### Scenario: Missing url returns False

- GIVEN a dict with no `url` key
- WHEN `_validate_article()` is called
- THEN it SHALL return `False`

#### Scenario: Non-http url returns False

- GIVEN a dict with `url: "ftp://example.com/a"`
- WHEN `_validate_article()` is called
- THEN it SHALL return `False`

#### Scenario: Validation filters invalid articles in extraction

- GIVEN a NewsAPI response where 1 of 3 articles has no `url`
- WHEN `extract_data_from_newsapi()` processes it
- THEN the returned list SHALL contain exactly 2 articles

### Requirement: Config Resolution Tests

The test suite MUST include unit tests for `resolve_newsapi_country()` and `resolve_newsapi_topic()` covering default values, env var overrides, and Airflow Variable overrides.

#### Scenario: Empty env returns default country

- GIVEN no `NEWS_API_COUNTRY` in env or Airflow Variables
- WHEN `resolve_newsapi_country()` is called
- THEN it SHALL return `"us"`

#### Scenario: Env var overrides country default

- GIVEN `NEWS_API_COUNTRY=fr` set in os.environ
- WHEN `resolve_newsapi_country()` is called
- THEN it SHALL return `"fr"`

#### Scenario: Empty env returns None for topic

- GIVEN no `NEWS_API_TOPIC` in env or Airflow Variables
- WHEN `resolve_newsapi_topic()` is called
- THEN it SHALL return `None`
