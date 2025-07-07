import json
import logging
import os
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from src.models.asset import Asset
from src.services.google_ads import GoogleAdsApiSimulator
from src.services.openai_api import OpenAiError, OpenAiImageAnalyzerSimulator

logger = logging.getLogger(__name__)


class AssetValidator:
    """Service for validating marketing assets."""

    def __init__(self, openai_api_key: str, google_ads_api_key: str):
        """Initialize the asset validator service.

        Args:
            openai_api_key: API key for OpenAI.
            google_ads_api_key: API key for Google Ads.
        """

        self.openai_api = OpenAiImageAnalyzerSimulator(openai_api_key)
        self.google_ads_api = GoogleAdsApiSimulator(google_ads_api_key)
        self.validation_results = {"valid": [], "invalid": [], "errors": []}

    def validate_asset_name(self, asset: Asset) -> bool:
        """Validate the asset name format.

        Expected format: {country-language} | {buyout-code} | {concept} |
        {audience} | {transaction_side} | {asset_format} | {duration} | {file_format} # {buyout_code}

        Args:
            asset: Asset to validate.

        Returns:
            True if the asset name is valid, False otherwise.
        """
        required_fields = [
            "country",
            "language",
            "buyout_code",
            "concept",
            "audience",
            "transaction_side",
            "asset_format",
            "duration",
        ]

        for field in required_fields:
            if not getattr(asset, field, None):
                logger.warning(f"Asset {asset.filename} missing required field: {field}")
                return False

        logger.info(f"Asset {asset.filename} name validation passed")
        return True

    def validate_buyout_code(self, asset: Asset, buyout_data: Dict[str, str]) -> bool:
        """Validate if the asset's buyout code is valid (not expired).

        Args:
            asset: Asset to validate.
            buyout_data: Dictionary mapping buyout codes to expiration dates.

        Returns:
            True if the buyout code is valid, False otherwise.
        """
        buyout_code = asset.buyout_code

        if not buyout_code:
            logger.warning(f"Asset {asset.filename} has no buyout code")
            return False

        if buyout_code not in buyout_data:
            logger.warning(f"Asset {asset.filename} has unknown buyout code: {buyout_code}")
            return False

        expiration_date_str = buyout_data.get(buyout_code)
        if not expiration_date_str:
            logger.warning(f"Asset {asset.filename} has buyout code with no expiration date: {buyout_code}")
            return False

        try:
            # Try multiple date formats to possible inconsistencies
            date_formats = ["%d/%m/%Y", "%m/%d/%Y", "%Y-%m-%d", "%Y/%m/%d"]
            expiration_date = None

            for date_format in date_formats:
                try:
                    expiration_date = datetime.strptime(expiration_date_str, date_format)
                    logger.debug(f"Successfully parsed date {expiration_date_str} with format {date_format}")
                    break
                except ValueError:
                    continue

            if not expiration_date:
                logger.error(f"Invalid expiration date format for buyout code {buyout_code}: {expiration_date_str}")
                return False

            current_date = datetime.now()

            if current_date > expiration_date:
                logger.warning(
                    f"Asset {asset.filename} has expired buyout code: {buyout_code}, expired on {expiration_date_str}"
                )
                return False

            logger.info(f"Asset {asset.filename} buyout validation passed, valid until {expiration_date_str}")
            return True

        except Exception as e:
            logger.error(f"Error validating buyout code for {asset.filename}: {str(e)}")
            return False

    def validate_image_quality(
        self, asset: Asset, image_path: str, max_retries: int = 3
    ) -> Tuple[Optional[float], Optional[bool]]:
        """Validate the image quality using OpenAI API.

        Args:
            asset: Asset to validate.
            image_path: Path to the image file.
            max_retries: Maximum number of retries for API calls.

        Returns:
            Tuple of (quality_score, is_privacy_compliant)
        """
        if not os.path.exists(image_path):
            logger.error(f"Image file not found: {image_path}")
            return None, None

        try:
            with open(image_path, "rb") as f:
                image_bytes = f.read()

            for attempt in range(max_retries):
                try:
                    analysis_result = self.openai_api.analyze_image(image_bytes)
                    if not analysis_result:
                        logger.warning(f"Empty analysis result for {asset.filename}, attempt {attempt+1}/{max_retries}")
                        continue

                    try:
                        analysis_data = json.loads(analysis_result)
                        quality_score = analysis_data.get("quality")
                        is_privacy_compliant = analysis_data.get("privacy", False)

                        logger.info(
                            f"Asset {asset.filename} quality validation: score={quality_score},"
                            " privacy_compliant={is_privacy_compliant}"
                        )
                        return quality_score, is_privacy_compliant

                    except json.JSONDecodeError:
                        logger.error(f"Invalid JSON response from OpenAI API for {asset.filename}: {analysis_result}")
                        continue

                except OpenAiError as e:
                    logger.warning(
                        f"OpenAI API error for {asset.filename}, attempt {attempt+1}/{max_retries}: {str(e)}"
                    )
                    if attempt == max_retries - 1:
                        logger.error(f"Max retries reached for OpenAI API call for {asset.filename}")
                        return None, None

        except Exception as e:
            logger.error(f"Error validating image quality for {asset.filename}: {str(e)}")
            return None, None

        return None, None

    def update_asset_budget(self, asset: Asset, set_to_zero: bool = False) -> bool:
        """Update the asset budget in Google Ads.

        Args:
            asset: Asset to update.
            set_to_zero: If True, set the budget to zero regardless of current value.

        Returns:
            True if the update was successful, False otherwise.
        """
        if not asset.ad_id:
            logger.warning(f"Asset {asset.filename} has no ad_id, cannot update budget")
            return False

        if not asset.file_id:
            logger.warning(f"Asset {asset.filename} has no file_id, cannot update budget")
            return False

        new_budget = 0 if set_to_zero else asset.budget

        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = self.google_ads_api.update_asset_budget(
                    ad_id=asset.ad_id, asset_id=asset.file_id, new_budget=new_budget
                )

                if "error" in response:
                    logger.warning(
                        f"Error updating budget for {asset.filename}, "
                        f"attempt {attempt+1}/{max_retries}: {response['error']}"
                    )
                    if attempt == max_retries - 1:
                        logger.error(f"Max retries reached for updating budget for {asset.filename}")
                        return False
                else:
                    logger.info(f"Successfully updated budget for {asset.filename} to {new_budget}")
                    return True

            except Exception as e:
                logger.error(f"Error updating budget for {asset.filename}: {str(e)}")
                if attempt == max_retries - 1:
                    return False

        return False

    def validate_asset(self, asset: Asset, image_path: str, buyout_data: Dict[str, str]) -> Asset:
        """Run the complete validation pipeline for an asset.

        Args:
            asset: Asset to validate.
            image_path: Path to the image file.
            buyout_data: Dictionary mapping buyout codes to expiration dates.

        Returns:
            Updated asset with validation results.
        """
        logger.info(f"Starting validation for asset: {asset.filename}")

        # Step 1: Validate asset name
        asset.is_valid_name = self.validate_asset_name(asset)

        # Step 2: Validate buyout code
        asset.is_buyout_valid = self.validate_buyout_code(asset, buyout_data)

        # Step 3: Validate image quality
        quality_score, is_privacy_compliant = self.validate_image_quality(asset, image_path)
        asset.quality_score = quality_score
        asset.is_privacy_compliant = is_privacy_compliant

        # Step 4: Update budget if buyout is expired
        if not asset.is_buyout_valid:
            logger.info(f"Setting budget to zero for asset with expired buyout: {asset.filename}")
            self.update_asset_budget(asset, set_to_zero=True)
            asset.budget = 0

        # Report validation results
        if asset.is_valid:
            self.validation_results["valid"].append(asset.filename)
        else:
            self.validation_results["invalid"].append(
                {
                    "filename": asset.filename,
                    "reasons": self._get_validation_failure_reasons(asset),
                }
            )

        return asset

    def _get_validation_failure_reasons(self, asset: Asset) -> List[str]:
        """Get the reasons why an asset failed validation.

        Args:
            asset: Asset that failed validation.

        Returns:
            List of failure reasons.
        """
        reasons = []

        if not asset.is_valid_name:
            reasons.append("Invalid filename format")

        if not asset.is_buyout_valid:
            reasons.append("Expired or invalid buyout code")

        if asset.quality_score is None:
            reasons.append("Quality check failed")
        elif asset.quality_score <= 5:
            reasons.append(f"Low quality score: {asset.quality_score}")

        if asset.is_privacy_compliant is None:
            reasons.append("Privacy compliance check failed")
        elif not asset.is_privacy_compliant:
            reasons.append("Not privacy compliant")

        return reasons

    def get_validation_report(self) -> Dict:
        """Get a report of the validation results.

        Returns:
            Dictionary with validation statistics.
        """
        return {
            "total_assets": len(self.validation_results["valid"]) + len(self.validation_results["invalid"]),
            "valid_assets": len(self.validation_results["valid"]),
            "invalid_assets": len(self.validation_results["invalid"]),
            "errors": len(self.validation_results["errors"]),
            "invalid_details": self.validation_results["invalid"],
            "error_details": self.validation_results["errors"],
        }
