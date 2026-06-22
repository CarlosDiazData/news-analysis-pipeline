"""
NewsAPI to PostgreSQL ETL DAG
This DAG extracts news articles from NewsAPI, enriches them via web scraping,
and loads them into a PostgreSQL database.
"""

# Airflow and provider modules
# Standard library modules
import json
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

# HTTP and retry
import requests
import spacy
from airflow import DAG
from airflow.exceptions import AirflowException
from airflow.operators.python import PythonOperator

# Web Scraping and ML modules
from bs4 import BeautifulSoup

# Pipeline modules
from pipeline.config import DAG_ID, NEWS_API_ENDPOINT

# Credential resolution (task-scoped, never at module top-level)
from pipeline.credentials import (
    get_db_connection,
    resolve_max_scrape_workers,
    resolve_newsapi_key,
    resolve_user_agent,
)
from tenacity import (
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)
from textblob import TextBlob

# Get a logger for this module
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# tenacity retry helper — used by the scraping worker
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Task 1: Extract from NewsAPI
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Task 2: Scrape Full Content (parallel, with retry and robots.txt)
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Task 3: Perform ML Analysis
# ---------------------------------------------------------------------------


def analyze_articles(**context):
    """Analyzes articles for sentiment and named entities using ML models.

    Args:
        context (dict): Airflow context for accessing XCom data.

    Returns:
        list: List of articles enriched with sentiment and named entity data.
    """
    articles = context["ti"].xcom_pull(task_ids="scrape_content_task")
    if not articles:
        logger.warning("No articles to analyze.")
        return []

    try:
        nlp = spacy.load("en_core_web_sm")
    except OSError:
        logger.error(
            "spaCy model 'en_core_web_sm' not found. Ensure it was downloaded in the Docker image."
        )
        raise

    analyzed_articles = []
    for article in articles:
        content = article.get("content")
        if not content:
            article.update(
                {
                    "sentiment_polarity": None,
                    "sentiment_subjectivity": None,
                    "named_entities": None,
                }
            )
            analyzed_articles.append(article)
            continue

        # 1. Sentiment Analysis with TextBlob
        blob = TextBlob(content)
        article["sentiment_polarity"] = blob.sentiment.polarity
        article["sentiment_subjectivity"] = blob.sentiment.subjectivity

        # 2. Named Entity Recognition (NER) with spaCy
        # Limit content length to prevent memory issues
        doc = nlp(content[:100000])
        entities = [
            {"text": ent.text, "label": ent.label_}
            for ent in doc.ents
            if ent.label_ in ["PERSON", "ORG", "GPE", "PRODUCT"]
        ]
        article["named_entities"] = entities

        logger.info("Analyzed article: %s...", article.get("title", "No Title")[:50])
        analyzed_articles.append(article)

    return analyzed_articles


# ---------------------------------------------------------------------------
# Task 4: Load Data into PostgreSQL
# ---------------------------------------------------------------------------


def load_data_to_postgres(**context):
    """Loads data into PostgreSQL with transaction management and duplicate handling.

    Uses stratified credential resolution inside the task callable:
    first Airflow Connection, then env vars.

    Args:
        context (dict): Airflow context for accessing XCom data.

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

    sql = """
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
        cursor.executemany(sql, records)
        conn.commit()
        logger.info("Successfully inserted or updated %s records.", cursor.rowcount)
    except Exception as exc:
        conn.rollback()
        logger.error("Database operation failed: %s", exc)
        raise AirflowException(f"Database error: {exc}") from exc
    finally:
        cursor.close()
        conn.close()


# ===========================================================================
# DAG Definition — NO credential reads, Variable gets, or Connection calls
# at module top-level. All resolution inside task callables only.
# ===========================================================================

default_args = {
    "owner": "airflow",
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
}

with DAG(
    dag_id=DAG_ID,
    description="News ingestion from NewsAPI to PostgreSQL with web scraping enrichment",
    start_date=datetime(2024, 1, 1),
    schedule="@daily",
    catchup=False,
    tags=["newsapi", "postgres", "scraping", "news"],
    default_args=default_args,
    doc_md="""
    # NewsAPI to PostgreSQL ETL with Web Scraping

    This DAG extracts news articles from NewsAPI, scrapes the full content
    from each article's URL, and then loads the enriched data into PostgreSQL.

    ## Tasks:
    1. `extract_newsapi_task`: Extracts top headlines from NewsAPI.
    2. `scrape_content_task`: Scrapes the full content for each article.
    3. `ml_analysis_task`: Performs sentiment analysis and NER.
    4. `load_postgres_task`: Loads the enriched articles into PostgreSQL.
    """,
) as dag:
    # Task 1: Extract data from NewsAPI
    extract_task = PythonOperator(
        task_id="extract_newsapi_task",
        python_callable=extract_data_from_newsapi,
    )

    # Task 2: Scrape and enrich the articles with full content (parallel)
    scrape_task = PythonOperator(
        task_id="scrape_content_task",
        python_callable=scrape_and_enrich_content,
    )

    # Task 3: ML analysis
    ml_analysis_task = PythonOperator(
        task_id="ml_analysis_task",
        python_callable=analyze_articles,
    )

    # Task 4: Load enriched data into PostgreSQL
    load_task = PythonOperator(
        task_id="load_postgres_task",
        python_callable=load_data_to_postgres,
    )

    # Task dependency chain
    extract_task >> scrape_task >> ml_analysis_task >> load_task
