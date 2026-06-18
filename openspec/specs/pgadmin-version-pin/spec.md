# pgAdmin Version Pin Specification

## Purpose

Replace the floating `latest` Docker tag for pgAdmin with a specific, tested stable version to ensure reproducible development environments.

## Requirements

### Requirement: Pinned Image Tag

`docker-compose.yml` MUST reference a specific pgAdmin version tag instead of `latest`.

#### Scenario: Specific tag in compose

- GIVEN `docker-compose.yml`
- WHEN inspecting the pgAdmin service `image` field
- THEN it references `dpage/pgadmin4:8.14` (or a confirmed-stable version) not `latest`

### Requirement: Inline Version Documentation

`docker-compose.yml` SHALL include a comment explaining the pinned version and update policy.

#### Scenario: Comment explains pin

- GIVEN `docker-compose.yml`
- WHEN reading the pgAdmin image line
- THEN a comment states the reason for pinning and when to re-evaluate

### Requirement: Clean Startup

The pinned version MUST be a stable release that starts without deprecation or incompatibility warnings.

#### Scenario: pgAdmin starts clean

- GIVEN `docker compose up pgadmin`
- WHEN inspecting container logs at startup
- THEN no version-related warnings or errors appear
