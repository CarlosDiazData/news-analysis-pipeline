"""
NewsAPI extraction module — fetches top headlines from NewsAPI.
"""

import logging

import requests
from airflow.exceptions import AirflowException

from pipeline.config import NEWS_API_ENDPOINT
from pipeline.credentials import resolve_newsapi_key

logger = logging.getLogger(__name__)


def extract_data_from_newsapi():
    """Extracts news data from NewsAPI.

    Returns:
        list: List of articles retrieved from the API.

    Raises:
        AirflowException: If API request fails or returns invalid data.
    """
    # Resolve the API key INSIDE the task callable — NEVER at module top-level
    try:
        news_api_key = resolve_newsapi_key()
    except RuntimeError as exc:
        raise AirflowException(str(exc)) from exc

    # Define API parameters (country: US, max 100 articles)
    params = {
        "apiKey": news_api_key,
        "country": "us",
        "pageSize": 100,
    }

    try:
        # Make API request with timeout
        logger.info("Requesting data from NewsAPI")
        response = requests.get(
            NEWS_API_ENDPOINT,
            params=params,
            timeout=30,
        )
        response.raise_for_status()

        data = response.json()

        # Check API status field in the response
        if data.get("status") != "ok":
            raise AirflowException(f"API Error: {data.get('message', 'Unknown error')}")

        articles = data.get("articles", [])
        logger.info("Successfully extracted %d articles", len(articles))
        return articles

    except requests.exceptions.RequestException as exc:
        logger.error("NewsAPI request failed: %s", exc)
        raise AirflowException(f"Connection error: {exc}") from exc
