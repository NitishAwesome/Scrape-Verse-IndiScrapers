import os
import unittest
from backend.scraper.config import ScraperMode, ScraperSettings
from backend.scraper.service import ScraperService

class TestLiveBrightDataIntegration(unittest.TestCase):
    """
    Optional live integration test against real Bright Data Scraper Studio collector.
    
    Safe by default: Automatically skips unless RUN_LIVE_BRIGHTDATA_TESTS=true and credentials exist.
    Never exposes API tokens in assertions or logs.
    """

    @unittest.skipUnless(
        os.getenv("RUN_LIVE_BRIGHTDATA_TESTS") == "true" and os.getenv("BRIGHTDATA_API_TOKEN"),
        "Live Bright Data integration test skipped (set RUN_LIVE_BRIGHTDATA_TESTS=true to enable)",
    )
    def test_live_brightdata_scraper_execution(self):
        settings = ScraperSettings(
            scraper_mode=ScraperMode.BRIGHTDATA,
            brightdata_api_token=os.getenv("BRIGHTDATA_API_TOKEN"),
            brightdata_collector_id=os.getenv("BRIGHTDATA_COLLECTOR_ID", "c_mt3d61eq4viqmv3f4"),
            brightdata_timeout_seconds=90.0,
            target_url="https://example.com",
        )
        service = ScraperService(settings=settings)
        result = service.execute(target_url="https://example.com")
        
        # Verify structure without printing any auth details
        self.assertIsNotNone(result)
        self.assertIn(result.status.value, ["success", "failed"])
        if result.status.value == "success":
            self.assertGreater(result.records_extracted, 0)
            self.assertTrue(len(result.data) > 0)
