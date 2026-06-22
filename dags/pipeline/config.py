"""
Shared configuration constants for the news ETL pipeline.
"""

import logging

# DAG configuration
DAG_ID = "ingestion_newsapi_postgres_with_scraping"
NEWS_API_ENDPOINT = "https://newsapi.org/v2/top-headlines"
DEFAULT_CONN_ID = "postgres_default"

logger = logging.getLogger(__name__)
