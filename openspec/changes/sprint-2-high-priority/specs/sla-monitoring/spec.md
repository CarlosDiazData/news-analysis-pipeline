# SLA Monitoring Specification

## Purpose

Enforce an SLA on `load_postgres_task` and emit structured SLA-miss alerts as JSON lines.

## Requirements

### Requirement: Load Task SLA Deadline

The `load_postgres_task` MUST carry `sla=timedelta(hours=9)` so data is ready before the 9 AM consumption window (DAG runs at midnight).

#### Scenario: Task completes within SLA

- GIVEN a DAG run starting at 00:00
- WHEN `load_postgres_task` finishes before 09:00
- THEN no SLA miss is logged

#### Scenario: Task exceeds SLA

- GIVEN a DAG run starting at 00:00
- WHEN `load_postgres_task` takes longer than 9 hours
- THEN the `sla_miss_callback` fires
- AND a JSON line is appended to the SLA log

### Requirement: Structured SLA Miss Log

The DAG MUST wire a `sla_miss_callback` that appends one JSON line per miss to `/opt/airflow/logs/sla_misses.log` (mounted volume `./logs`).

#### Scenario: JSON line schema

- GIVEN an SLA miss on `load_postgres_task`
- WHEN the callback executes
- THEN it appends `{"timestamp": "<iso-utc>", "dag_id": "news_etl_dag", "task_id": "load_postgres_task", "scheduled_time": "<iso-utc>", "sla_exceeded_by": <seconds_int>}`
- AND `sla_exceeded_by` SHALL be an integer representing total seconds exceeded (e.g., `1835` for 30min 35s over SLA)
- AND `sla_exceeded_by` SHALL be computed as `int((datetime.now(timezone.utc) - (execution_date + task.sla)).total_seconds())`
- AND all timestamps SHALL be timezone-aware UTC (`datetime.now(timezone.utc)`)

#### Scenario: Callback signature matches Airflow 2.x

- GIVEN the `sla_miss_callback` function
- WHEN Airflow invokes it
- THEN the function signature SHALL be `def on_sla_miss(dag, task_list, blocking_task_list, slas, blocking_tis):`
- AND it SHALL iterate `slas` (a `list[SLAMiss]`) and emit one JSON line per miss

#### Scenario: Multiple misses in single invocation

- GIVEN the callback receives `slas` with 2 SLAMiss objects
- WHEN the callback executes
- THEN it appends exactly 2 JSON lines to the log file
- AND each line has the correct `task_id` and `scheduled_time` for its miss

### Requirement: Log-Only Alerting

The system MUST NOT send SMTP or email alerts on SLA misses (log-only by decision).

#### Scenario: No SMTP attempted

- GIVEN an SLA miss
- WHEN the callback writes the log line
- THEN no SMTP connection is attempted
- AND no Airflow email config is required
