"""
NewsAPI extraction module — fetches top headlines from NewsAPI with tenacity retry.
"""

import logging

import requests
from airflow.exceptions import AirflowException
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

from pipeline.config import NEWS_API_ENDPOINT
from pipeline.credentials import resolve_newsapi_key

logger = logging.getLogger(__name__)


def _is_retryable(exception: BaseException) -> bool:
    """Determine if an exception should trigger a retry.

    Retries all exceptions except HTTP 404 (permanent — page not found).
    This includes HTTP 429/5xx, ConnectionError, Timeout, and RuntimeError
    raised by the body-status check (e.g., rateLimited).
    """
    if isinstance(exception, requests.exceptions.HTTPError):
        if exception.response is not None:
            if exception.response.status_code == 404:
                return False
    return True


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=4),
    retry=retry_if_exception(_is_retryable),
    reraise=True,
)
def _fetch_newsapi(endpoint: str, params: dict) -> list[dict]:
    """Fetch articles from NewsAPI with retry on transient errors.

    Args:
        endpoint: NewsAPI endpoint URL.
        params: Query parameters including apiKey.

    Returns:
        List of article dicts.

    Raises:
        requests.exceptions.RequestException: On HTTP errors after retries.
        RuntimeError: On API error body (e.g., rateLimited) after retries.
    """
    response = requests.get(endpoint, params=params, timeout=30)
    response.raise_for_status()  # → HTTPError for non-2xx (caught by _is_retryable)
    data = response.json()
    if data.get("status") != "ok":
        # NewsAPI can return 200 with error body on rate limits
        raise RuntimeError(f"API Error: {data.get('message', 'Unknown error')}")
    return data.get("articles", [])


def extract_data_from_newsapi():
    """Extracts news data from NewsAPI with exponential-backoff retry.

    Credential resolution happens ONCE (outside the retry loop). The inner
    ``_fetch_newsapi`` function is decorated with tenacity retry so transient
    HTTP errors (429, 5xx, ConnectionError, Timeout) and rate-limit-in-body
    responses are retried up to 3 times with exponential backoff.

    Returns:
        list: List of articles retrieved from the API.

    Raises:
        AirflowException: If API key is missing, all retries fail, or the
            API returns a non-retryable error (404).
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
        logger.info("Requesting data from NewsAPI")
        articles = _fetch_newsapi(NEWS_API_ENDPOINT, params)
        logger.info("Successfully extracted %d articles", len(articles))
        return articles
    except requests.exceptions.RequestException as exc:
        logger.error("NewsAPI request failed: %s", exc)
        raise AirflowException(f"Connection error: {exc}") from exc
    except RuntimeError as exc:
        raise AirflowException(str(exc)) from exc
