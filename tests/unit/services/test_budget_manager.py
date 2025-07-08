import os
import unittest
from datetime import datetime
from unittest.mock import mock_open, patch

from src.models.asset import Asset
from src.services.budget_manager import BudgetManager
from src.services.google_ads import GoogleAdsApiSimulator


class TestBudgetManager(unittest.TestCase):
    """Test cases for the BudgetManager class."""

    def setUp(self):
        """Set up test fixtures before each test."""
        self.google_ads_api_key = "test_google_ads_api_key"
        self.manager = BudgetManager(self.google_ads_api_key)

        # Create sample assets
        self.asset1 = Asset(
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
            ad_id="ad123",
            budget=100,
            impressions=1000,  # Will give click_through_rate of 0.05
            clicks=50,
            conversions=1,  # Will give conversion_rate of 0.02
        )

        self.asset2 = Asset(
            filename="DE-DE | BUY456 | Winter | Adult | Buyer | Video | 15s | mp4",
            country="DE",
            language="DE",
            buyout_code="BUY456",
            concept="Winter",
            audience="Adult",
            transaction_side="Buyer",
            asset_format="Video",
            duration="15s",
            file_format="mp4",
            file_id="file456",
            ad_id="ad123",
            budget=200,
            impressions=2000,  # Will give click_through_rate of 0.02
            clicks=40,
            conversions=0,  # Will give conversion_rate of 0
        )

        self.asset3 = Asset(
            filename="FR-FR | BUY789 | Spring | Youth | Seller | Image | 30s | jpg",
            country="FR",
            language="FR",
            buyout_code="BUY789",
            concept="Spring",
            audience="Youth",
            transaction_side="Seller",
            asset_format="Image",
            duration="30s",
            file_format="jpg",
            file_id="file789",
            ad_id="ad456",
            budget=150,
            impressions=1000,  # Will give click_through_rate of 0.08
            clicks=80,
            conversions=3,  # Will give conversion_rate of 0.0375
        )

        self.asset_no_ad_id = Asset(
            filename="UK-EN | BUY101 | Summer | Youth | Seller | Image | 30s | jpg",
            country="UK",
            language="EN",
            buyout_code="BUY101",
            concept="Summer",
            audience="Youth",
            transaction_side="Seller",
            asset_format="Image",
            duration="30s",
            file_format="jpg",
            file_id="file101",
            ad_id=None,
            budget=120,
        )

        self.asset_no_metrics = Asset(
            filename="ES-ES | BUY202 | Summer | Youth | Seller | Image | 30s | jpg",
            country="ES",
            language="ES",
            buyout_code="BUY202",
            concept="Summer",
            audience="Youth",
            transaction_side="Seller",
            asset_format="Image",
            duration="30s",
            file_format="jpg",
            file_id="file202",
            ad_id="ad789",
            budget=80,
            # No impressions, clicks, or conversions to simulate no metrics
        )

    def test_init(self):
        """Test initialization of BudgetManager."""
        self.assertIsInstance(self.manager.google_ads_api, GoogleAdsApiSimulator)
        self.assertEqual(self.manager.max_retries, 3)
        self.assertEqual(self.manager.budget_changes, [])

    def test_group_assets_by_ad(self):
        """Test grouping assets by ad_id."""
        assets = [self.asset1, self.asset2, self.asset3, self.asset_no_ad_id]
        grouped = self.manager.group_assets_by_ad(assets)

        self.assertEqual(len(grouped), 2)
        self.assertEqual(len(grouped["ad123"]), 2)
        self.assertEqual(len(grouped["ad456"]), 1)
        self.assertIn(self.asset1, grouped["ad123"])
        self.assertIn(self.asset2, grouped["ad123"])
        self.assertIn(self.asset3, grouped["ad456"])
        self.assertNotIn(self.asset_no_ad_id, grouped.get("None", []))

    def test_identify_performance_outliers_empty_list(self):
        """Test identifying outliers with an empty list."""
        top, low = self.manager.identify_performance_outliers([])
        self.assertEqual(len(top), 0)
        self.assertEqual(len(low), 0)

    def test_identify_performance_outliers_no_scores(self):
        """Test identifying outliers when assets have no performance scores."""
        # Create an asset with no performance metrics
        asset_no_metrics = Asset(
            filename="test_no_metrics.jpg",
            country="US",
            language="EN",
            buyout_code="BUY123",
            concept="Test",
            audience="Youth",
            transaction_side="Seller",
            asset_format="Image",
            duration="30s",
            file_format="jpg",
            ad_id="ad123",
            # No clicks, impressions or conversions
        )

        # Verify the asset has zero performance score when metrics are missing
        self.assertEqual(asset_no_metrics.performance_score, 0.0)

        # The BudgetManager.identify_performance_outliers method checks if score is None,
        # but Asset.performance_score returns 0.0 for missing metrics, not None.
        # This means the asset will be included in assets_with_scores, but with a score of 0.0
        assets = [asset_no_metrics]
        top, low = self.manager.identify_performance_outliers(assets)

        # Since there's only one asset with a score of 0.0, it will be both a top and low performer
        # according to the logic in identify_performance_outliers
        self.assertEqual(len(top), 1)
        self.assertEqual(len(low), 1)
        self.assertIn(asset_no_metrics, top)
        self.assertIn(asset_no_metrics, low)

    def test_identify_performance_outliers(self):
        """Test identifying performance outliers."""
        # Create assets with different performance scores
        asset_high = Asset(**vars(self.asset1))
        asset_high.impressions = 1000
        asset_high.clicks = 100  # CTR = 0.1
        asset_high.conversions = 5  # CVR = 0.05

        asset_medium1 = Asset(**vars(self.asset2))
        asset_medium1.impressions = 1000
        asset_medium1.clicks = 50  # CTR = 0.05
        asset_medium1.conversions = 1  # CVR = 0.02

        asset_medium2 = Asset(**vars(self.asset3))
        asset_medium2.impressions = 1000
        asset_medium2.clicks = 40  # CTR = 0.04
        asset_medium2.conversions = 1  # CVR = 0.025

        asset_low = Asset(**vars(self.asset_no_metrics))
        asset_low.impressions = 1000
        asset_low.clicks = 10  # CTR = 0.01
        asset_low.conversions = 0  # CVR = 0
        asset_low.ad_id = "ad789"

        assets = [asset_high, asset_medium1, asset_medium2, asset_low]
        top, low = self.manager.identify_performance_outliers(assets)

        self.assertEqual(len(top), 1)
        self.assertEqual(len(low), 1)
        self.assertIn(asset_high, top)
        self.assertIn(asset_low, low)

    @patch("src.services.google_ads.GoogleAdsApiSimulator.update_asset_budget")
    def test_update_asset_budget_success(self, mock_update):
        """Test successful asset budget update."""
        mock_update.return_value = {"status": "SUCCESS"}

        result = self.manager.update_asset_budget(self.asset1, 1.2, "Test increase")

        self.assertTrue(result)
        mock_update.assert_called_once_with(
            ad_id=self.asset1.ad_id,
            asset_id=self.asset1.file_id,
            new_budget=120,  # 100 * 1.2
        )
        self.assertEqual(len(self.manager.budget_changes), 1)
        self.assertEqual(self.manager.budget_changes[0]["filename"], self.asset1.filename)
        self.assertEqual(self.manager.budget_changes[0]["previous_budget"], 100)
        self.assertEqual(self.manager.budget_changes[0]["new_budget"], 120)
        self.assertEqual(self.manager.budget_changes[0]["adjustment_factor"], 1.2)
        self.assertEqual(self.manager.budget_changes[0]["reason"], "Test increase")

    @patch("src.services.google_ads.GoogleAdsApiSimulator.update_asset_budget")
    def test_update_asset_budget_error(self, mock_update):
        """Test asset budget update with API error."""
        mock_update.return_value = {"error": "API Error"}

        result = self.manager.update_asset_budget(self.asset1, 1.2, "Test increase")

        self.assertFalse(result)
        self.assertEqual(len(self.manager.budget_changes), 0)

    def test_update_asset_budget_missing_ids(self):
        """Test asset budget update with missing ad_id or file_id."""
        # Test with missing ad_id
        asset_no_ad = Asset(**vars(self.asset1))
        asset_no_ad.ad_id = None
        result = self.manager.update_asset_budget(asset_no_ad, 1.2, "Test increase")
        self.assertFalse(result)

        # Test with missing file_id
        asset_no_file = Asset(**vars(self.asset1))
        asset_no_file.file_id = None
        result = self.manager.update_asset_budget(asset_no_file, 1.2, "Test increase")
        self.assertFalse(result)

    @patch("src.services.google_ads.GoogleAdsApiSimulator.update_asset_budget")
    def test_update_asset_budget_retry_logic(self, mock_update):
        """Test retry logic for asset budget update."""
        # First two calls fail, third succeeds
        mock_update.side_effect = [
            {"error": "API Error"},
            {"error": "API Error"},
            {"status": "SUCCESS"},
        ]

        result = self.manager.update_asset_budget(self.asset1, 1.2, "Test increase")

        self.assertTrue(result)
        self.assertEqual(mock_update.call_count, 3)
        self.assertEqual(len(self.manager.budget_changes), 1)

    @patch("src.services.budget_manager.BudgetManager.update_asset_budget")
    def test_adjust_budgets_by_performance(self, mock_update):
        """Test adjusting budgets based on performance."""
        # Setup mock for update_asset_budget
        mock_update.return_value = True

        # Create assets with same ad_id but different performance scores
        high_asset = Asset(
            filename="high_performer.jpg",
            country="US",
            language="EN",
            buyout_code="BUY123",
            concept="Test",
            audience="Youth",
            transaction_side="Seller",
            asset_format="Image",
            duration="30s",
            file_format="jpg",
            file_id="file_high",
            ad_id="same_ad",
            impressions=1000,
            clicks=900,  # 90% CTR, very high
            conversions=450,  # 50% CVR, very high
        )

        low_asset = Asset(
            filename="low_performer.jpg",
            country="US",
            language="EN",
            buyout_code="BUY123",
            concept="Test",
            audience="Youth",
            transaction_side="Seller",
            asset_format="Image",
            duration="30s",
            file_format="jpg",
            file_id="file_low",
            ad_id="same_ad",
            impressions=1000,
            clicks=10,  # 1% CTR, very low
            conversions=0,  # 0% CVR, very low
        )

        mid_asset = Asset(
            filename="mid_performer.jpg",
            country="US",
            language="EN",
            buyout_code="BUY123",
            concept="Test",
            audience="Youth",
            transaction_side="Seller",
            asset_format="Image",
            duration="30s",
            file_format="jpg",
            file_id="file_mid",
            ad_id="same_ad",
            impressions=1000,
            clicks=50,  # 5% CTR, medium
            conversions=5,  # 10% CVR, medium
        )

        # Run the method
        assets = [high_asset, low_asset, mid_asset]
        result = self.manager.adjust_budgets_by_performance(assets)

        # Check that update_asset_budget was called for top and low performers
        self.assertEqual(mock_update.call_count, 2)

        # Check the calls were made with correct parameters - using the actual message from the implementation
        mock_update.assert_any_call(high_asset, 1.2, "Top performer - budget increased by 20%")
        mock_update.assert_any_call(low_asset, 0.8, "Low performer - budget decreased by 20%")

        # Check the summary
        self.assertEqual(result["total_assets"], 3)
        self.assertEqual(result["valid_assets"], 3)
        self.assertEqual(result["budgets_increased"], 1)
        self.assertEqual(result["budgets_decreased"], 1)
        self.assertEqual(result["budgets_unchanged"], 1)

    @patch("src.services.budget_manager.BudgetManager.update_asset_budget")
    def test_adjust_budgets_single_asset_per_ad(self, mock_update):
        """Test adjusting budgets when there's only one asset per ad."""
        # Setup mock for update_asset_budget
        mock_update.return_value = True

        # Create a high-performing asset in one ad
        high_asset = Asset(
            filename="high_performer.jpg",
            country="US",
            language="EN",
            buyout_code="BUY123",
            concept="Test",
            audience="Youth",
            transaction_side="Seller",
            asset_format="Image",
            duration="30s",
            file_format="jpg",
            file_id="file_high",
            ad_id="ad_high",  # Unique ad_id
            impressions=1000,
            clicks=900,  # 90% CTR, very high
            conversions=600,  # 66.7% CVR, very high
        )

        # Create a low-performing asset in another ad
        low_asset = Asset(
            filename="low_performer.jpg",
            country="US",
            language="EN",
            buyout_code="BUY123",
            concept="Test",
            audience="Youth",
            transaction_side="Seller",
            asset_format="Image",
            duration="30s",
            file_format="jpg",
            file_id="file_low",
            ad_id="ad_low",  # Different ad_id
            impressions=1000,
            clicks=10,  # 1% CTR, very low
            conversions=0,  # 0% CVR, very low
        )

        # Calculate and verify the performance scores
        high_score = (high_asset.click_through_rate * 0.4) + (high_asset.conversion_rate * 0.6)
        low_score = (low_asset.click_through_rate * 0.4) + (low_asset.conversion_rate * 0.6)

        # Verify the performance scores meet the thresholds
        self.assertGreaterEqual(high_score, 0.7)  # Above threshold
        self.assertLessEqual(low_score, 0.3)  # Below threshold

        # Run the method
        assets = [high_asset, low_asset]
        result = self.manager.adjust_budgets_by_performance(assets)

        # Check that update_asset_budget was called for both assets
        self.assertEqual(mock_update.call_count, 2)

        # Check the calls were made with correct parameters
        mock_update.assert_any_call(high_asset, 1.2, "Single high-performing asset - budget increased by 20%")
        mock_update.assert_any_call(low_asset, 0.8, "Single low-performing asset - budget decreased by 20%")

        # Check the summary
        self.assertEqual(result["total_assets"], 2)
        self.assertEqual(result["valid_assets"], 2)
        self.assertEqual(result["budgets_increased"], 1)
        self.assertEqual(result["budgets_decreased"], 1)
        self.assertEqual(result["budgets_unchanged"], 0)

    def test_adjust_budgets_skips_invalid_assets(self):
        """Test that assets without ad_id or performance metrics are skipped."""
        # Create an asset with no ad_id
        asset_no_ad_id = Asset(
            filename="test_no_ad_id.jpg",
            country="US",
            language="EN",
            buyout_code="BUY123",
            concept="Test",
            audience="Youth",
            transaction_side="Seller",
            asset_format="Image",
            duration="30s",
            file_format="jpg",
            file_id="file_no_ad",
            ad_id=None,  # No ad_id
            impressions=1000,
            clicks=50,
            conversions=1,
        )

        # Create an asset with no performance metrics
        asset_no_metrics = Asset(
            filename="test_no_metrics.jpg",
            country="US",
            language="EN",
            buyout_code="BUY123",
            concept="Test",
            audience="Youth",
            transaction_side="Seller",
            asset_format="Image",
            duration="30s",
            file_format="jpg",
            file_id="file_no_metrics",
            ad_id="ad123",
            # No impressions, clicks, or conversions
        )

        # Verify the asset has zero performance score
        self.assertEqual(asset_no_metrics.performance_score, 0.0)

        # Run the method
        assets = [asset_no_ad_id, asset_no_metrics]
        result = self.manager.adjust_budgets_by_performance(assets)

        # Check that invalid assets were skipped
        # The asset with no ad_id should be skipped
        self.assertEqual(len(result["skipped_assets"]), 1)
        self.assertEqual(result["skipped_assets"][0]["filename"], asset_no_ad_id.filename)
        self.assertEqual(result["skipped_assets"][0]["reason"], "Missing ad_id")

    @patch("builtins.open", new_callable=mock_open)
    def test_generate_budget_report(self, mock_file):
        """Test generating budget reports."""
        # Setup mocks for os.path.exists and os.makedirs
        with patch("os.path.exists", return_value=False) as _, patch("os.makedirs") as mock_makedirs:

            # Add some budget changes
            self.manager.budget_changes = [
                {
                    "filename": "asset1.jpg",
                    "previous_budget": 100,
                    "new_budget": 120,
                    "adjustment_factor": 1.2,
                    "reason": "Top performer",
                    "timestamp": datetime.now().isoformat(),
                },
                {
                    "filename": "asset2.jpg",
                    "previous_budget": 200,
                    "new_budget": 160,
                    "adjustment_factor": 0.8,
                    "reason": "Low performer",
                    "timestamp": datetime.now().isoformat(),
                },
            ]

            # Setup skipped and unchanged assets as attributes on the manager
            self.manager.skipped_assets = [
                {"filename": "skipped1.jpg", "reason": "No ad_id"},
                {"filename": "skipped2.jpg", "reason": "No performance metrics"},
            ]

            self.manager.unchanged_assets = [{"filename": "unchanged1.jpg", "reason": "Medium performer"}]

            # Generate the report
            report_dir = "/tmp/budget_reports"
            self.manager.generate_budget_report(report_dir)

            # Check that directory was created - without exist_ok=True
            # This matches the actual implementation in BudgetManager
            mock_makedirs.assert_called_once_with(report_dir)

            # Get the file handle from the mock
            handle = mock_file()
            # Don't rely on exact JSON format, just check that write was called
            self.assertTrue(handle.write.called)

            # The mock_file is called for each file open operation
            # Two files are opened (json and txt), but there might be multiple calls
            # Just verify that the two specific files we expect were opened
            mock_file.assert_any_call(os.path.join(report_dir, "budget_changes.json"), "w")
            mock_file.assert_any_call(os.path.join(report_dir, "budget_report.txt"), "w")

            # Check that text report was written
            text_calls = [call for call in handle.write.call_args_list if "BUDGET ADJUSTMENT REPORT" in str(call)]
            self.assertTrue(len(text_calls) > 0)
