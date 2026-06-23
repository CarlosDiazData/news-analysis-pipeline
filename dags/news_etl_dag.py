"""
NewsAPI to PostgreSQL ETL DAG
This DAG extracts news articles from NewsAPI, enriches them via web scraping,
and loads them into a PostgreSQL database.
"""

from datetime import datetime, timedelta

from airflow.sdk import DAG
from airflow.providers.standard.operators.python import PythonOperator

from pipeline.config import DAG_ID
from pipeline.extract import extract_data_from_newsapi
from pipeline.scrape import scrape_and_enrich_content
from pipeline.analyze import analyze_articles
from pipeline.load import load_data_to_postgres
from pipeline.sla_callbacks import on_sla_miss


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
    sla_miss_callback=on_sla_miss,
    doc_md="""
    # NewsAPI to PostgreSQL ETL with Web Scraping

    This DAG extracts news articles from NewsAPI, scrapes the full content
    from each article's URL, performs NLP analysis (sentiment + NER), and then
    loads the enriched data into PostgreSQL.

    ## Tasks:
    1. `extract_newsapi_task`: Extracts top headlines from NewsAPI.
    2. `scrape_content_task`: Scrapes the full content for each article.
     3. `ml_analysis_task`: Analyzes articles with sentiment analysis and NER.
     4. `load_postgres_task`: Loads the enriched articles into PostgreSQL
        (SLA: 9 hours — data must be ready before 9 AM).
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

    # Task 4: Load enriched data into PostgreSQL (9h SLA — data must be
    #   ready before 9 AM consumption window when DAG runs at midnight).
    load_task = PythonOperator(
        task_id="load_postgres_task",
        python_callable=load_data_to_postgres,
        sla=timedelta(hours=9),
    )

    # Task dependency chain
    extract_task >> scrape_task >> ml_analysis_task >> load_task
