"""
Unit tests for SLA miss callback (dags/pipeline/sla_callbacks.py).

Mocks Airflow SLAMiss and DAG internals — zero Airflow runtime required.
"""

import json
import os
from collections import namedtuple
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest

# Mimic Airflow's SLAMiss model (dag_id, task_id, execution_date)
SLAMiss = namedtuple("SLAMiss", ["dag_id", "task_id", "execution_date"])

SLA_MISS_LOG = "/opt/airflow/logs/sla_misses.log"


class TestSlaCallback:
    """SLA miss callback tests — JSON schema, append behavior, computation."""

    def _make_miss(self, task_id="load_postgres_task", hours_ago=10):
        """Create a mock SLAMiss with execution_date hours_ago."""
        exec_date = datetime.now(timezone.utc) - timedelta(hours=hours_ago)
        return SLAMiss(dag_id="news_etl_dag", task_id=task_id, execution_date=exec_date)

    def _make_dag(self, sla_timedelta=timedelta(hours=9)):
        """Create a mock DAG that returns a mock task with given SLA."""
        dag = MagicMock()
        mock_task = MagicMock()
        mock_task.sla = sla_timedelta
        dag.get_task.return_value = mock_task
        return dag

    def test_writes_valid_json_line(self, tmp_path):
        """GIVEN one SLAMiss
        WHEN the callback executes
        THEN it appends a valid JSON line with all 5 required fields."""
        log_path = tmp_path / "sla_misses.log"
        miss = self._make_miss()

        # Import inside test to avoid Airflow side effects at module level
        from pipeline.sla_callbacks import on_sla_miss

        dag = self._make_dag()

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr("pipeline.sla_callbacks.SLA_MISS_LOG", str(log_path))
            on_sla_miss(dag, [], [], [miss], [])

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
        assert record["sla_exceeded_by"] > 0  # 10h run > 9h SLA

    def test_appends_without_overwrite(self, tmp_path):
        """GIVEN a log file with 2 prior lines
        WHEN a third SLA miss triggers the callback
        THEN the file contains exactly 3 lines and prior lines are preserved."""
        log_path = tmp_path / "sla_misses.log"
        # Pre-populate with 2 lines (each with trailing newline)
        prior_line = json.dumps({"line": 1}) + "\n"
        log_path.write_text(prior_line + prior_line)

        miss = self._make_miss()
        from pipeline.sla_callbacks import on_sla_miss

        dag = self._make_dag()
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr("pipeline.sla_callbacks.SLA_MISS_LOG", str(log_path))
            on_sla_miss(dag, [], [], [miss], [])

        lines = log_path.read_text().strip().split("\n")
        assert len(lines) == 3
        # First 2 lines are the prior lines
        assert json.loads(lines[0]) == {"line": 1}
        assert json.loads(lines[1]) == {"line": 1}
        # Third line is the new miss
        record = json.loads(lines[2])
        assert record["dag_id"] == "news_etl_dag"

    def test_sla_exceeded_by_computation(self, tmp_path):
        """GIVEN a task.sla of 9h and execution_date 10h ago
        WHEN the callback runs
        THEN sla_exceeded_by is ~3600s (10h - 9h = 1h)."""
        log_path = tmp_path / "sla_misses.log"
        miss = self._make_miss(hours_ago=10)  # 10 hours ago

        from pipeline.sla_callbacks import on_sla_miss

        dag = self._make_dag(sla_timedelta=timedelta(hours=9))
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr("pipeline.sla_callbacks.SLA_MISS_LOG", str(log_path))
            on_sla_miss(dag, [], [], [miss], [])

        record = json.loads(log_path.read_text().strip())
        # 10h ago - 9h SLA ≈ 3600s (± a few seconds for test execution)
        assert 3500 <= record["sla_exceeded_by"] <= 3700

    def test_multiple_misses_in_one_invocation(self, tmp_path):
        """GIVEN the callback receives 2 SLAMiss objects
        WHEN it executes
        THEN it appends exactly 2 JSON lines with correct task_ids."""
        log_path = tmp_path / "sla_misses.log"
        miss1 = self._make_miss(task_id="load_postgres_task", hours_ago=11)
        miss2 = self._make_miss(task_id="scrape_content_task", hours_ago=12)

        from pipeline.sla_callbacks import on_sla_miss

        dag = self._make_dag()
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr("pipeline.sla_callbacks.SLA_MISS_LOG", str(log_path))
            on_sla_miss(dag, [], [], [miss1, miss2], [])

        lines = log_path.read_text().strip().split("\n")
        assert len(lines) == 2

        rec1 = json.loads(lines[0])
        rec2 = json.loads(lines[1])
        assert rec1["task_id"] == "load_postgres_task"
        assert rec2["task_id"] == "scrape_content_task"
        # Both exceeded; scrape ran longer ago → larger exceedance
        assert rec2["sla_exceeded_by"] > rec1["sla_exceeded_by"]

    def test_callback_signature(self):
        """GIVEN the sla_miss_callback function
        WHEN inspected
        THEN it has the correct 5-parameter Airflow 2.x signature."""
        from pipeline.sla_callbacks import on_sla_miss

        import inspect
        sig = inspect.signature(on_sla_miss)
        param_names = list(sig.parameters.keys())
        assert param_names == [
            "dag", "task_list", "blocking_task_list", "slas", "blocking_tis",
        ]
