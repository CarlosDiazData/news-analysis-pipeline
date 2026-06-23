"""
PostgreSQL data loading module — inserts enriched articles with upsert handling.
"""

import json
import logging

from airflow.exceptions import AirflowException

from pipeline.credentials import get_db_connection

logger = logging.getLogger(__name__)

SQL_INSERT = """
    INSERT INTO news_articles
    (title, description, url, image_url, published_at, source_name, author, content,
     sentiment_polarity, sentiment_subjectivity, named_entities)
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    ON CONFLICT (url) DO UPDATE SET
        title = EXCLUDED.title,
        description = EXCLUDED.description,
        content = EXCLUDED.content,
        sentiment_polarity = EXCLUDED.sentiment_polarity,
        sentiment_subjectivity = EXCLUDED.sentiment_subjectivity,
        named_entities = EXCLUDED.named_entities;
    """


def load_data_to_postgres(**context) -> int:
    """Loads data into PostgreSQL with transaction management and duplicate handling.

    Uses stratified credential resolution inside the task callable:
    first Airflow Connection, then env vars.

    Args:
        context (dict): Airflow context for accessing XCom data.

    Returns:
        int: Number of records inserted/updated.

    Raises:
        AirflowException: If no data to load or database error occurs.
    """
    articles = context["ti"].xcom_pull(task_ids="ml_analysis_task")

    if not articles or len(articles) == 0:
        logger.warning("No news data to load into PostgreSQL")
        return 0

    logger.info("Processing %d articles for database insertion", len(articles))

    # Resolve DB connection INSIDE the task callable — NEVER at module top-level
    conn = get_db_connection()
    cursor = conn.cursor()

    # Prepare records from the news data
    records = [
        (
            n.get("title"),
            n.get("description"),
            n.get("url"),
            n.get("urlToImage"),
            n.get("publishedAt"),
            n.get("source", {}).get("name"),
            n.get("author"),
            n.get("content"),
            n.get("sentiment_polarity"),
            n.get("sentiment_subjectivity"),
            json.dumps(n.get("named_entities")) if n.get("named_entities") is not None else None,
        )
        for n in articles
    ]

    try:
        cursor.executemany(SQL_INSERT, records)
        conn.commit()
        logger.info("Successfully inserted or updated %s records.", len(records))
        return len(records)
    except Exception as exc:
        conn.rollback()
        logger.error("Database operation failed: %s", exc)
        raise AirflowException(f"Database error: {exc}") from exc
    finally:
        cursor.close()
        conn.close()
