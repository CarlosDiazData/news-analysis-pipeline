"""
NewsAPI to PostgreSQL ETL DAG
This DAG extracts news articles from NewsAPI, enriches them via web scraping, 
and loads them into a PostgreSQL database.
"""

# Airflow and provider modules
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.providers.postgres.hooks.postgres import PostgresHook
from airflow.exceptions import AirflowException
from datetime import datetime, timedelta

# Standard library modules
import requests
import logging
import os
import json

# Web Scraping and ML modules
from bs4 import BeautifulSoup
from textblob import TextBlob
import spacy

# Define constants for the DAG configuration
DAG_ID = 'ingestion_newsapi_postgres_with_scraping'
NEWS_API_ENDPOINT = "https://newsapi.org/v2/top-headlines"
DEFAULT_CONN_ID = 'postgres_default'

# Get a logger for this module
logger = logging.getLogger(__name__)

# --- Task 1: Extract from NewsAPI ---
def extract_data_from_newsapi():
    """
    Extracts news data from NewsAPI.
    
    Returns:
        list: List of articles retrieved from the API.
    
    Raises:
        AirflowException: If API request fails or returns invalid data.
    """
    # Fetch NewsAPI key from environment variables
    news_api_key = os.environ.get("NEWS_API_KEY")
    if not news_api_key:
        raise AirflowException("News API key not configured in environment variables")
    
    # Define API parameters (country: US, max 100 articles)
    params = {
        'apiKey': news_api_key,
        'country': 'us',
        'pageSize': 100,
    }
    
    try:
        # Make API request with timeout
        logger.info("Requesting data from NewsAPI")
        response = requests.get(
            NEWS_API_ENDPOINT,
            params=params,
            timeout=30  
        )
        response.raise_for_status()
        
        data = response.json()
        
        # Check API status field in the response
        if data.get('status') != 'ok':
            raise AirflowException(f"API Error: {data.get('message', 'Unknown error')}")
            
        articles = data.get('articles', [])
        logger.info(f"Successfully extracted {len(articles)} articles")
        return articles
        
    except requests.exceptions.RequestException as e:
        logger.error(f"NewsAPI request failed: {str(e)}")
        raise AirflowException(f"Connection error: {str(e)}")
    
# --- Task 2: Scrape Full Content ---
def scrape_and_enrich_content(**context):
    """
    Performs web scraping on article URLs to get the full content.
    
    Args:
        context (dict): Airflow context for accessing XCom data.
        
    Returns:
        list: List of articles with the 'content' field updated with scraped data.
    """
    # Retrieve articles from the previous task
    articles = context['ti'].xcom_pull(task_ids='extract_newsapi_task')
    
    if not articles:
        logger.warning("No articles to scrape.")
        return []

    enriched_articles = []
    
    for article in articles:
        url = article.get('url')
        if not url:
            enriched_articles.append(article)
            continue

        try:
            # Set headers to mimic a browser visit, which helps avoid being blocked
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            # Fetch the article page
            response = requests.get(url, headers=headers, timeout=15)
            response.raise_for_status()

            # Parse the HTML content
            soup = BeautifulSoup(response.content, 'html.parser')

            paragraphs = soup.find_all('p')
            full_content = ' '.join([p.get_text() for p in paragraphs])
            
            # Update the article's content if scraping was successful
            if full_content and len(full_content) > len(article.get('content') or ''):
                logger.info(f"Successfully scraped full content from: {url}")
                article['content'] = full_content
            else:
                logger.warning(f"Could not scrape additional content from {url}. Keeping original.")

        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to fetch or scrape URL {url}: {e}")
            # In case of an error, we keep the original (truncated) content
        except Exception as e:
            logger.error(f"An unexpected error occurred while processing {url}: {e}")

        enriched_articles.append(article)

    return enriched_articles

