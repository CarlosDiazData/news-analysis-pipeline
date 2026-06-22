"""
Concurrent web scraping with retry, robots.txt compliance, and configurable workers.
"""

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import requests
from bs4 import BeautifulSoup
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

from pipeline.credentials import resolve_max_scrape_workers, resolve_user_agent

logger = logging.getLogger(__name__)


def _is_retryable(exception: BaseException) -> bool:
    """Determine if a request exception should be retried.

    Retry on connection errors, 429 (rate limit), and 5xx (server errors).
    Skip 404 permanently — retrying won't fix a missing page.
    """
    if isinstance(exception, requests.exceptions.HTTPError):
        if exception.response is not None:
            status = exception.response.status_code
            if status == 404:  # Not Found — permanent
                return False
            if status == 429:  # Too Many Requests — transient
                return True
            if 500 <= status < 600:  # Server errors — transient
                return True
        return False
    # ConnectionError, Timeout, etc. — retry
    return True


def _scrape_single_article(article: dict, user_agent: str, robots_cache: dict) -> dict:
    """Scrape full content for a single article. Worker for ThreadPoolExecutor."""
    url = article.get("url")
    if not url:
        return article

    # --- robots.txt check ---
    try:
        domain = urlparse(url).netloc
        rp = robots_cache.get(domain)
        if rp is not None and not rp.can_fetch(
            user_agent.split("/")[0] if "/" in user_agent else user_agent, url
        ):
            logger.warning("Robots.txt disallows fetching %s", url)
            return article
    except Exception:
        # If robots check fails for any reason, proceed cautiously
        pass

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=4),
        retry=retry_if_exception(_is_retryable),
        reraise=True,
    )
    def _fetch_with_retry(fetch_url: str, headers: dict) -> requests.Response:
        resp = requests.get(fetch_url, headers=headers, timeout=15)
        resp.raise_for_status()
        return resp

    try:
        headers = {"User-Agent": user_agent}
        response = _fetch_with_retry(url, headers)

        soup = BeautifulSoup(response.content, "html.parser")
        paragraphs = soup.find_all("p")
        full_content = " ".join([p.get_text() for p in paragraphs])

        if full_content and len(full_content) > len(article.get("content") or ""):
            logger.info("Successfully scraped full content from: %s", url)
            article["content"] = full_content
        else:
            logger.warning("Could not scrape additional content from %s. Keeping original.", url)

    except requests.exceptions.HTTPError as exc:
        status_code = exc.response.status_code if exc.response is not None else 0
        if status_code == 404:
            logger.warning("URL not found (404), skipping: %s", url)
        elif status_code == 429:
            logger.error("Rate limited (429) after retries for %s", url)
        else:
            logger.error("HTTP error %s for %s: %s", status_code, url, exc)
    except requests.exceptions.RequestException as exc:
        logger.error("Failed to fetch or scrape URL %s: %s", url, exc)
    except Exception as exc:
        logger.error("Unexpected error while processing %s: %s", url, exc)

    return article


def scrape_and_enrich_content(**context):
    """Performs concurrent web scraping on article URLs with robots.txt compliance.

    Uses ThreadPoolExecutor with configurable workers, tenacity retry with
    exponential backoff, and a configurable User-Agent. Robots.txt is fetched
    once per domain and cached in a dict initialized INSIDE this function.

    Args:
        context (dict): Airflow context for accessing XCom data.

    Returns:
        list: List of articles with the 'content' field updated with scraped data.
    """
    # Retrieve articles from the previous task
    articles = context["ti"].xcom_pull(task_ids="extract_newsapi_task")

    if not articles:
        logger.warning("No articles to scrape.")
        return []

    # --- Resolve configuration INSIDE the task callable ---
    max_workers = resolve_max_scrape_workers()
    user_agent = resolve_user_agent()

    logger.info(
        "Starting concurrent scraping with %d workers, User-Agent: %s",
        max_workers,
        user_agent.split("/")[0],
    )

    # --- Build robots.txt cache (fetch once per domain before ThreadPool) ---
    # Cache is initialized INSIDE the task function, NEVER at module global scope.
    robots_cache: dict = {}
    domains_seen: set = set()

    for article in articles:
        url = article.get("url")
        if not url:
            continue
        domain = urlparse(url).netloc
        if domain not in domains_seen:
            domains_seen.add(domain)
            rp = RobotFileParser()
            rp.set_url(f"https://{domain}/robots.txt")
            try:
                rp.read()
                robots_cache[domain] = rp
                logger.debug("Fetched robots.txt for %s", domain)
            except Exception:
                logger.warning("Could not fetch robots.txt for %s", domain)
                robots_cache[domain] = None

    # --- Scrape concurrently ---
    results: list = []

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_map = {}
        for i, article in enumerate(articles):
            future = executor.submit(
                _scrape_single_article,
                article.copy(),
                user_agent,
                robots_cache,
            )
            future_map[future] = i

        for future in as_completed(future_map):
            idx = future_map[future]
            try:
                result = future.result()
                results.append((idx, result))
            except Exception as exc:
                logger.error("Scrape worker failed for index %d: %s", idx, exc)

    # Restore original order
    results.sort(key=lambda x: x[0])
    enriched_articles = [r[1] for r in results]

    logger.info("Scraping complete. Processed %d articles.", len(enriched_articles))
    return enriched_articles
