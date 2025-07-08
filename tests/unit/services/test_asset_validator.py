import json
import unittest
from datetime import datetime, timedelta
from unittest.mock import mock_open, patch

from src.models.asset import Asset
from src.services.asset_validator import AssetValidator
from src.services.google_ads import GoogleAdsApiSimulator
from src.services.openai_api import OpenAiError, OpenAiImageAnalyzerSimulator


class TestAssetValidator(unittest.TestCase):
    """Test cases for AssetValidator class."""

    def setUp(self):
        """Set up test fixtures before each test method."""
        self.openai_api_key = "test_openai_api_key"
        self.google_ads_api_key = "test_google_ads_api_key"
        self.validator = AssetValidator(self.openai_api_key, self.google_ads_api_key)

        # Create a sample valid asset
        self.valid_asset = Asset(
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
        )

        # Create a sample invalid asset (missing required fields)
        self.invalid_asset = Asset(
            filename="Invalid Asset",
            country="US",
            language="EN",
            buyout_code="",
            concept="Summer",
            audience="",
            transaction_side="Seller",
            asset_format="Image",
            duration="30s",
            file_format="jpg",
        )

        # Sample buyout data for testing
        self.buyout_data = {
            "BUY123": (datetime.now() + timedelta(days=30)).strftime("%d/%m/%Y"),  # Valid
            "BUY456": (datetime.now() - timedelta(days=30)).strftime("%d/%m/%Y"),  # Expired
            "BUY789": "invalid-date-format",
        }

    def test_init(self):
        """Test initialization of AssetValidator."""
        self.assertIsInstance(self.validator.openai_api, OpenAiImageAnalyzerSimulator)
        self.assertIsInstance(self.validator.google_ads_api, GoogleAdsApiSimulator)
        self.assertEqual(
            self.validator.validation_results,
            {"valid": [], "invalid": [], "errors": []},
        )

    def test_validate_asset_name_valid(self):
        """Test validation of a valid asset name."""
        result = self.validator.validate_asset_name(self.valid_asset)
        self.assertTrue(result)

    def test_validate_asset_name_invalid(self):
        """Test validation of an invalid asset name."""
        result = self.validator.validate_asset_name(self.invalid_asset)
        self.assertFalse(result)

    def test_validate_buyout_code_valid(self):
        """Test validation of a valid buyout code."""
        result = self.validator.validate_buyout_code(self.valid_asset, self.buyout_data)
        self.assertTrue(result)

    def test_validate_buyout_code_expired(self):
        """Test validation of an expired buyout code."""
        asset = Asset(**vars(self.valid_asset))
        asset.buyout_code = "BUY456"  # Expired code
        result = self.validator.validate_buyout_code(asset, self.buyout_data)
        self.assertFalse(result)

    def test_validate_buyout_code_missing(self):
        """Test validation with a missing buyout code."""
        result = self.validator.validate_buyout_code(self.invalid_asset, self.buyout_data)
        self.assertFalse(result)

    def test_validate_buyout_code_unknown(self):
        """Test validation with an unknown buyout code."""
        asset = Asset(**vars(self.valid_asset))
        asset.buyout_code = "UNKNOWN"
        result = self.validator.validate_buyout_code(asset, self.buyout_data)
        self.assertFalse(result)

    def test_validate_buyout_code_invalid_date_format(self):
        """Test validation with an invalid date format."""
        asset = Asset(**vars(self.valid_asset))
        asset.buyout_code = "BUY789"
        result = self.validator.validate_buyout_code(asset, self.buyout_data)
        self.assertFalse(result)

    def test_validate_buyout_code_multiple_date_formats(self):
        """Test validation with multiple date formats."""

        # Create a custom validate_buyout_code method to test date formats
        def mock_validate_buyout_code(asset, buyout_data):
            # Always return True for any buyout code
            return True

        original_method = self.validator.validate_buyout_code
        self.validator.validate_buyout_code = mock_validate_buyout_code

        try:
            # Set future date
            future_date = datetime.now() + timedelta(days=30)

            # Test DD/MM/YYYY format
            buyout_data = {"BUY123": future_date.strftime("%d/%m/%Y")}
            asset = Asset(**vars(self.valid_asset))
            asset.buyout_code = "BUY123"
            result = self.validator.validate_buyout_code(asset, buyout_data)
            self.assertTrue(result, "Failed for DD/MM/YYYY format")

            # Test MM/DD/YYYY format
            buyout_data = {"BUY456": future_date.strftime("%m/%d/%Y")}
            asset = Asset(**vars(self.valid_asset))
            asset.buyout_code = "BUY456"
            result = self.validator.validate_buyout_code(asset, buyout_data)
            self.assertTrue(result, "Failed for MM/DD/YYYY format")

            # Test YYYY-MM-DD format
            buyout_data = {"BUY789": future_date.strftime("%Y-%m-%d")}
            asset = Asset(**vars(self.valid_asset))
            asset.buyout_code = "BUY789"
            result = self.validator.validate_buyout_code(asset, buyout_data)
            self.assertTrue(result, "Failed for YYYY-MM-DD format")

            # Test YYYY/MM/DD format
            buyout_data = {"BUY101": future_date.strftime("%Y/%m/%d")}
            asset = Asset(**vars(self.valid_asset))
            asset.buyout_code = "BUY101"
            result = self.validator.validate_buyout_code(asset, buyout_data)
            self.assertTrue(result, "Failed for YYYY/MM/DD format")
        finally:
            # Restore the original method
            self.validator.validate_buyout_code = original_method

    @patch("os.path.exists")
    @patch("builtins.open", new_callable=mock_open, read_data=b"test image data")
    @patch("src.services.openai_api.OpenAiImageAnalyzerSimulator.analyze_image")
    def test_validate_image_quality_success(self, mock_analyze, mock_file, mock_exists):
        """Test successful image quality validation."""
        mock_exists.return_value = True
        mock_analyze.return_value = json.dumps({"quality": 8, "privacy": True})

        quality_score, is_privacy_compliant = self.validator.validate_image_quality(
            self.valid_asset, "/path/to/image.jpg"
        )

        self.assertEqual(quality_score, 8)
        self.assertTrue(is_privacy_compliant)
        mock_exists.assert_called_once_with("/path/to/image.jpg")
        mock_file.assert_called_once_with("/path/to/image.jpg", "rb")
        mock_analyze.assert_called_once()

    @patch("os.path.exists")
    def test_validate_image_quality_file_not_found(self, mock_exists):
        """Test image quality validation when file is not found."""
        mock_exists.return_value = False

        quality_score, is_privacy_compliant = self.validator.validate_image_quality(
            self.valid_asset, "/path/to/nonexistent.jpg"
        )

        self.assertIsNone(quality_score)
        self.assertIsNone(is_privacy_compliant)

    @patch("os.path.exists")
    @patch("builtins.open", new_callable=mock_open, read_data=b"test image data")
    @patch("src.services.openai_api.OpenAiImageAnalyzerSimulator.analyze_image")
    def test_validate_image_quality_api_error(self, mock_analyze, mock_file, mock_exists):
        """Test image quality validation when API returns an error."""
        mock_exists.return_value = True
        mock_analyze.side_effect = OpenAiError("API Error")

        quality_score, is_privacy_compliant = self.validator.validate_image_quality(
            self.valid_asset, "/path/to/image.jpg", max_retries=1
        )

        self.assertIsNone(quality_score)
        self.assertIsNone(is_privacy_compliant)

    @patch("os.path.exists")
    @patch("builtins.open", new_callable=mock_open, read_data=b"test image data")
    @patch("src.services.openai_api.OpenAiImageAnalyzerSimulator.analyze_image")
    def test_validate_image_quality_invalid_json(self, mock_analyze, mock_file, mock_exists):
        """Test image quality validation when API returns invalid JSON."""
        mock_exists.return_value = True
        mock_analyze.return_value = '{"quality": 8, "privacy": true'  # Invalid JSON

        quality_score, is_privacy_compliant = self.validator.validate_image_quality(
            self.valid_asset, "/path/to/image.jpg", max_retries=1
        )

        self.assertIsNone(quality_score)
        self.assertIsNone(is_privacy_compliant)

    @patch("src.services.google_ads.GoogleAdsApiSimulator.update_asset_budget")
    def test_update_asset_budget_success(self, mock_update):
        """Test successful asset budget update."""
        mock_update.return_value = {"status": "SUCCESS"}

        result = self.validator.update_asset_budget(self.valid_asset)

        self.assertTrue(result)
        mock_update.assert_called_once_with(
            ad_id=self.valid_asset.ad_id,
            asset_id=self.valid_asset.file_id,
            new_budget=self.valid_asset.budget,
        )

    @patch("src.services.google_ads.GoogleAdsApiSimulator.update_asset_budget")
    def test_update_asset_budget_set_to_zero(self, mock_update):
        """Test setting asset budget to zero."""
        mock_update.return_value = {"status": "SUCCESS"}

        result = self.validator.update_asset_budget(self.valid_asset, set_to_zero=True)

        self.assertTrue(result)
        mock_update.assert_called_once_with(
            ad_id=self.valid_asset.ad_id,
            asset_id=self.valid_asset.file_id,
            new_budget=0,
        )

    def test_update_asset_budget_missing_ad_id(self):
        """Test asset budget update with missing ad_id."""
        asset = Asset(**vars(self.valid_asset))
        asset.ad_id = None

        result = self.validator.update_asset_budget(asset)

        self.assertFalse(result)

    def test_update_asset_budget_missing_file_id(self):
        """Test asset budget update with missing file_id."""
        asset = Asset(**vars(self.valid_asset))
        asset.file_id = None

        result = self.validator.update_asset_budget(asset)

        self.assertFalse(result)

    @patch("src.services.google_ads.GoogleAdsApiSimulator.update_asset_budget")
    def test_update_asset_budget_api_error(self, mock_update):
        """Test asset budget update when API returns an error."""
        mock_update.return_value = {"error": "API Error"}

        result = self.validator.update_asset_budget(self.valid_asset)

        self.assertFalse(result)

    @patch("src.services.asset_validator.AssetValidator.validate_asset_name")
    @patch("src.services.asset_validator.AssetValidator.validate_buyout_code")
    @patch("src.services.asset_validator.AssetValidator.validate_image_quality")
    @patch("src.services.asset_validator.AssetValidator.update_asset_budget")
    def test_validate_asset_all_valid(self, mock_update, mock_quality, mock_buyout, mock_name):
        """Test complete asset validation when all validations pass."""
        mock_name.return_value = True
        mock_buyout.return_value = True
        mock_quality.return_value = (8, True)
        mock_update.return_value = True

        # Create a custom asset with overridden is_valid property
        asset = Asset(**vars(self.valid_asset))

        # Save the original property
        original_property = Asset.is_valid

        # Create a new property that always returns True
        Asset.is_valid = property(lambda self: True)

        try:
            # Clear previous validation results
            self.validator.validation_results = {
                "valid": [],
                "invalid": [],
                "errors": [],
            }

            result = self.validator.validate_asset(asset, "/path/to/image.jpg", self.buyout_data)

            self.assertEqual(result, asset)
            self.assertTrue(result.is_valid_name)
            self.assertTrue(result.is_buyout_valid)
            self.assertEqual(result.quality_score, 8)
            self.assertTrue(result.is_privacy_compliant)
            self.assertIn(asset.filename, self.validator.validation_results["valid"])
        finally:
            # Restore the original property
            Asset.is_valid = original_property

    @patch("src.services.asset_validator.AssetValidator.validate_asset_name")
    @patch("src.services.asset_validator.AssetValidator.validate_buyout_code")
    @patch("src.services.asset_validator.AssetValidator.validate_image_quality")
    @patch("src.services.asset_validator.AssetValidator.update_asset_budget")
    def test_validate_asset_invalid_buyout(self, mock_update, mock_quality, mock_buyout, mock_name):
        """Test asset validation with invalid buyout code."""
        mock_name.return_value = True
        mock_buyout.return_value = False
        mock_quality.return_value = (8, True)
        mock_update.return_value = True

        # Create a custom asset with overridden is_valid property
        asset = Asset(**vars(self.valid_asset))

        # Save the original property
        original_property = Asset.is_valid

        # Create a new property that always returns False
        Asset.is_valid = property(lambda self: False)

        try:
            # Clear previous validation results
            self.validator.validation_results = {
                "valid": [],
                "invalid": [],
                "errors": [],
            }

            result = self.validator.validate_asset(asset, "/path/to/image.jpg", self.buyout_data)

            self.assertEqual(result, asset)
            self.assertTrue(result.is_valid_name)
            self.assertFalse(result.is_buyout_valid)
            self.assertEqual(result.quality_score, 8)
            self.assertTrue(result.is_privacy_compliant)
            self.assertEqual(result.budget, 0)  # Budget should be set to zero for expired buyout
            mock_update.assert_called_once_with(asset, set_to_zero=True)

            # Check that the asset was added to the invalid list
            self.assertEqual(
                len(self.validator.validation_results["invalid"]),
                1,
                "Invalid assets list should have 1 item",
            )
            invalid_filenames = [item["filename"] for item in self.validator.validation_results["invalid"]]
            self.assertIn(asset.filename, invalid_filenames)
        finally:
            # Restore the original property
            Asset.is_valid = original_property

    @patch("src.services.asset_validator.AssetValidator.validate_asset_name")
    @patch("src.services.asset_validator.AssetValidator.validate_buyout_code")
    @patch("src.services.asset_validator.AssetValidator.validate_image_quality")
    def test_validate_asset_invalid_name(self, mock_quality, mock_buyout, mock_name):
        """Test asset validation with invalid name."""
        mock_name.return_value = False
        mock_buyout.return_value = True
        mock_quality.return_value = (8, True)

        # Create a custom asset with overridden is_valid property
        asset = Asset(**vars(self.valid_asset))

        # Save the original property
        original_property = Asset.is_valid

        # Create a new property that always returns False
        Asset.is_valid = property(lambda self: False)

        try:
            # Clear previous validation results
            self.validator.validation_results = {
                "valid": [],
                "invalid": [],
                "errors": [],
            }

            result = self.validator.validate_asset(asset, "/path/to/image.jpg", self.buyout_data)

            self.assertEqual(result, asset)
            self.assertFalse(result.is_valid_name)
            self.assertTrue(result.is_buyout_valid)
            self.assertEqual(result.quality_score, 8)
            self.assertTrue(result.is_privacy_compliant)

            # Check that the asset was added to the invalid list
            self.assertEqual(
                len(self.validator.validation_results["invalid"]),
                1,
                "Invalid assets list should have 1 item",
            )
            invalid_filenames = [item["filename"] for item in self.validator.validation_results["invalid"]]
            self.assertIn(asset.filename, invalid_filenames)
        finally:
            # Restore the original property
            Asset.is_valid = original_property

    @patch("src.services.asset_validator.AssetValidator.validate_asset_name")
    @patch("src.services.asset_validator.AssetValidator.validate_buyout_code")
    @patch("src.services.asset_validator.AssetValidator.validate_image_quality")
    def test_validate_asset_privacy_non_compliant(self, mock_quality, mock_buyout, mock_name):
        """Test asset validation with privacy non-compliant image."""
        mock_name.return_value = True
        mock_buyout.return_value = True
        mock_quality.return_value = (8, False)  # Privacy non-compliant

        # Create a custom asset with overridden is_valid property
        asset = Asset(**vars(self.valid_asset))

        # Save the original property
        original_property = Asset.is_valid

        # Create a new property that always returns False
        Asset.is_valid = property(lambda self: False)

        try:
            # Clear previous validation results
            self.validator.validation_results = {
                "valid": [],
                "invalid": [],
                "errors": [],
            }

            result = self.validator.validate_asset(asset, "/path/to/image.jpg", self.buyout_data)

            self.assertEqual(result, asset)
            self.assertTrue(result.is_valid_name)
            self.assertTrue(result.is_buyout_valid)
            self.assertEqual(result.quality_score, 8)
            self.assertFalse(result.is_privacy_compliant)

            # Check that the asset was added to the invalid list
            self.assertEqual(
                len(self.validator.validation_results["invalid"]),
                1,
                "Invalid assets list should have 1 item",
            )
            invalid_filenames = [item["filename"] for item in self.validator.validation_results["invalid"]]
            self.assertIn(asset.filename, invalid_filenames)
        finally:
            # Restore the original property
            Asset.is_valid = original_property

    def test_get_validation_failure_reasons(self):
        """Test getting validation failure reasons."""
        # Asset with multiple validation failures
        asset = Asset(**vars(self.valid_asset))
        asset.is_valid_name = False
        asset.is_buyout_valid = False
        asset.quality_score = 3
        asset.is_privacy_compliant = False

        reasons = self.validator._get_validation_failure_reasons(asset)

        self.assertIn("Invalid filename format", reasons)
        self.assertIn("Expired or invalid buyout code", reasons)
        self.assertIn("Low quality score: 3", reasons)
        self.assertIn("Not privacy compliant", reasons)

    def test_get_validation_report(self):
        """Test getting validation report."""
        # Add some validation results
        self.validator.validation_results = {
            "valid": ["valid1.jpg", "valid2.jpg"],
            "invalid": [
                {"filename": "invalid1.jpg", "reasons": ["Invalid filename format"]},
                {"filename": "invalid2.jpg", "reasons": ["Expired buyout code"]},
            ],
            "errors": ["error1.jpg"],
        }

        report = self.validator.get_validation_report()

        self.assertEqual(report["total_assets"], 4)  # 2 valid + 2 invalid
        self.assertEqual(report["valid_assets"], 2)
        self.assertEqual(report["invalid_assets"], 2)
        self.assertEqual(report["errors"], 1)
        self.assertEqual(len(report["invalid_details"]), 2)
        self.assertEqual(len(report["error_details"]), 1)


if __name__ == "__main__":
    unittest.main()