# --- Task 3: Perform ML Analysis ---
def analyze_articles(**context):
    """Analyzes articles for sentiment and named entities using ML models.

    Args:
        context (dict): Airflow context for accessing XCom data.

    Returns:
        list: List of articles enriched with sentiment and named entity data.
    """
    articles = context['ti'].xcom_pull(task_ids='scrape_content_task')
    if not articles:
        logger.warning("No articles to analyze.")
        return []

    try:
        nlp = spacy.load("en_core_web_sm")
    except OSError:
        logger.error("spaCy model 'en_core_web_sm' not found. Ensure it was downloaded in the Docker image.")
        raise

    analyzed_articles = []
    for article in articles:
        content = article.get('content')
        if not content:
            article.update({'sentiment_polarity': None, 'sentiment_subjectivity': None, 'named_entities': None})
            analyzed_articles.append(article)
            continue
        
        # 1. Sentiment Analysis with TextBlob
        blob = TextBlob(content)
        article['sentiment_polarity'] = blob.sentiment.polarity
        article['sentiment_subjectivity'] = blob.sentiment.subjectivity

        # 2. Named Entity Recognition (NER) with spaCy
        # Limit content length to prevent memory issues with very long articles
        doc = nlp(content[:100000]) 
        entities = [{'text': ent.text, 'label': ent.label_} for ent in doc.ents if ent.label_ in ['PERSON', 'ORG', 'GPE', 'PRODUCT']]
        article['named_entities'] = entities
        
        logger.info(f"Analyzed article: {article.get('title', 'No Title')[:50]}...")
        analyzed_articles.append(article)
        
    return analyzed_articles

def load_data_to_postgres(**context):
    """
    Loads data into PostgreSQL with transaction management and duplicate handling.
    
    Args:
        context (dict): Airflow context for accessing XCom data.
    
    Raises:
        AirflowException: If no data to load or database error occurs.
    """
    articles = context['ti'].xcom_pull(task_ids='ml_analysis_task')
    
    if not articles or len(articles) == 0:
        logger.warning("No news data to load into PostgreSQL")
        return 0
    
    logger.info(f"Processing {len(articles)} articles for database insertion")
    
    hook = PostgresHook(postgres_conn_id=DEFAULT_CONN_ID)
    conn = hook.get_conn()
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
            n.get('title'), n.get('description'), n.get('url'), n.get('urlToImage'),
            n.get('publishedAt'), n.get('source', {}).get('name'), n.get('author'),
            n.get('content'), n.get('sentiment_polarity'), n.get('sentiment_subjectivity'),
            json.dumps(n.get('named_entities')) if n.get('named_entities') is not None else None
        ) for n in articles
    ]
        
    try:
        cursor.executemany(sql, records)
        conn.commit()
        logger.info(f"Successfully inserted or updated {cursor.rowcount} records.")
    except Exception as e:
        conn.rollback()
        logger.error(f"Database operation failed: {e}")
        raise AirflowException(f"Database error: {e}")
    finally:
        cursor.close()
        conn.close()

# Define the DAG configuration
default_args = {
    'owner': 'airflow',
    'retries': 2,                 
    'retry_delay': timedelta(minutes=5),  
}

with DAG(
    dag_id=DAG_ID,
    description='News ingestion from NewsAPI to PostgreSQL with web scraping enrichment',
    start_date=datetime(2024, 1, 1),
    schedule_interval='@daily', 
    catchup=False,
    tags=['newsapi', 'postgres', 'scraping', 'news'],
    default_args=default_args,
    doc_md="""
    # NewsAPI to PostgreSQL ETL with Web Scraping
    
    This DAG extracts news articles from NewsAPI, scrapes the full content from each article's URL, and then loads the enriched data into PostgreSQL.
    
    ## Tasks:
    1. `extract_newsapi_task`: Extracts top headlines from NewsAPI.
    2. `scrape_content_task`: Scrapes the full content for each article.
    3. `load_postgres_task`: Loads the enriched articles into PostgreSQL.
    """
) as dag:
    # Task 1: Extract data from NewsAPI
    extract_task = PythonOperator(
        task_id='extract_newsapi_task',
        python_callable=extract_data_from_newsapi,
    )

    # Task 2: Scrape and enrich the articles with full content
    scrape_task = PythonOperator(
        task_id='scrape_content_task',
        python_callable=scrape_and_enrich_content,
        provide_context=True,
    )

    # Task 3: ML analysis 
    ml_analysis_task = PythonOperator(
        task_id='ml_analysis_task',
        python_callable=analyze_articles,
    )

    # Task 4: Load enriched data into PostgreSQL
    load_task = PythonOperator(
        task_id='load_postgres_task',
        python_callable=load_data_to_postgres,
        provide_context=True,
    )

    # Task dependency chain
    extract_task >> scrape_task >> ml_analysis_task >> load_task
