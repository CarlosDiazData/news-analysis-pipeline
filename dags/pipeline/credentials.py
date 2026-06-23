"""
Stratified credential resolution for the news ETL pipeline.

Resolves credentials in strict order:
  Airflow Connection/Variable → env vars → .env → defaults.

All resolution functions are designed to be called inside task execution
context (PythonOperator callables), NEVER at DAG module top-level.
"""

import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)


def _load_dotenv() -> None:
    """Load .env file into os.environ. Idempotent — safe to call multiple times."""
    try:
        from dotenv import load_dotenv as _load_dotenv_impl

        # .env lives at project root: two levels above dags/pipeline/
        dotenv_path = os.path.join(os.path.dirname(__file__), "..", "..", ".env")
        if os.path.exists(dotenv_path):
            _load_dotenv_impl(dotenv_path)
    except ImportError:
        pass


def _try_airflow_connection(conn_id: str) -> Optional[dict[str, str]]:
    """Resolve DB credentials from an Airflow Connection.

    Returns None if Airflow is unavailable or the connection doesn't exist.
    """
    try:
        from airflow.hooks.base import BaseHook

        conn = BaseHook.get_connection(conn_id)
        if conn:
            return {
                "host": conn.host or "postgres",
                "port": str(conn.port) if conn.port else "5432",
                "dbname": conn.schema or "airflow_db",
                "user": conn.login or "airflow",
                "password": conn.password or "airflow",
            }
    except Exception as exc:
        logger.debug("Airflow Connection '%s' not available: %s", conn_id, exc)
    return None


def _try_airflow_variable(key: str) -> Optional[str]:
    """Resolve a value from an Airflow Variable.

    Returns None if Airflow is unavailable or the variable is not set.
    """
    try:
        from airflow.models import Variable

        val = Variable.get(key)
        if val:
            return val
    except Exception as exc:
        logger.debug("Airflow Variable '%s' not available: %s", key, exc)
    return None


def resolve_db_creds(conn_id: str = "postgres_default") -> dict[str, str]:
    """Resolve PostgreSQL credentials with stratified fallback.

    Resolution order:
        1. Airflow Connection (encrypted store)
        2. Environment variables (POSTGRES_HOST, POSTGRES_PORT, etc.)
        3. .env file
        4. Default values

    Returns:
        dict with keys: host, port, dbname, user, password
    """
    # 1. Airflow Connection
    conn_creds = _try_airflow_connection(conn_id)
    if conn_creds:
        logger.debug("Resolved DB creds from Airflow Connection '%s'", conn_id)
        return conn_creds

    # 2. Environment variables + .env fallback
    _load_dotenv()

    env_creds = {
        "host": os.environ.get("POSTGRES_HOST", "postgres"),
        "port": os.environ.get("POSTGRES_PORT", "5432"),
        "dbname": os.environ.get("POSTGRES_DB", "airflow_db"),
        "user": os.environ.get("POSTGRES_USER", "airflow"),
        "password": os.environ.get("POSTGRES_PASSWORD", "airflow"),
    }
    logger.debug("Resolved DB creds from environment")
    return env_creds


def resolve_newsapi_key() -> str:
    """Resolve the NewsAPI key with stratified fallback.

    Resolution order:
        1. Airflow Variable (NEWS_API_KEY)
        2. Environment variable (NEWS_API_KEY)
        3. .env file

    Returns:
        str: The resolved NewsAPI key.

    Raises:
        RuntimeError: If the key cannot be resolved from any source.
    """
    # 1. Airflow Variable
    var_val = _try_airflow_variable("NEWS_API_KEY")
    if var_val:
        logger.debug("Resolved NewsAPI key from Airflow Variable")
        return var_val

    # 2. Environment variables + .env fallback
    _load_dotenv()

    env_val = os.environ.get("NEWS_API_KEY")
    if env_val:
        logger.debug("Resolved NewsAPI key from environment")
        return env_val

    raise RuntimeError(
        "NewsAPI key not found. Set NEWS_API_KEY as an Airflow Variable, "
        "environment variable, or in a .env file at the project root."
    )


