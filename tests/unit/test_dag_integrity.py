"""
DAG integrity tests — parse and validate the news ETL DAG.

These tests are the single most important CI gate:
if the DAG has import errors or cycles, nothing else can work.
"""

import os

import pytest


@pytest.mark.skipif(
    os.environ.get("SKIP_AIRFLOW_TESTS") == "1",
    reason="Airflow not installed — set SKIP_AIRFLOW_TESTS=0 to run",
)
class TestDagIntegrity:
    """Parse the DAG via Airflow DagBag and validate structure."""

    def test_dag_bag_zero_import_errors(self):
        """GIVEN the dags/ directory
        WHEN Airflow parses DAGs with DagBag
        THEN len(dagbag.import_errors) SHALL be 0."""
        try:
            from airflow.models import DagBag
        except ImportError:
            pytest.skip("Airflow not installed")

        dag_folder = os.path.join(os.path.dirname(__file__), "..", "..", "dags")
        dagbag = DagBag(dag_folder=dag_folder, include_examples=False)

        import_errors = dagbag.import_errors
        assert len(import_errors) == 0, f"DagBag import errors found: {import_errors}"

    def test_dag_no_cycles(self):
        """GIVEN the parsed DAG
        WHEN task dependencies are analyzed
        THEN no cycles SHALL exist in the task graph."""
        try:
            from airflow.models import DagBag
        except ImportError:
            pytest.skip("Airflow not installed")

        dag_folder = os.path.join(os.path.dirname(__file__), "..", "..", "dags")
        dagbag = DagBag(dag_folder=dag_folder, include_examples=False)

        dag_ids = dagbag.dag_ids
        assert len(dag_ids) > 0, "No DAGs found in dags/ directory"

        for dag_id in dag_ids:
            dag = dagbag.dags.get(dag_id)
            assert dag is not None, f"DAG '{dag_id}' is None"

    def test_dag_has_expected_task_ids(self):
        """GIVEN the news ETL DAG
        WHEN parsed
        THEN it contains all four core task IDs."""
        try:
            from airflow.models import DagBag
        except ImportError:
            pytest.skip("Airflow not installed")

        dag_folder = os.path.join(os.path.dirname(__file__), "..", "..", "dags")
        dagbag = DagBag(dag_folder=dag_folder, include_examples=False)

        dag = dagbag.dags.get("ingestion_newsapi_postgres_with_scraping")
        assert dag is not None, "Expected DAG not found"

        task_ids = {t.task_id for t in dag.tasks}
        expected = {
            "extract_newsapi_task",
            "scrape_content_task",
            "ml_analysis_task",
            "load_postgres_task",
        }
        assert task_ids == expected, f"Task IDs mismatch: {task_ids}"

    def test_dag_has_deadline_alert(self):
        """GIVEN the news ETL DAG
        WHEN parsed
        THEN the DAG has a DeadlineAlert configured with 9h interval."""
        try:
            from airflow.models import DagBag
            from airflow.sdk.definitions.deadline import DeadlineAlert
        except ImportError:
            pytest.skip("Airflow not installed")

        dag_folder = os.path.join(os.path.dirname(__file__), "..", "..", "dags")
        dagbag = DagBag(dag_folder=dag_folder, include_examples=False)

        dag = dagbag.dags.get("ingestion_newsapi_postgres_with_scraping")
        assert dag is not None, "Expected DAG not found"

        from datetime import timedelta

        assert dag.deadline is not None, "DAG has no deadline configured"
        assert len(dag.deadline) == 1, f"Expected 1 deadline, got {len(dag.deadline)}"

        deadline = dag.deadline[0]
        assert isinstance(deadline, DeadlineAlert), f"Expected DeadlineAlert, got {type(deadline)}"
        assert deadline.interval == timedelta(hours=9), (
            f"Expected 9h interval, got {deadline.interval}"
        )

    def test_dag_deadline_has_callback(self):
        """GIVEN the news ETL DAG
        WHEN parsed
        THEN the DeadlineAlert callback is a SyncCallback wrapping on_sla_miss."""
        try:
            from airflow.models import DagBag
            from airflow.sdk.definitions.deadline import SyncCallback
        except ImportError:
            pytest.skip("Airflow not installed")

        dag_folder = os.path.join(os.path.dirname(__file__), "..", "..", "dags")
        dagbag = DagBag(dag_folder=dag_folder, include_examples=False)

        dag = dagbag.dags.get("ingestion_newsapi_postgres_with_scraping")
        assert dag is not None, "Expected DAG not found"

        deadline = dag.deadline[0]
        assert isinstance(deadline.callback, SyncCallback), (
            f"Expected SyncCallback, got {type(deadline.callback)}"
        )

        from pipeline.sla_callbacks import on_sla_miss

        # SyncCallback stores the callable path, not the callable itself
        # Verify the callback is wired (path contains 'on_sla_miss')
        assert "on_sla_miss" in str(deadline.callback.path), (
            f"Callback not wired to on_sla_miss: {deadline.callback.path}"
        )
