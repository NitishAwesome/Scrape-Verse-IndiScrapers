"""DOMFetcher service for fetching live target HTML via Bright Data Web Unlocker."""

import logging
from typing import Any

import httpx

from backend.scraper.config import ScraperSettings, get_settings
from backend.scraper.exceptions import ScraperError

logger = logging.getLogger(__name__)


def _mask_token(token: str | None) -> str:
    """Safely mask API token for logs and errors."""
    if not token or len(token) < 8:
        return "***"
    return f"{token[:4]}...{token[-4:]}"


def _sanitize_error_message(msg: str, token: str | None) -> str:
    """Ensure token never appears in error messages."""
    if token and token in msg:
        return msg.replace(token, _mask_token(token))
    return msg


class DOMFetcherError(ScraperError):
    """Raised when live HTML retrieval fails."""


class DOMFetcher:
    """
    Fetches raw HTML DOM from target websites using Bright Data Web Unlocker API.

    API Endpoint:
        POST https://api.brightdata.com/request
    Body:
        {
            "zone": "<BRIGHTDATA_UNLOCKER_ZONE>",
            "url": "<target_url>",
            "format": "raw"
        }
    """

    def __init__(self, settings: ScraperSettings | None = None) -> None:
        self.settings = settings or get_settings()

    def fetch(self, target_url: str) -> str:
        """
        Fetch raw HTML for the specified target URL.

        Attempts Bright Data Web Unlocker first; falls back to standard HTTP request
        if unlocker is unavailable or returns an error.
        """
        if not target_url or not target_url.strip():
            raise DOMFetcherError("Cannot fetch DOM: Target URL is empty.")

        token = self.settings.brightdata_api_token
        zone = self.settings.brightdata_unlocker_zone or "unlocker"
        base_url = self.settings.brightdata_api_base_url.rstrip("/")

        # If API token is configured, try Bright Data Web Unlocker
        if token and token.strip():
            try:
                html = self._fetch_via_web_unlocker(
                    target_url=target_url,
                    base_url=base_url,
                    token=token,
                    zone=zone,
                )
                if html and len(html.strip()) > 0:
                    logger.info(
                        "Successfully fetched live HTML via Bright Data Web Unlocker (%d bytes) for %s",
                        len(html),
                        target_url,
                    )
                    return html
            except Exception as exc:
                sanitized_msg = _sanitize_error_message(str(exc), token)
                logger.warning(
                    "Bright Data Web Unlocker fetch failed (%s); falling back to direct HTTP fetch for %s",
                    sanitized_msg,
                    target_url,
                )

        # Fallback: direct HTTP fetch for live public sites
        try:
            return self._fetch_direct(target_url)
        except Exception as exc:
            sanitized_msg = _sanitize_error_message(str(exc), token)
            raise DOMFetcherError(
                f"Failed to fetch live HTML for {target_url}: {sanitized_msg}"
            ) from exc

    def _fetch_via_web_unlocker(
        self, target_url: str, base_url: str, token: str, zone: str
    ) -> str:
        """Call Bright Data Web Unlocker API: POST /request."""
        endpoint = f"{base_url}/request"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
        payload = {
            "zone": zone,
            "url": target_url,
            "format": "raw",
        }

        timeout = min(self.settings.brightdata_timeout_seconds, 60.0)

        with httpx.Client(timeout=timeout) as client:
            resp = client.post(endpoint, json=payload, headers=headers)
            if resp.status_code == 401 or resp.status_code == 403:
                raise DOMFetcherError(
                    f"Bright Data Web Unlocker authentication failed (HTTP {resp.status_code})"
                )
            if resp.status_code >= 400:
                raise DOMFetcherError(
                    f"Bright Data Web Unlocker error (HTTP {resp.status_code}): {resp.text[:200]}"
                )
            return resp.text

    def _fetch_direct(self, target_url: str) -> str:
        """Direct HTTP GET with browser headers for public target sites."""
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        }
        with httpx.Client(timeout=30.0, follow_redirects=True) as client:
            resp = client.get(target_url, headers=headers)
            resp.raise_for_status()
            return resp.text
