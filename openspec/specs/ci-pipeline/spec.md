# CI Pipeline Specification

## Purpose

Automate linting, testing, and Docker image building on every push to main and pull request.

## Requirements

### Requirement: Lint with Ruff

CI SHALL run `ruff check` AND `ruff format --check` on all Python files.

#### Scenario: Lint passes on clean code

- GIVEN no lint violations in source files
- WHEN the lint job runs `ruff check`
- THEN it exits with code 0

#### Scenario: Lint fails on violations

- GIVEN source files with lint errors
- WHEN the lint job runs `ruff check`
- THEN it exits with non-zero code

#### Scenario: Code is not formatted

- GIVEN source files with improper formatting
- WHEN the lint job runs `ruff format --check`
- THEN it exits with a non-zero code

### Requirement: Test with PostgreSQL Service Container

CI MUST run pytest against a PostgreSQL service container — no `pytest-postgresql`.

#### Scenario: Tests pass with service container

- GIVEN a workflow with `postgres` service container on `5432`
- WHEN the test job runs `pytest`
- THEN tests execute and pass against the live service

### Requirement: Docker Build Verification

CI SHALL build the Docker image to validate the Dockerfile and requirements.

#### Scenario: Build succeeds

- GIVEN the Dockerfile and requirements.txt
- WHEN `docker build` executes
- THEN it produces an image without errors

### Requirement: Trigger Rules

CI MUST trigger on push to `main` and on pull requests targeting `main`.

#### Scenario: Push triggers all jobs

- GIVEN a push event on `main`
- WHEN the workflow evaluates the trigger
- THEN lint, test, and build jobs execute

### Requirement: Pip Dependency Caching

CI SHOULD cache pip dependencies to speed up runs.

#### Scenario: Cache hit skips download

- GIVEN a cached pip directory matching requirements.txt checksum
- WHEN `pip install` runs
- THEN cached packages are used instead of downloading

### Requirement: Docker Layer Caching

CI MUST use Docker layer caching via `cache-from` and `cache-to` in GitHub Actions to reduce build times.

#### Scenario: Docker cache hit

- GIVEN a previous Docker build cached in GitHub Actions
- WHEN `docker build` executes with unchanged Dockerfile layers
- THEN it reuses cached layers instead of rebuilding
- AND build time is reduced from minutes to seconds

### Requirement: Secrets Configuration

Workflow secrets SHALL include `NEWS_API_KEY`, `POSTGRES_PASSWORD`, `POSTGRES_USER`.

#### Scenario: Missing secret fails gracefully

- GIVEN `NEWS_API_KEY` is unset in CI
- WHEN the extraction test runs
- THEN it fails with a clear missing-key error
