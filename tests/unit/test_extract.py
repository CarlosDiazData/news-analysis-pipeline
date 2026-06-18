"""
Unit tests for NewsAPI extraction (extract_data_from_newsapi).

All HTTP calls are intercepted by requests-mock — zero real network.
"""

from unittest.mock import patch

import pytest
from airflow.exceptions import AirflowException

NEWS_API_ENDPOINT = "https://newsapi.org/v2/top-headlines"


# ---------------------------------------------------------------------------
# Tests: successful extraction
# ---------------------------------------------------------------------------


class TestExtractSuccess:
    """Happy-path extraction tests."""

    def test_200_returns_articles(self, requests_mock, newsapi_response):
        """GIVEN NewsAPI returns 200 with valid articles
        WHEN extract_data_from_newsapi runs
        THEN it returns the parsed article list."""
        requests_mock.get(NEWS_API_ENDPOINT, json=newsapi_response, status_code=200)

        with patch("pipeline.extract.resolve_newsapi_key", return_value="test-api-key"):
            from pipeline.extract import extract_data_from_newsapi

            result = extract_data_from_newsapi()

        assert len(result) == 3
        assert result[0]["title"] == "Test Article 1"
        assert result[1]["source"]["name"] == "Other Source"

    def test_empty_articles_list(self, requests_mock):
        """GIVEN NewsAPI returns 200 with empty articles list
        WHEN extract runs THEN it returns an empty list."""
        response = {"status": "ok", "totalResults": 0, "articles": []}
        requests_mock.get(NEWS_API_ENDPOINT, json=response, status_code=200)

        with patch("pipeline.extract.resolve_newsapi_key", return_value="test-api-key"):
            from pipeline.extract import extract_data_from_newsapi

            result = extract_data_from_newsapi()

        assert result == []


# ---------------------------------------------------------------------------
# Tests: error handling
# ---------------------------------------------------------------------------


class TestExtractErrors:
    """Extraction error-handling tests."""

    def test_non_200_raises_airflow_exception(self, requests_mock):
        """GIVEN NewsAPI returns a non-200 status
        WHEN extract runs THEN it raises AirflowException."""
        requests_mock.get(NEWS_API_ENDPOINT, status_code=401, reason="Unauthorized")

        with patch("pipeline.extract.resolve_newsapi_key", return_value="test-api-key"):
            from pipeline.extract import extract_data_from_newsapi

            with pytest.raises(AirflowException, match="Connection error"):
                extract_data_from_newsapi()

    def test_api_error_status_raises(self, requests_mock):
        """GIVEN NewsAPI returns 200 but with status: 'error'
        WHEN extract runs THEN it raises AirflowException."""
        response = {
            "status": "error",
            "message": "API key is invalid.",
            "code": "apiKeyInvalid",
        }
        requests_mock.get(NEWS_API_ENDPOINT, json=response, status_code=200)

        with patch("pipeline.extract.resolve_newsapi_key", return_value="test-api-key"):
            from pipeline.extract import extract_data_from_newsapi

            with pytest.raises(AirflowException, match="API key is invalid"):
                extract_data_from_newsapi()

    def test_missing_api_key_raises(self):
        """GIVEN NEWS_API_KEY is not resolvable
        WHEN extract runs THEN it raises AirflowException."""
        with patch(
            "pipeline.extract.resolve_newsapi_key",
            side_effect=RuntimeError("NewsAPI key not found"),
        ):
            from pipeline.extract import extract_data_from_newsapi

            with pytest.raises(AirflowException, match="NewsAPI key not found"):
                extract_data_from_newsapi()
