"""
NLP analysis module — sentiment analysis with TextBlob and NER with spaCy.
"""

import logging

import spacy
from textblob import TextBlob

logger = logging.getLogger(__name__)


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
