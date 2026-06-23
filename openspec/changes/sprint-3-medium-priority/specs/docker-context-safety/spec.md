# Docker Context Safety Specification

## Purpose

Ensure the Docker build context excludes secrets, version-control metadata, and build-irrelevant files, reducing context size from ~4MB to ~200KB while keeping `dags/`, `Dockerfile`, and `requirements.lock`.

## Requirements

### Requirement: Secrets and Metadata Exclusion

The `.dockerignore` MUST exclude `.env`, `.git/`, `logs/`, `__pycache__/`, `.pytest_cache/`, `.ruff_cache/`, `airflow_home_test/`, `.github/`, `Docs/`, `openspec/`, `data/`, `tests/`, `requirements.in`, `pyproject.toml`, `readme.md`, `LICENSE.txt`, `.gitignore`, `.env.example`, `init_db/`, `.atl/`, `config/`.

#### Scenario: Build context excludes .env

- GIVEN a `.dockerignore` file at the project root
- WHEN `docker build .` runs
- THEN `.env` SHALL NOT be in the build context (verified via `docker build --no-cache` output)

#### Scenario: Essential files remain in context

- GIVEN the `.dockerignore` file
- WHEN `docker build .` runs
- THEN `dags/`, `Dockerfile`, and `requirements.lock` SHALL be present in the build context

### Requirement: .gitignore Unblock for .dockerignore

The `.gitignore` MUST remove line 24 (`.dockerignore`) so the file is tracked by git.

#### Scenario: .dockerignore is tracked

- GIVEN `.gitignore` line 24 removed
- WHEN `git add .dockerignore` runs
- THEN the file SHALL be staged without error

#### Scenario: No accidental exclusion of dags/

- GIVEN the `.dockerignore` does NOT list `dags/` in exclusion patterns
- WHEN `docker build .` runs
- THEN the `dags/` directory SHALL be present in the build context
