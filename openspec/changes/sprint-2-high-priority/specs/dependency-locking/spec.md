# Dependency Locking Specification

## Purpose

Lock Python dependencies with pip-tools for reproducible builds: `requirements.in` (loose constraints) + `requirements.lock` (pinned transitive deps).

## Requirements

### Requirement: Requirements Split

`requirements.txt` MUST be renamed to `requirements.in`. `requirements.lock` MUST be generated via `pip-compile requirements.in -o requirements.lock`.

The lock file is committed to the repository. A developer regenerates it (via `pip-compile`) whenever `requirements.in` changes. CI does NOT run `pip-compile` — it only installs from the pre-generated lock.

#### Scenario: Requirements files exist

- GIVEN the repository root
- WHEN `ls` is called
- THEN `requirements.in` and `requirements.lock` SHALL exist
- AND `requirements.txt` SHALL NOT exist

#### Scenario: Lock is generated from .in

- GIVEN `requirements.in` with loose constraints
- WHEN `pip-compile requirements.in -o requirements.lock` runs
- THEN `requirements.lock` SHALL contain pinned versions for every transitive dependency

### Requirement: Airflow Version Pin

`requirements.in` MUST pin `apache-airflow==2.11.2` to match the base image `apache/airflow:2.11.2-python3.11`.

#### Scenario: Pin prevents drift

- GIVEN `apache-airflow==2.11.2` in `requirements.in`
- WHEN `pip-compile` resolves the dependency graph
- THEN `apache-airflow==2.11.2` SHALL appear verbatim in `requirements.lock`
- AND transitive Airflow providers SHALL be compatible with 2.11.2

### Requirement: Dockerfile Installs from Lock

The Dockerfile MUST `COPY requirements.lock` and install via `pip install -r requirements.lock`.

#### Scenario: Build uses lock

- GIVEN the Dockerfile
- WHEN `docker build` executes
- THEN it copies `requirements.lock` (not `requirements.txt`)
- AND `pip install` runs against the lock file
- AND the build succeeds with pinned dependencies
