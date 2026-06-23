# Configurable NewsAPI Params Specification

## Purpose

Make NewsAPI `country` and `category` query parameters configurable via Airflow Variable, environment variable, `.env`, or built-in default — following the existing stratified resolution pattern — without code changes.

## Requirements

### Requirement: Stratified Resolution for Country

The system MUST resolve `NEWS_API_COUNTRY` with stratified fallback: Airflow Variable → env var → `.env` → built-in default `"us"`.

#### Scenario: Default country is us

- GIVEN no `NEWS_API_COUNTRY` set in any resolution layer
- WHEN `resolve_newsapi_country()` is called
- THEN it SHALL return `"us"`

#### Scenario: Environment variable overrides default

- GIVEN `NEWS_API_COUNTRY=ar` set in environment
- WHEN `resolve_newsapi_country()` is called
- THEN it SHALL return `"ar"`

### Requirement: Stratified Resolution for Topic

The system MUST resolve `NEWS_API_TOPIC` with stratified fallback: Airflow Variable → env var → `.env` → built-in default `None` (no topic filter). The value MUST map to the NewsAPI `category` query param.

#### Scenario: Topic defaults to None

- GIVEN no `NEWS_API_TOPIC` set
- WHEN `resolve_newsapi_topic()` is called
- THEN it SHALL return `None`

#### Scenario: Topic value maps to category param

- GIVEN `NEWS_API_TOPIC=sports` is set
- WHEN the NewsAPI request is built with params
- THEN the request SHALL include `category=sports`
- AND `topic` SHALL NOT be in the request params

### Requirement: Extract Uses Resolved Params

`extract_data_from_newsapi()` MUST call `resolve_newsapi_country()` and `resolve_newsapi_topic()` instead of hardcoding `"country": "us"`.

#### Scenario: Custom country propagates to API call

- GIVEN `NEWS_API_COUNTRY=ar` resolved
- WHEN `extract_data_from_newsapi()` builds params
- THEN `country=ar` SHALL appear in the API request

### Requirement: Backward Compatibility

If `NEWS_API_COUNTRY` is unset, behavior MUST match the previous hardcoded `"us"` default. If `NEWS_API_TOPIC` is unset or `None`, no category filter SHALL be applied.

#### Scenario: Unset params produce identical request URL

- GIVEN no newsapi params configured
- WHEN comparing the request URL before and after the change
- THEN the base URL and `country=us` SHALL match exactly
