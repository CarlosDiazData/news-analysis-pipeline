# Credential Management Specification

## Purpose

Define a stratified, secure credential resolution strategy and eliminate all hardcoded secrets from config files and source code.

## Requirements

### Requirement: Stratified Resolution Order

The system MUST resolve credentials in strict order: Airflow Connection > env var > `.env` > default fallback.

#### Scenario: Connection takes precedence over env var

- GIVEN an Airflow Connection `postgres_default` exists
- AND `POSTGRES_PASSWORD` env var is also set
- WHEN the DAG resolves the credential
- THEN it uses the Airflow Connection value

#### Scenario: .env provides defaults locally

- GIVEN no Airflow Connection or env var is set
- AND a `.env` file exists with credentials
- WHEN the DAG resolves credentials
- THEN it uses values from `.env`

### Requirement: Task-Scoped Resolution

Credential resolution MUST execute inside task execution context, never at DAG module top-level.

#### Scenario: No global resolution on import

- GIVEN the DAG module is loaded by Airflow
- WHEN Python evaluates the module
- THEN no `Variable.get()`, `Connection.get_connection()`, or `os.environ.get()` executes at module level

### Requirement: PostgreSQL via Airflow Connections

PostgreSQL credentials MUST use Airflow Connections (encrypted), never Airflow Variables.

#### Scenario: Load uses PostgresHook

- GIVEN an Airflow Connection `postgres_default` with encrypted credentials
- WHEN `load_data_to_postgres` connects
- THEN it uses `PostgresHook(postgres_conn_id=DEFAULT_CONN_ID)`

### Requirement: No Plaintext Passwords in Config Files

`docker-compose.yml`, `servers.json`, and DAG code MUST NOT contain hardcoded passwords.

#### Scenario: docker-compose uses env references

- GIVEN `docker-compose.yml`
- WHEN inspected for plaintext passwords
- THEN all password values use `${VAR:-default}` syntax only

#### Scenario: servers.json has no plaintext password

- GIVEN `config/pgadmin/servers.json`
- WHEN inspected for the Password field
- THEN no plaintext password string exists
- AND credentials are provided via `.pgpass` file mounted into the container (pgAdmin does NOT expand env vars in servers.json)

### Requirement: pgAdmin Credential Isolation

pgAdmin's native `servers.json` does NOT expand environment variables in the Password field. Credentials MUST be provided via `.pgpass` file mount into the container.

#### Scenario: pgAdmin uses mounted .pgpass

- GIVEN the pgAdmin container configuration
- WHEN configuring database connections in servers.json
- THEN passwords SHALL NOT be hardcoded in servers.json
- AND a `.pgpass` file SHALL be mounted into the container for credential resolution

### Requirement: .env.example Documents All Vars

`.env.example` MUST list every required credential with descriptive placeholders.

#### Scenario: All vars documented

- GIVEN `.env.example`
- WHEN reading its entries
- THEN it includes `NEWS_API_KEY`, `POSTGRES_PASSWORD`, `PGADMIN_PASSWORD`, `USER_AGENT`
