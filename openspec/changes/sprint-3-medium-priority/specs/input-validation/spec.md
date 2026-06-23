# Input Validation Specification

## Purpose

Validate NewsAPI response structure and article fields immediately after fetching, before downstream processing, to prevent silent failures from malformed or incomplete data.

## Requirements

### Requirement: NewsAPI Response Structure Validation

The system MUST validate the top-level NewsAPI response JSON structure after the `status == "ok"` check. The `articles` key MUST exist and be a list.

#### Scenario: Response missing articles key

- GIVEN a NewsAPI response with `status: "ok"` but no `articles` key
- WHEN `extract_data_from_newsapi` processes the response
- THEN it SHALL log a warning and return an empty list
- AND it SHALL NOT raise an exception

### Requirement: Individual Article Validation

The system MUST validate each article dict after extraction. Articles missing `url` (non-empty string) or `title` (non-empty string) MUST be dropped with a logged warning.

#### Scenario: Article missing url is dropped

- GIVEN a NewsAPI response with one article that has no `url` field
- WHEN `extract_data_from_newsapi` processes the articles
- THEN the article SHALL be excluded from the returned list
- AND a warning SHALL be logged with the article index

#### Scenario: Article missing title is dropped

- GIVEN a NewsAPI response with one article where `title` is an empty string
- WHEN `extract_data_from_newsapi` processes the articles
- THEN the article SHALL be excluded from the returned list
- AND a warning SHALL be logged with the article index

#### Scenario: Valid article passes validation

- GIVEN an article with non-empty `url` starting with `http` and non-empty `title`
- WHEN `_validate_article` processes it
- THEN it SHALL return `True`

### Requirement: No Pydantic Dependency

Validation MUST use only Python stdlib. No Pydantic, marshmallow, or schema library SHALL be added.

#### Scenario: Validation uses dict checks only

- GIVEN the `_validate_article` helper
- WHEN inspecting its implementation
- THEN it SHALL use only `isinstance`, `len`, `str.startswith`, or similar stdlib calls
