"""
Shared test fixtures for the news ETL pipeline test suite.

Provides:
- Airflow environment setup for DagBag tests
- Mock NewsAPI responses
- Sample article data
- PostgreSQL connection for integration tests
- Table truncation teardown (app tables only, NEVER Airflow internal tables)
"""

import os
import sys
from unittest.mock import MagicMock

import pytest

# ---------------------------------------------------------------------------
# Path setup — ensure dags/ is importable
# ---------------------------------------------------------------------------
_dags_path = os.path.join(os.path.dirname(__file__), "..", "dags")
sys.path.insert(0, _dags_path)

# Set up minimal Airflow environment for DagBag
_airflow_home = os.path.join(os.path.dirname(__file__), "..", "airflow_home_test")
os.makedirs(_airflow_home, exist_ok=True)
os.environ.setdefault("AIRFLOW_HOME", _airflow_home)

# Prevent Airflow from trying to load config at import time on module-level
# imports by ensuring a basic airflow.cfg exists
_airflow_cfg = os.path.join(_airflow_home, "airflow.cfg")
if not os.path.exists(_airflow_cfg):
    with open(_airflow_cfg, "w") as f:
        f.write(f"[core]\ndags_folder = {_dags_path}\n")


# ---------------------------------------------------------------------------
# Sample data fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_article():
    """Single article dict matching NewsAPI response format."""
    return {
        "title": "Test Article",
        "description": "A test description.",
        "url": "https://example.com/article1",
        "urlToImage": "https://example.com/img1.jpg",
        "publishedAt": "2024-01-15T10:00:00Z",
        "source": {"name": "Example News"},
        "author": "John Doe",
        "content": "Short original content.",
        "sentiment_polarity": None,
        "sentiment_subjectivity": None,
        "named_entities": None,
    }


@pytest.fixture
def sample_articles():
    """Multiple article dicts matching NewsAPI response format."""
    return [
        {
            "title": "Test Article 1",
            "description": "Description 1",
            "url": "https://example.com/article1",
            "urlToImage": "https://example.com/img1.jpg",
            "publishedAt": "2024-01-15T10:00:00Z",
            "source": {"name": "Example News"},
            "author": "John Doe",
            "content": "Original content for article one.",
        },
        {
            "title": "Test Article 2",
            "description": "Description 2",
            "url": "https://example.org/article2",
            "urlToImage": "https://example.org/img2.jpg",
            "publishedAt": "2024-01-15T11:00:00Z",
            "source": {"name": "Other Source"},
            "author": "Jane Smith",
            "content": "Original content for article two.",
        },
        {
            "title": "Test Article 3",
            "description": "Description 3",
            "url": "https://example.com/article3",
            "urlToImage": None,
            "publishedAt": "2024-01-15T12:00:00Z",
            "source": {"name": "Example News"},
            "author": None,
            "content": None,
        },
    ]


@pytest.fixture
def newsapi_response():
    """Valid NewsAPI top-headlines JSON response."""
    return {
        "status": "ok",
        "totalResults": 3,
        "articles": [
            {
                "title": "Test Article 1",
                "description": "Description 1",
                "url": "https://example.com/article1",
                "urlToImage": "https://example.com/img1.jpg",
                "publishedAt": "2024-01-15T10:00:00Z",
                "source": {"name": "Example News"},
                "author": "John Doe",
                "content": "Original content.",
            },
            {
                "title": "Test Article 2",
                "description": "Description 2",
                "url": "https://example.org/article2",
                "urlToImage": "https://example.org/img2.jpg",
                "publishedAt": "2024-01-15T11:00:00Z",
                "source": {"name": "Other Source"},
                "author": "Jane Smith",
                "content": "Original content.",
            },
            {
                "title": "Test Article 3",
                "description": "Description 3",
                "url": "https://example.com/article3",
                "urlToImage": None,
                "publishedAt": "2024-01-15T12:00:00Z",
                "source": {"name": "Example News"},
                "author": None,
                "content": None,
            },
        ],
    }


# ---------------------------------------------------------------------------
# Mock context for task functions that use `**context`
# ---------------------------------------------------------------------------


@pytest.fixture
def task_context():
    """Mock Airflow task context with xcom_pull support."""
    ti = MagicMock()
    context = {"ti": ti}
    return context


# ---------------------------------------------------------------------------
# Integration test fixtures (PostgreSQL)
# ---------------------------------------------------------------------------

_pg_conn = None


def _get_pg_connection():
    """Get or create a PostgreSQL connection for integration tests."""
    global _pg_conn
    if _pg_conn is None or _pg_conn.closed:
        import psycopg2

        _pg_conn = psycopg2.connect(
            host=os.environ.get("POSTGRES_HOST", "localhost"),
            port=os.environ.get("POSTGRES_PORT", "5432"),
            dbname=os.environ.get("POSTGRES_DB", "airflow_db"),
            user=os.environ.get("POSTGRES_USER", "airflow"),
            password=os.environ.get("POSTGRES_PASSWORD", "airflow"),
        )
    return _pg_conn


@pytest.fixture(scope="module")
def db_connection():
    """Provide a live PostgreSQL connection shared across integration tests."""
    conn = _get_pg_connection()
    # Ensure the news_articles table exists
    with conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS news_articles (
                id SERIAL PRIMARY KEY,
                title VARCHAR(500) NOT NULL,
                description TEXT,
                url VARCHAR(500) UNIQUE NOT NULL,
                image_url VARCHAR(500),
                published_at TIMESTAMP NOT NULL,
                source_name VARCHAR(255) NOT NULL,
                author VARCHAR(255),
                content TEXT,
                ingested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                sentiment_polarity FLOAT,
                sentiment_subjectivity FLOAT,
                named_entities JSONB
            );
        """)
        conn.commit()
    yield conn


@pytest.fixture
def _truncate_app_tables(db_connection):
    """TRUNCATE app tables after each test. NEVER touches Airflow internal tables.

    This fixture is NOT autouse — only integration tests that require
    PostgreSQL isolation should explicitly request it. Unit tests that mock
    the database are unaffected.
    """
    yield
    with db_connection.cursor() as cur:
        # Only application tables — NEVER Airflow internals
        cur.execute("TRUNCATE TABLE news_articles RESTART IDENTITY CASCADE;")
        db_connection.commit()
