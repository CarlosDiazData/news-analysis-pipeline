# Codebase Consistency Specification

## Purpose

Ensure all Airflow task callables across the pipeline have return type annotations, making the public API surface self-documenting and type-checker ready.

## Requirements

### Requirement: Extract Task Return Type

`extract_data_from_newsapi()` MUST declare a `-> list[dict]` return type annotation.

#### Scenario: Return type is declared

- GIVEN `dags/pipeline/extract.py`
- WHEN inspecting `extract_data_from_newsapi`
- THEN its signature SHALL include `-> list[dict]`

### Requirement: Scrape Task Return Type

`scrape_and_enrich_content()` MUST declare a `-> list[dict]` return type annotation.

#### Scenario: Return type is declared

- GIVEN `dags/pipeline/scrape.py`
- WHEN inspecting `scrape_and_enrich_content`
- THEN its signature SHALL include `-> list[dict]`

### Requirement: Analyze Task Return Type

`analyze_articles()` MUST declare a `-> list[dict]` return type annotation.

#### Scenario: Return type is declared

- GIVEN `dags/pipeline/analyze.py`
- WHEN inspecting `analyze_articles`
- THEN its signature SHALL include `-> list[dict]`

### Requirement: Load Task Return Type

`load_data_to_postgres()` MUST declare a `-> int` return type annotation.

#### Scenario: Return type is declared

- GIVEN `dags/pipeline/load.py`
- WHEN inspecting `load_data_to_postgres`
- THEN its signature SHALL include `-> int`

### Requirement: No Breaking Changes

Type annotations MUST NOT alter function behavior, add imports, or introduce `mypy` dependencies. Existing ruff type checks MUST continue passing.

#### Scenario: DAG imports without error

- GIVEN all four modules with added type annotations
- WHEN `news_etl_dag.py` is parsed by Airflow DagBag
- THEN no import errors SHALL occur