def resolve_newsapi_country() -> str:
    """Resolve the NewsAPI country parameter with stratified fallback.

    Resolution order:
        1. Airflow Variable (NEWS_API_COUNTRY)
        2. Environment variable (NEWS_API_COUNTRY)
        3. .env file
        4. Default: config.NEWS_API_COUNTRY ("us")

    Returns:
        str: The resolved country code (e.g., "us", "ar", "fr").
    """
    # 1. Airflow Variable
    var_val = _try_airflow_variable("NEWS_API_COUNTRY")
    if var_val:
        return var_val

    # 2. Environment variables + .env fallback
    _load_dotenv()

    env_val = os.environ.get("NEWS_API_COUNTRY")
    if env_val:
        return env_val

    from pipeline.config import NEWS_API_COUNTRY

    return NEWS_API_COUNTRY


def resolve_newsapi_topic() -> Optional[str]:
    """Resolve the NewsAPI topic (category) parameter with stratified fallback.

    Resolution order:
        1. Airflow Variable (NEWS_API_TOPIC)
        2. Environment variable (NEWS_API_TOPIC)
        3. .env file
        4. Default: config.NEWS_API_TOPIC (None — no category filter)

    Returns:
        str | None: The resolved topic (e.g., "sports", "technology") or None.
    """
    # 1. Airflow Variable
    var_val = _try_airflow_variable("NEWS_API_TOPIC")
    if var_val:
        return var_val

    # 2. Environment variables + .env fallback
    _load_dotenv()

    env_val = os.environ.get("NEWS_API_TOPIC")
    if env_val:
        return env_val

    from pipeline.config import NEWS_API_TOPIC

    return NEWS_API_TOPIC


def resolve_user_agent() -> str:
    """Resolve the User-Agent string for HTTP scraping requests.

    Resolution order:
        1. Airflow Variable (USER_AGENT)
        2. Environment variable (USER_AGENT)
        3. .env file
        4. Default: "NewsETL/1.0 (news-analysis-pipeline)"

    Returns:
        str: The resolved User-Agent string.
    """
    # 1. Airflow Variable
    var_val = _try_airflow_variable("USER_AGENT")
    if var_val:
        return var_val

    # 2. Environment variables + .env fallback
    _load_dotenv()

    env_val = os.environ.get("USER_AGENT")
    if env_val:
        return env_val

    return "NewsETL/1.0 (news-analysis-pipeline)"


def resolve_max_scrape_workers() -> int:
    """Resolve the maximum number of concurrent scraping workers.

    Resolution order:
        1. Airflow Variable (MAX_SCRAPE_WORKERS)
        2. Environment variable (MAX_SCRAPE_WORKERS)
        3. .env file
        4. Default: 4

    The returned value is always clamped to the range [1, 8].

    Returns:
        int: Number of workers between 1 and 8.
    """
    raw: Optional[str] = None

    # 1. Airflow Variable
    var_val = _try_airflow_variable("MAX_SCRAPE_WORKERS")
    if var_val is not None:
        raw = var_val

    if raw is None:
        # 2. Environment variables + .env fallback
        _load_dotenv()
        raw = os.environ.get("MAX_SCRAPE_WORKERS")

    if raw is not None:
        try:
            workers = int(raw)
            return max(1, min(8, workers))
        except (ValueError, TypeError):
            logger.warning("Invalid MAX_SCRAPE_WORKERS value '%s', using default 4", raw)

    return 4


def get_db_connection():
    """Get a database connection using stratified credential resolution.

    First attempt: Airflow PostgresHook via Connection (encrypted store).
    Fallback: raw psycopg2 connection using env-resolved credentials.

    Returns:
        A PEP 249 database connection object.

    Raises:
        RuntimeError: If no connection can be established.
    """
    # 1. Try Airflow PostgresHook first
    try:
        from airflow.providers.postgres.hooks.postgres import PostgresHook

        hook = PostgresHook(postgres_conn_id="postgres_default")
        return hook.get_conn()
    except Exception as exc:
        logger.debug("Airflow PostgresHook unavailable, falling back to env creds: %s", exc)

    # 2. Fallback: raw psycopg2 with env creds
    creds = resolve_db_creds()
    try:
        import psycopg2

        conn = psycopg2.connect(
            host=creds["host"],
            port=creds["port"],
            dbname=creds["dbname"],
            user=creds["user"],
            password=creds["password"],
        )
        logger.debug("Connected to PostgreSQL via env-resolved credentials")
        return conn
    except Exception as exc:
        raise RuntimeError(f"Failed to connect to PostgreSQL: {exc}") from exc
