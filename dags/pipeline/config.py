"""
Shared configuration constants for the news ETL pipeline.
"""

import logging

# DAG configuration
DAG_ID = "ingestion_newsapi_postgres_with_scraping"
NEWS_API_ENDPOINT = "https://newsapi.org/v2/top-headlines"
DEFAULT_CONN_ID = "postgres_default"

# NewsAPI query parameters (configurable via stratified resolution)
NEWS_API_COUNTRY = "us"
NEWS_API_TOPIC = None  # None = no category filter (NewsAPI `category` param)

logger = logging.getLogger(__name__)
