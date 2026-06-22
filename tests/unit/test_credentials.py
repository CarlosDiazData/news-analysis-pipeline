"""
Unit tests for stratified credential resolution functions.

Tests resolve_newsapi_country() and resolve_newsapi_topic() covering:
- Default values when nothing is configured
- Environment variable overrides
- Airflow Variable overrides
"""

import os
from unittest.mock import patch

import pytest

from pipeline.credentials import resolve_newsapi_country, resolve_newsapi_topic


# ---------------------------------------------------------------------------
# resolve_newsapi_country tests
# ---------------------------------------------------------------------------


class TestResolveNewsapiCountry:
    """Tests for resolve_newsapi_country()."""

    def test_default_country_is_us(self, monkeypatch):
        """GIVEN no NEWS_API_COUNTRY in env or Airflow Variables
        WHEN resolve_newsapi_country() is called
        THEN it returns 'us'."""
        monkeypatch.delenv("NEWS_API_COUNTRY", raising=False)

        with patch(
            "pipeline.credentials._try_airflow_variable", return_value=None
        ):
            with patch("pipeline.credentials._load_dotenv"):
                result = resolve_newsapi_country()

        assert result == "us"

    def test_env_var_overrides_default(self, monkeypatch):
        """GIVEN NEWS_API_COUNTRY=fr set in environment
        WHEN resolve_newsapi_country() is called
        THEN it returns 'fr'."""
        monkeypatch.setenv("NEWS_API_COUNTRY", "fr")

        with patch(
            "pipeline.credentials._try_airflow_variable", return_value=None
        ):
            with patch("pipeline.credentials._load_dotenv"):
                result = resolve_newsapi_country()

        assert result == "fr"

    def test_airflow_variable_has_highest_priority(self, monkeypatch):
        """GIVEN Airflow Variable NEWS_API_COUNTRY='ar' AND env='fr'
        WHEN resolve_newsapi_country() is called
        THEN it returns 'ar' (Airflow Variable wins)."""
        monkeypatch.setenv("NEWS_API_COUNTRY", "fr")

        with patch(
            "pipeline.credentials._try_airflow_variable", return_value="ar"
        ):
            with patch("pipeline.credentials._load_dotenv"):
                result = resolve_newsapi_country()

        assert result == "ar"


# ---------------------------------------------------------------------------
# resolve_newsapi_topic tests
# ---------------------------------------------------------------------------


class TestResolveNewsapiTopic:
    """Tests for resolve_newsapi_topic()."""

    def test_default_topic_is_none(self, monkeypatch):
        """GIVEN no NEWS_API_TOPIC in env or Airflow Variables
        WHEN resolve_newsapi_topic() is called
        THEN it returns None."""
        monkeypatch.delenv("NEWS_API_TOPIC", raising=False)

        with patch(
            "pipeline.credentials._try_airflow_variable", return_value=None
        ):
            with patch("pipeline.credentials._load_dotenv"):
                result = resolve_newsapi_topic()

        assert result is None

    def test_env_var_overrides_default(self, monkeypatch):
        """GIVEN NEWS_API_TOPIC=sports set in environment
        WHEN resolve_newsapi_topic() is called
        THEN it returns 'sports'."""
        monkeypatch.setenv("NEWS_API_TOPIC", "sports")

        with patch(
            "pipeline.credentials._try_airflow_variable", return_value=None
        ):
            with patch("pipeline.credentials._load_dotenv"):
                result = resolve_newsapi_topic()

        assert result == "sports"

    def test_airflow_variable_has_highest_priority(self, monkeypatch):
        """GIVEN Airflow Variable NEWS_API_TOPIC='technology' AND env='sports'
        WHEN resolve_newsapi_topic() is called
        THEN it returns 'technology' (Airflow Variable wins)."""
        monkeypatch.setenv("NEWS_API_TOPIC", "sports")

        with patch(
            "pipeline.credentials._try_airflow_variable", return_value="technology"
        ):
            with patch("pipeline.credentials._load_dotenv"):
                result = resolve_newsapi_topic()

        assert result == "technology"
