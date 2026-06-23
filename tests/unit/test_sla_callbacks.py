"""
Unit tests for Deadline alert callback (dags/pipeline/sla_callbacks.py).

Mocks Airflow context — zero Airflow runtime required.
"""

import json
from datetime import datetime, timedelta, timezone

import pytest


SLA_MISS_LOG = "/opt/airflow/logs/sla_misses.log"


class TestSlaCallback:
    """Deadline alert callback tests — JSON schema, append behavior, computation."""

    def _make_context(self, dag_id="news_etl_dag", task_id="load_postgres_task", hours_ago=10):
        """Create a mock Airflow context with logical_date hours_ago."""
        logical_date = datetime.now(timezone.utc) - timedelta(hours=hours_ago)
        return {
            "dag": dag_id,
            "task": task_id,
            "logical_date": logical_date,
        }

    def test_writes_valid_json_line(self, tmp_path):
        """GIVEN a valid Airflow context
        WHEN the callback executes
        THEN it appends a valid JSON line with all 5 required fields."""
        log_path = tmp_path / "sla_misses.log"
        context = self._make_context()

        from pipeline.sla_callbacks import on_sla_miss

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr("pipeline.sla_callbacks.SLA_MISS_LOG", str(log_path))
            on_sla_miss(**context)

        assert log_path.exists()
        lines = log_path.read_text().strip().split("\n")
        assert len(lines) == 1

        record = json.loads(lines[0])
        assert set(record.keys()) == {
            "timestamp", "dag_id", "task_id", "scheduled_time", "sla_exceeded_by",
        }
        assert record["dag_id"] == "news_etl_dag"
        assert record["task_id"] == "load_postgres_task"
        assert isinstance(record["sla_exceeded_by"], int)
        assert record["sla_exceeded_by"] > 0  # 10h run > 9h deadline

    def test_appends_without_overwrite(self, tmp_path):
        """GIVEN a log file with 2 prior lines
        WHEN a third deadline miss triggers the callback
        THEN the file contains exactly 3 lines and prior lines are preserved."""
        log_path = tmp_path / "sla_misses.log"
        prior_line = json.dumps({"line": 1}) + "\n"
        log_path.write_text(prior_line + prior_line)

        context = self._make_context()
        from pipeline.sla_callbacks import on_sla_miss

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr("pipeline.sla_callbacks.SLA_MISS_LOG", str(log_path))
            on_sla_miss(**context)

        lines = log_path.read_text().strip().split("\n")
        assert len(lines) == 3
        assert json.loads(lines[0]) == {"line": 1}
        assert json.loads(lines[1]) == {"line": 1}
        record = json.loads(lines[2])
        assert record["dag_id"] == "news_etl_dag"

    def test_sla_exceeded_by_computation(self, tmp_path):
        """GIVEN a deadline of 9h and logical_date 10h ago
        WHEN the callback runs
        THEN sla_exceeded_by is ~3600s (10h - 9h = 1h)."""
        log_path = tmp_path / "sla_misses.log"
        context = self._make_context(hours_ago=10)

        from pipeline.sla_callbacks import on_sla_miss

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr("pipeline.sla_callbacks.SLA_MISS_LOG", str(log_path))
            on_sla_miss(**context)

        record = json.loads(log_path.read_text().strip())
        # 10h ago - 9h deadline ≈ 3600s (± a few seconds for test execution)
        assert 3500 <= record["sla_exceeded_by"] <= 3700

    def test_callback_signature(self):
        """GIVEN the on_sla_miss function
        WHEN inspected
        THEN it accepts **kwargs (Airflow context)."""
        from pipeline.sla_callbacks import on_sla_miss

        import inspect
        sig = inspect.signature(on_sla_miss)
        # Should accept **context (VAR_KEYWORD)
        params = list(sig.parameters.values())
        assert len(params) == 1
        assert params[0].kind == inspect.Parameter.VAR_KEYWORD

    def test_missing_context_keys_use_defaults(self, tmp_path):
        """GIVEN a context with missing keys
        WHEN the callback executes
        THEN it uses safe defaults and still writes a record."""
        log_path = tmp_path / "sla_misses.log"
        context = {"logical_date": datetime.now(timezone.utc) - timedelta(hours=10)}

        from pipeline.sla_callbacks import on_sla_miss

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr("pipeline.sla_callbacks.SLA_MISS_LOG", str(log_path))
            on_sla_miss(**context)

        record = json.loads(log_path.read_text().strip())
        assert record["dag_id"] == "unknown"
        assert record["task_id"] == "unknown"
