"""
Unit tests for NLP analysis (analyze_articles).

Tests cover: sentiment polarity/subjectivity, named entity extraction,
empty content edge case, and spaCy model handling.
"""

from unittest.mock import MagicMock

import pytest


@pytest.fixture
def enriched_article():
    """An article that has been through scraping with content populated."""
    return {
        "title": "Breaking News: Markets Rally",
        "description": "Stocks surge as economic data exceeds expectations.",
        "url": "https://example.com/markets",
        "urlToImage": None,
        "publishedAt": "2024-06-15T09:00:00Z",
        "source": {"name": "Financial Times"},
        "author": "Jane Analyst",
        "content": (
            "Global markets rallied strongly today as positive economic "
            "indicators from the United States and Europe surprised investors. "
            "The Dow Jones Industrial Average gained over 500 points while "
            "the S&P 500 reached a new all-time high. Federal Reserve "
            "Chair Jerome Powell commented on the encouraging data."
        ),
    }


@pytest.fixture
def articles_with_varied_content(enriched_article):
    """Articles including one with empty content."""
    empty_content = {
        "title": "Missing Content",
        "url": "https://example.com/empty",
        "content": None,
        "source": {"name": "Unknown"},
        "publishedAt": "2024-06-15T10:00:00Z",
    }
    return [enriched_article, empty_content]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestAnalyzeArticles:
    """Tests for the analyze_articles task function."""

    def test_sentiment_and_entities_added(self, enriched_article):
        """GIVEN an article with text content
        WHEN analyze_articles processes it
        THEN sentiment_polarity, sentiment_subjectivity, and
             named_entities are populated."""
        mock_context = {"ti": MagicMock()}
        mock_context["ti"].xcom_pull.return_value = [enriched_article]

        from news_etl_dag import analyze_articles

        result = analyze_articles(**mock_context)

        assert len(result) == 1
        article = result[0]
        assert "sentiment_polarity" in article
        assert "sentiment_subjectivity" in article
        assert "named_entities" in article
        # Sentiment scores should be numeric
        assert isinstance(article["sentiment_polarity"], float)
        assert isinstance(article["sentiment_subjectivity"], float)
        # named_entities should be a list of dicts with text/label
        assert isinstance(article["named_entities"], list)
        if article["named_entities"]:
            entity = article["named_entities"][0]
            assert "text" in entity
            assert "label" in entity

    def test_empty_content_gets_none_values(self, articles_with_varied_content):
        """GIVEN an article with empty/missing content
        WHEN analyze_articles processes it
        THEN sentiment and entities are set to None."""
        mock_context = {"ti": MagicMock()}
        mock_context["ti"].xcom_pull.return_value = articles_with_varied_content

        from news_etl_dag import analyze_articles

        result = analyze_articles(**mock_context)

        assert len(result) == 2
        # First article (has content) — should have values
        assert result[0]["sentiment_polarity"] is not None
        # Second article (empty content) — should have None
        assert result[1]["sentiment_polarity"] is None
        assert result[1]["sentiment_subjectivity"] is None
        assert result[1]["named_entities"] is None

    def test_no_articles_returns_empty_list(self):
        """GIVEN no articles to analyze
        WHEN analyze_articles runs THEN empty list is returned."""
        mock_context = {"ti": MagicMock()}
        mock_context["ti"].xcom_pull.return_value = []

        from news_etl_dag import analyze_articles

        result = analyze_articles(**mock_context)
        assert result == []

    def test_named_entities_filtered_by_label(self, enriched_article):
        """GIVEN an article with PERSON and ORG mentions
        WHEN analyze_articles runs
        THEN only PERSON, ORG, GPE, PRODUCT entities are returned."""
        mock_context = {"ti": MagicMock()}
        mock_context["ti"].xcom_pull.return_value = [enriched_article]

        from news_etl_dag import analyze_articles

        result = analyze_articles(**mock_context)
        article = result[0]

        # Verify all returned entities have valid labels
        valid_labels = {"PERSON", "ORG", "GPE", "PRODUCT"}
        for entity in article["named_entities"]:
            assert entity["label"] in valid_labels, f"Unexpected label: {entity['label']}"
