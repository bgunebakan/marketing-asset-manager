import unittest
from datetime import datetime

from src.models.asset import Asset


class TestAsset(unittest.TestCase):
    """Test cases for Asset class."""

    def setUp(self):
        """Set up test fixtures before each test method."""
        # Create a sample asset for testing
        self.asset = Asset(
            filename="US-EN | BUY123 | Summer | Youth | Seller | Image | 30s | jpg",
            country="US",
            language="EN",
            buyout_code="BUY123",
            concept="Summer",
            audience="Youth",
            transaction_side="Seller",
            asset_format="Image",
            duration="30s",
            file_format="jpg",
            file_id="file123",
            mime_type="image/jpeg",
            size_bytes=1024,
            production_date=datetime(2023, 6, 15),
            year=2023,
            month=6,
            budget=100,
            ad_id="ad123",
            clicks=500,
            impressions=10000,
            conversions=50,
            is_valid_name=True,
            is_buyout_valid=True,
            quality_score=8.5,
            is_privacy_compliant=True,
        )

    def test_init(self):
        """Test initialization of Asset."""
        self.assertEqual(self.asset.filename, "US-EN | BUY123 | Summer | Youth | Seller | Image | 30s | jpg")
        self.assertEqual(self.asset.country, "US")
        self.assertEqual(self.asset.language, "EN")
        self.assertEqual(self.asset.buyout_code, "BUY123")
        self.assertEqual(self.asset.concept, "Summer")
        self.assertEqual(self.asset.audience, "Youth")
        self.assertEqual(self.asset.transaction_side, "Seller")
        self.assertEqual(self.asset.asset_format, "Image")
        self.assertEqual(self.asset.duration, "30s")
        self.assertEqual(self.asset.file_format, "jpg")
        self.assertEqual(self.asset.file_id, "file123")
        self.assertEqual(self.asset.mime_type, "image/jpeg")
        self.assertEqual(self.asset.size_bytes, 1024)
        self.assertEqual(self.asset.production_date, datetime(2023, 6, 15))
        self.assertEqual(self.asset.year, 2023)
        self.assertEqual(self.asset.month, 6)
        self.assertEqual(self.asset.budget, 100)
        self.assertEqual(self.asset.ad_id, "ad123")
        self.assertEqual(self.asset.clicks, 500)
        self.assertEqual(self.asset.impressions, 10000)
        self.assertEqual(self.asset.conversions, 50)
        self.assertTrue(self.asset.is_valid_name)
        self.assertTrue(self.asset.is_buyout_valid)
        self.assertEqual(self.asset.quality_score, 8.5)
        self.assertTrue(self.asset.is_privacy_compliant)

    def test_is_valid_all_conditions_met(self):
        """Test is_valid property when all conditions are met."""
        self.asset.is_valid_name = True
        self.asset.is_buyout_valid = True
        self.asset.quality_score = 8.5
        self.asset.is_privacy_compliant = True
        self.assertTrue(self.asset.is_valid)

    def test_is_valid_name_invalid(self):
        """Test is_valid property when name is invalid."""
        self.asset.is_valid_name = False
        self.asset.is_buyout_valid = True
        self.asset.quality_score = 8.5
        self.asset.is_privacy_compliant = True
        self.assertFalse(self.asset.is_valid)

    def test_is_valid_buyout_invalid_but_quality_high(self):
        """Test is_valid property when buyout is invalid but quality score is high."""
        self.asset.is_valid_name = True
        self.asset.is_buyout_valid = False
        self.asset.quality_score = 8.5  # > 5, should be valid
        self.asset.is_privacy_compliant = True
        self.assertTrue(self.asset.is_valid)

    def test_is_valid_buyout_invalid_and_quality_low(self):
        """Test is_valid property when buyout is invalid and quality score is low."""
        self.asset.is_valid_name = True
        self.asset.is_buyout_valid = False
        self.asset.quality_score = 4.5  # < 5, should be invalid
        self.asset.is_privacy_compliant = True
        self.assertFalse(self.asset.is_valid)

    def test_is_valid_privacy_non_compliant(self):
        """Test is_valid property when privacy is non-compliant."""
        self.asset.is_valid_name = True
        self.asset.is_buyout_valid = True
        self.asset.quality_score = 8.5
        self.asset.is_privacy_compliant = False
        self.assertFalse(self.asset.is_valid)

    def test_is_valid_privacy_none(self):
        """Test is_valid property when privacy is None."""
        self.asset.is_valid_name = True
        self.asset.is_buyout_valid = True
        self.asset.quality_score = 8.5
        self.asset.is_privacy_compliant = None
        self.assertFalse(self.asset.is_valid)

    def test_click_through_rate_calculation(self):
        """Test click-through rate calculation."""
        self.asset.clicks = 500
        self.asset.impressions = 10000
        self.assertEqual(self.asset.click_through_rate, 0.05)  # 500 / 10000 = 0.05

    def test_click_through_rate_zero_impressions(self):
        """Test click-through rate calculation with zero impressions."""
        self.asset.clicks = 500
        self.asset.impressions = 0
        self.assertIsNone(self.asset.click_through_rate)

    def test_click_through_rate_none_clicks(self):
        """Test click-through rate calculation with None clicks."""
        self.asset.clicks = None
        self.asset.impressions = 10000
        self.assertIsNone(self.asset.click_through_rate)

    def test_conversion_rate_calculation(self):
        """Test conversion rate calculation."""
        self.asset.conversions = 50
        self.asset.clicks = 500
        self.assertEqual(self.asset.conversion_rate, 0.1)  # 50 / 500 = 0.1

    def test_conversion_rate_zero_clicks(self):
        """Test conversion rate calculation with zero clicks."""
        self.asset.conversions = 50
        self.asset.clicks = 0
        self.assertIsNone(self.asset.conversion_rate)

    def test_conversion_rate_none_conversions(self):
        """Test conversion rate calculation with None conversions."""
        self.asset.conversions = None
        self.asset.clicks = 500
        self.assertIsNone(self.asset.conversion_rate)

    def test_performance_score_calculation(self):
        """Test performance score calculation."""
        self.asset.clicks = 500
        self.asset.impressions = 10000
        self.asset.conversions = 50
        # CTR = 0.05, CVR = 0.1
        # Score = (0.05 * 0.4) + (0.1 * 0.6) = 0.02 + 0.06 = 0.08
        self.assertEqual(self.asset.performance_score, 0.08)

    def test_performance_score_missing_metrics(self):
        """Test performance score calculation with missing metrics."""
        self.asset.clicks = None
        self.asset.impressions = 10000
        self.asset.conversions = 50
        # CTR = None (defaults to 0), CVR = None (defaults to 0)
        # Score = (0 * 0.4) + (0 * 0.6) = 0
        self.assertEqual(self.asset.performance_score, 0)

    def test_update_budget(self):
        """Test updating the asset's budget."""
        initial_budget = self.asset.budget
        self.asset.update_budget(200, "Increased for better performance")

        self.assertEqual(self.asset.previous_budget, initial_budget)
        self.assertEqual(self.asset.budget, 200)
        self.assertEqual(self.asset.budget_update_reason, "Increased for better performance")
        self.assertIsNotNone(self.asset.budget_updated_at)

    def test_update_budget_multiple_times(self):
        """Test updating the asset's budget multiple times."""
        # First update
        self.asset.update_budget(200, "Increased for better performance")
        self.assertEqual(self.asset.previous_budget, 100)
        self.assertEqual(self.asset.budget, 200)

        # Second update
        self.asset.update_budget(150, "Adjusted based on performance")
        self.assertEqual(self.asset.previous_budget, 200)
        self.assertEqual(self.asset.budget, 150)
        self.assertEqual(self.asset.budget_update_reason, "Adjusted based on performance")


if __name__ == "__main__":
    unittest.main()
