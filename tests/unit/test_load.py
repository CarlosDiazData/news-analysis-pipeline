"""
Unit tests for PostgreSQL data loading (load_data_to_postgres).

Uses unittest.mock for PostgresHook/psycopg2 — zero database required.
Tests cover: successful insert, empty input, DB errors, rollback behavior.
"""

from unittest.mock import MagicMock, patch

import pytest
from airflow.exceptions import AirflowException


@pytest.fixture
def load_ready_articles():
    """Articles that have been through scraping and analysis — ready to load."""
    return [
        {
            "title": "Market Rally Continues",
            "description": "Stocks surge again.",
            "url": "https://example.com/markets-2",
            "urlToImage": "https://example.com/img.jpg",
            "publishedAt": "2024-06-15T15:00:00Z",
            "source": {"name": "Financial Daily"},
            "author": "Jane Reporter",
            "content": "Full article content here.",
            "sentiment_polarity": 0.35,
            "sentiment_subjectivity": 0.55,
            "named_entities": [
                {"text": "Dow Jones", "label": "ORG"},
                {"text": "Jerome Powell", "label": "PERSON"},
            ],
        },
        {
            "title": "Tech Innovation Summit",
            "description": "Annual tech event wraps up.",
            "url": "https://example.org/tech-summit",
            "urlToImage": None,
            "publishedAt": "2024-06-15T14:00:00Z",
            "source": {"name": "Tech Source"},
            "author": None,
            "content": "Innovation content.",
            "sentiment_polarity": 0.12,
            "sentiment_subjectivity": 0.33,
            "named_entities": None,
        },
    ]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestLoadDataToPostgres:
    """Unit tests for load_data_to_postgres."""

    def test_empty_articles_returns_zero(self):
        """GIVEN no articles from upstream
        WHEN load_data_to_postgres runs THEN it returns 0."""
        mock_context = {"ti": MagicMock()}
        mock_context["ti"].xcom_pull.return_value = []

        from pipeline.load import load_data_to_postgres

        result = load_data_to_postgres(**mock_context)
        assert result == 0

    def test_insert_success(self, load_ready_articles):
        """GIVEN valid analyzed articles
        WHEN load_data_to_postgres runs
        THEN executemany is called, commit is called, and returns record count."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.rowcount = len(load_ready_articles)
        mock_conn.cursor.return_value = mock_cursor

        mock_context = {"ti": MagicMock()}
        mock_context["ti"].xcom_pull.return_value = load_ready_articles

        from pipeline.load import load_data_to_postgres

        with patch("pipeline.load.get_db_connection", return_value=mock_conn):
            result = load_data_to_postgres(**mock_context)

        # Verify return value equals number of records loaded
        assert result == len(load_ready_articles)

        # Verify the SQL was executed
        mock_cursor.executemany.assert_called_once()
        mock_conn.commit.assert_called_once()

        # Verify the call arguments contain expected field values
        call_args = mock_cursor.executemany.call_args
        sql, records = call_args[0]
        assert len(records) == 2
        assert records[0][0] == "Market Rally Continues"  # title

    def test_db_error_triggers_rollback_and_raises(self, load_ready_articles):
        """GIVEN the database connection but executemany fails
        WHEN load_data_to_postgres runs
        THEN conn.rollback() is called and AirflowException is raised."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.executemany.side_effect = Exception("Simulated DB error")
        mock_conn.cursor.return_value = mock_cursor

        mock_context = {"ti": MagicMock()}
        mock_context["ti"].xcom_pull.return_value = load_ready_articles

        from pipeline.load import load_data_to_postgres

        with (
            patch("pipeline.load.get_db_connection", return_value=mock_conn),
            pytest.raises(AirflowException, match="Database error"),
        ):
            load_data_to_postgres(**mock_context)

        mock_conn.rollback.assert_called_once()
        mock_cursor.close.assert_called_once()
        mock_conn.close.assert_called_once()

    def test_articles_with_none_entities_handled(self, load_ready_articles):
        """GIVEN an article where named_entities is None
        WHEN the record tuple is constructed
        THEN it serializes as None (not 'null' string)."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        mock_context = {"ti": MagicMock()}
        mock_context["ti"].xcom_pull.return_value = load_ready_articles

        from pipeline.load import load_data_to_postgres

        with patch("pipeline.load.get_db_connection", return_value=mock_conn):
            load_data_to_postgres(**mock_context)

        call_args = mock_cursor.executemany.call_args
        _sql, records = call_args[0]
        # Second article has named_entities=None → should be Python None
        assert records[1][10] is None

    def test_articles_with_entities_serialized_to_json(self, load_ready_articles):
        """GIVEN an article with a named_entities list
        WHEN the record tuple is constructed
        THEN it is serialized as a JSON string."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        mock_context = {"ti": MagicMock()}
        mock_context["ti"].xcom_pull.return_value = load_ready_articles

        from pipeline.load import load_data_to_postgres

        with patch("pipeline.load.get_db_connection", return_value=mock_conn):
            load_data_to_postgres(**mock_context)

        call_args = mock_cursor.executemany.call_args
        _sql, records = call_args[0]
        # First article has named_entities → should be JSON string
        import json

        entities = json.loads(records[0][10])
        assert isinstance(entities, list)
        assert entities[0]["text"] == "Dow Jones"
