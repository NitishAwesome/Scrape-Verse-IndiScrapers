"""Unit tests for DOMFetcher and Bright Data Web Unlocker integration."""

import os
import sys
import unittest
from unittest.mock import MagicMock, patch

import httpx

# Ensure root path is accessible for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.scraper.config import ScraperSettings
from backend.scraper.dom_fetcher import (
    DOMFetcher,
    DOMFetcherError,
    _mask_token,
    _sanitize_error_message,
)


class TestDOMFetcher(unittest.TestCase):
    """Tests for DOMFetcher."""

    def test_token_masking(self):
        """Test that tokens are safely masked."""
        self.assertEqual(_mask_token(None), "***")
        self.assertEqual(_mask_token(""), "***")
        self.assertEqual(_mask_token("short"), "***")
        masked = _mask_token("1c69b84c-79b6-479f-abd4-bc01a45cc3aa")
        self.assertTrue(masked.startswith("1c69..."))
        self.assertTrue(masked.endswith("c3aa"))
        self.assertNotIn("79b6-479f", masked)

    def test_sanitize_error_message(self):
        """Test token removal from error messages."""
        token = "secret-token-12345"
        msg = f"HTTP 401 Unauthorized for Bearer {token} on endpoint"
        sanitized = _sanitize_error_message(msg, token)
        self.assertNotIn(token, sanitized)
        self.assertIn("secr...2345", sanitized)

    def test_empty_target_url_raises_error(self):
        """Test that empty target URL raises DOMFetcherError."""
        fetcher = DOMFetcher()
        with self.assertRaises(DOMFetcherError):
            fetcher.fetch("")

    @patch("backend.scraper.dom_fetcher.httpx.Client")
    def test_fetch_via_web_unlocker_success(self, mock_client_cls):
        """Test successful Web Unlocker POST /request."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "<html><body><h1>Live Target Webpage</h1></body></html>"

        mock_client = MagicMock()
        mock_client.__enter__.return_value = mock_client
        mock_client.post.return_value = mock_response
        mock_client_cls.return_value = mock_client

        settings = ScraperSettings(
            brightdata_api_token="test_token_12345",
            brightdata_unlocker_zone="unlocker_test",
        )
        fetcher = DOMFetcher(settings=settings)
        html = fetcher.fetch("https://books.toscrape.com/catalogue/category/books/travel_2/index.html")

        self.assertIn("Live Target Webpage", html)
        mock_client.post.assert_called_once()
        call_args = mock_client.post.call_args
        self.assertIn("https://api.brightdata.com/request", call_args[0][0])
        self.assertEqual(call_args[1]["json"]["zone"], "unlocker_test")
        self.assertEqual(call_args[1]["json"]["format"], "raw")

    @patch("backend.scraper.dom_fetcher.httpx.Client")
    def test_web_unlocker_auth_error_fallback_to_direct(self, mock_client_cls):
        """Test that Web Unlocker auth error falls back cleanly to direct fetch."""
        unlocker_fail_resp = MagicMock()
        unlocker_fail_resp.status_code = 401
        unlocker_fail_resp.text = "Unauthorized"

        direct_success_resp = MagicMock()
        direct_success_resp.status_code = 200
        direct_success_resp.text = "<html><body><h1>Fallback Direct Page</h1></body></html>"
        direct_success_resp.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.__enter__.return_value = mock_client
        mock_client.post.return_value = unlocker_fail_resp
        mock_client.get.return_value = direct_success_resp
        mock_client_cls.return_value = mock_client

        settings = ScraperSettings(brightdata_api_token="invalid_token_12345")
        fetcher = DOMFetcher(settings=settings)
        html = fetcher.fetch("https://books.toscrape.com/catalogue/category/books/travel_2/index.html")

        self.assertIn("Fallback Direct Page", html)
        mock_client.get.assert_called_once()


if __name__ == "__main__":
    unittest.main()
