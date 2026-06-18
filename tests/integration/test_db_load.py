"""
Integration test: PostgreSQL insert/read round-trip.

Uses a live PostgreSQL service container (via conftest fixture).
NEVER touches Airflow internal tables — only news_articles.
"""

import json
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def integration_articles():
    """Articles ready for integration test insertion."""
    return [
        {
            "title": "Integration Test Article",
            "description": "Description for integration test.",
            "url": "https://unique-integration.example.com/article1",
            "urlToImage": "https://unique-integration.example.com/img.jpg",
            "publishedAt": "2024-06-15T10:00:00Z",
            "source": {"name": "Integration Times"},
            "author": "Integration Author",
            "content": "Full integration test article content.",
            "sentiment_polarity": 0.25,
            "sentiment_subjectivity": 0.40,
            "named_entities": [
                {"text": "Integration Corp", "label": "ORG"},
                {"text": "Test User", "label": "PERSON"},
            ],
        },
    ]


@pytest.mark.usefixtures("_truncate_app_tables")
class TestDbLoadRoundTrip:
    """Insert articles via load_data_to_postgres, then verify with SELECT."""

    def test_insert_and_read_back(self, db_connection, integration_articles):
        """GIVEN a running PostgreSQL with the news_articles table
        WHEN load_data_to_postgres inserts valid articles
        THEN the records appear with correct column values on SELECT."""
        mock_context = {"ti": MagicMock()}
        mock_context["ti"].xcom_pull.return_value = integration_articles

        # Patch get_db_connection to return our fixture connection
        with patch("news_etl_dag.get_db_connection", return_value=db_connection):
            from news_etl_dag import load_data_to_postgres

            load_data_to_postgres(**mock_context)

        # Read back the inserted data
        with db_connection.cursor() as cur:
            cur.execute(
                "SELECT title, description, url, author, content, "
                "sentiment_polarity, sentiment_subjectivity, named_entities "
                "FROM news_articles "
                "WHERE url = %s",
                ("https://unique-integration.example.com/article1",),
            )
            row = cur.fetchone()

        assert row is not None, "Inserted article not found in database"
        assert row[0] == "Integration Test Article"
        assert row[1] == "Description for integration test."
        assert row[2] == "https://unique-integration.example.com/article1"
        assert row[3] == "Integration Author"
        assert row[4] == "Full integration test article content."
        assert row[5] == pytest.approx(0.25)
        assert row[6] == pytest.approx(0.40)

        named_entities = row[7]
        if isinstance(named_entities, str):
            named_entities = json.loads(named_entities)
        assert isinstance(named_entities, list)
        assert len(named_entities) == 2
        assert named_entities[0]["text"] == "Integration Corp"

    def test_upsert_behavior(self, db_connection, integration_articles):
        """GIVEN an existing article with the same URL
        WHEN load_data_to_postgres inserts again
        THEN the row is updated (ON CONFLICT DO UPDATE), not duplicated.

        Note: Test case verifies upsert contract."""
        mock_context = {"ti": MagicMock()}
        mock_context["ti"].xcom_pull.return_value = integration_articles

        # First insert
        with patch("news_etl_dag.get_db_connection", return_value=db_connection):
            from news_etl_dag import load_data_to_postgres

            load_data_to_postgres(**mock_context)

        # Modify the article and re-insert (simulates update)
        updated = integration_articles.copy()
        updated[0]["content"] = "Updated content after re-scrape."
        updated[0]["sentiment_polarity"] = 0.99
        mock_context["ti"].xcom_pull.return_value = updated

        with patch("news_etl_dag.get_db_connection", return_value=db_connection):
            load_data_to_postgres(**mock_context)

        # Verify only ONE row exists (not duplicated)
        with db_connection.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) FROM news_articles WHERE url = %s",
                ("https://unique-integration.example.com/article1",),
            )
            count = cur.fetchone()[0]

        assert count == 1, f"Expected 1 row, found {count} (duplicate detected)"

        # Verify the row was updated
        with db_connection.cursor() as cur:
            cur.execute(
                "SELECT content, sentiment_polarity FROM news_articles WHERE url = %s",
                ("https://unique-integration.example.com/article1",),
            )
            row = cur.fetchone()

        assert row[0] == "Updated content after re-scrape."
        assert row[1] == pytest.approx(0.99)

    def test_empty_insert_returns_zero(self, db_connection):
        """GIVEN no articles
        WHEN load_data_to_postgres runs
        THEN it returns 0 and no rows are inserted."""
        mock_context = {"ti": MagicMock()}
        mock_context["ti"].xcom_pull.return_value = []

        with patch("news_etl_dag.get_db_connection", return_value=db_connection):
            from news_etl_dag import load_data_to_postgres

            result = load_data_to_postgres(**mock_context)

        assert result == 0
