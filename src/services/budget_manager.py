import json
import logging
import os
from datetime import datetime
from typing import Dict, List, Tuple

from src.models.asset import Asset
from src.services.google_ads import GoogleAdsApiSimulator

logger = logging.getLogger(__name__)


class BudgetManager:
    """Service for managing asset budgets based on performance."""

    def __init__(self, google_ads_api_key: str, max_retries: int = 3):
        """Initialize the budget manager service.

        Args:
            google_ads_api_key: API key for Google Ads.
            max_retries: Maximum number of retries for API calls.
        """
        self.google_ads_api = GoogleAdsApiSimulator(google_ads_api_key)
        self.max_retries = max_retries
        self.budget_changes = []

    def group_assets_by_ad(self, assets: List[Asset]) -> Dict[str, List[Asset]]:
        """Group assets by their ad_id.

        Args:
            assets: List of assets to group.

        Returns:
            Dictionary mapping ad_ids to lists of assets.
        """
        ad_assets = {}

        for asset in assets:
            if not asset.ad_id:
                continue

            if asset.ad_id not in ad_assets:
                ad_assets[asset.ad_id] = []

            ad_assets[asset.ad_id].append(asset)

        return ad_assets

    def identify_performance_outliers(self, assets: List[Asset]) -> Tuple[List[Asset], List[Asset]]:
        """Identify top and low performing assets within a group.

        Args:
            assets: List of assets to analyze.

        Returns:
            Tuple of (top_performers, low_performers).
        """
        if not assets:
            return [], []

        # Calculate performance scores for all assets
        assets_with_scores = []
        for asset in assets:
            score = asset.performance_score
            if score is not None:
                logger.debug(
                    f"Asset {asset.filename} performance metrics: "
                    f"CTR={asset.click_through_rate}, "
                    f"CVR={asset.conversion_rate}, "
                    f"Score={score}"
                )
                assets_with_scores.append((asset, score))
            else:
                logger.warning(f"Asset {asset.filename} has no performance score, skipping")

        if not assets_with_scores:
            logger.warning("No assets with performance scores found in group")
            return [], []

        # Sort by performance score
        assets_with_scores.sort(key=lambda x: x[1], reverse=True)

        # Define thresholds for top and low performers
        # For simplicity, consider the top 25% as top performers and bottom 25% as low performers
        total = len(assets_with_scores)
        top_count = max(1, total // 4)
        low_count = max(1, total // 4)

        top_performers = [asset for asset, score in assets_with_scores[:top_count]]
        low_performers = [asset for asset, score in assets_with_scores[-low_count:]]

        logger.info(
            f"Identified {len(top_performers)} top performers and "
            f"{len(low_performers)} low performers out of {total} assets"
        )

        return top_performers, low_performers

    def update_asset_budget(self, asset: Asset, adjustment_factor: float, reason: str) -> bool:
        """Update an asset's budget by a factor.

        Args:
            asset: Asset to update.
            adjustment_factor: Factor to multiply the current budget by.
            reason: Reason for the budget adjustment.

        Returns:
            True if the update was successful, False otherwise.
        """
        if not asset.ad_id or not asset.file_id:
            logger.warning(f"Asset {asset.filename} missing ad_id or file_id, cannot update budget")
            return False

        new_budget = int(asset.budget * adjustment_factor)

        for attempt in range(self.max_retries):
            try:
                response = self.google_ads_api.update_asset_budget(
                    ad_id=asset.ad_id, asset_id=asset.file_id, new_budget=new_budget
                )

                if "error" in response:
                    logger.warning(
                        f"Error updating budget for {asset.filename}, "
                        f"attempt {attempt+1}/{self.max_retries}: {response['error']}"
                    )
                    if attempt == self.max_retries - 1:
                        logger.error(f"Max retries reached for updating budget for {asset.filename}")
                        return False
                else:
                    asset.update_budget(new_budget, reason)

                    self.budget_changes.append(
                        {
                            "filename": asset.filename,
                            "ad_id": asset.ad_id,
                            "previous_budget": asset.previous_budget,
                            "new_budget": new_budget,
                            "adjustment_factor": adjustment_factor,
                            "reason": reason,
                            "timestamp": datetime.now().isoformat(),
                        }
                    )

                    logger.info(
                        f"Successfully updated budget for {asset.filename} from "
                        f"{asset.previous_budget} to {new_budget} ({reason})"
                    )
                    return True

            except Exception as e:
                logger.error(f"Error updating budget for {asset.filename}: {str(e)}")
                if attempt == self.max_retries - 1:
                    return False

        return False

    def adjust_budgets_by_performance(self, assets: List[Asset]) -> Dict:
        """Adjust budgets for assets based on their performance.

        Args:
            assets: List of assets to process.

        Returns:
            Dictionary with summary of budget adjustments.
        """
        logger.info(f"Starting budget adjustment for {len(assets)} assets")

        # Reset budget changes tracking
        self.budget_changes = []
        self.skipped_assets = []
        self.unchanged_assets = []

        # Filter assets with ad_id and performance metrics
        valid_assets = []
        for asset in assets:
            if not asset.ad_id:
                self.skipped_assets.append(
                    {
                        "filename": asset.filename,
                        "reason": "Missing ad_id",
                        "asset_id": asset.file_id,
                    }
                )
                logger.warning(f"Asset {asset.filename} has no ad_id, skipping budget adjustment")
                continue
            if asset.performance_score is None:
                self.skipped_assets.append(
                    {
                        "filename": asset.filename,
                        "reason": "Missing performance metrics",
                        "asset_id": asset.file_id,
                        "ad_id": asset.ad_id,
                    }
                )
                logger.warning(f"Asset {asset.filename} has no performance metrics, skipping budget adjustment")
                continue
            valid_assets.append(asset)

        logger.info(f"Found {len(valid_assets)} assets with valid ad_id and performance metrics")

        # Group assets by ad
        ad_assets = self.group_assets_by_ad(valid_assets)
        logger.info(f"Found {len(ad_assets)} ads with assets")

        # Process each ad's assets
        total_increased = 0
        total_decreased = 0
        total_unchanged = 0

        for ad_id, ad_assets_list in ad_assets.items():
            # Handle ads with only one asset using absolute performance thresholds
            if len(ad_assets_list) == 1:
                asset = ad_assets_list[0]
                logger.info(f"Ad {ad_id} has only one asset, using absolute performance metrics")

                # Define absolute performance thresholds
                # These thresholds can be adjusted based on business requirements
                high_performance_threshold = 0.7  # Assets with score > 0.7 get budget increase
                low_performance_threshold = 0.3  # Assets with score < 0.3 get budget decrease

                if asset.performance_score > high_performance_threshold:
                    logger.info(
                        f"Increasing budget for single high-performing asset: {asset.filename}",
                        " (score: {asset.performance_score})",
                    )
                    if self.update_asset_budget(
                        asset,
                        1.2,
                        "Single high-performing asset - budget increased by 20%",
                    ):
                        total_increased += 1
                elif asset.performance_score < low_performance_threshold:
                    logger.info(
                        f"Decreasing budget for single low-performing asset: {asset.filename}"
                        " (score: {asset.performance_score})"
                    )
                    if self.update_asset_budget(
                        asset,
                        0.8,
                        "Single low-performing asset - budget decreased by 20%",
                    ):
                        total_decreased += 1
                else:
                    self.unchanged_assets.append(
                        {
                            "filename": asset.filename,
                            "reason": "Single asset with average performance - budget unchanged",
                            "asset_id": asset.file_id,
                            "ad_id": asset.ad_id,
                            "budget": asset.budget,
                            "performance_score": asset.performance_score,
                        }
                    )
                    total_unchanged += 1
                continue

            logger.info(f"Processing ad {ad_id} with {len(ad_assets_list)} assets")

            # Identify top and low performers
            top_performers, low_performers = self.identify_performance_outliers(ad_assets_list)

            # Track middle performers
            middle_performers = [
                asset for asset in ad_assets_list if asset not in top_performers and asset not in low_performers
            ]

            # Increase budget for top performers
            for asset in top_performers:
                logger.info(f"Increasing budget for top performer: {asset.filename} (score: {asset.performance_score})")
                if self.update_asset_budget(asset, 1.2, "Top performer - budget increased by 20%"):
                    total_increased += 1

            # Decrease budget for low performers
            for asset in low_performers:
                logger.info(f"Decreasing budget for low performer: {asset.filename} (score: {asset.performance_score})")
                if self.update_asset_budget(asset, 0.8, "Low performer - budget decreased by 20%"):
                    total_decreased += 1

            # Track unchanged assets (middle performers)
            for asset in middle_performers:
                self.unchanged_assets.append(
                    {
                        "filename": asset.filename,
                        "reason": "Average performer - budget unchanged",
                        "asset_id": asset.file_id,
                        "ad_id": asset.ad_id,
                        "budget": asset.budget,
                        "performance_score": asset.performance_score,
                    }
                )

            # Count unchanged assets
            unchanged = len(middle_performers)
            total_unchanged += unchanged

        # Prepare summary
        summary = {
            "total_assets": len(assets),
            "valid_assets": len(valid_assets),
            "total_ads": len(ad_assets),
            "budgets_increased": total_increased,
            "budgets_decreased": total_decreased,
            "budgets_unchanged": total_unchanged,
            "budget_changes": self.budget_changes,
            "skipped_assets": self.skipped_assets,
            "unchanged_assets": self.unchanged_assets,
        }

        logger.info(
            f"Budget adjustment completed: {total_increased} increased,"
            f" {total_decreased} decreased, {total_unchanged} unchanged"
        )

        return summary

    def generate_budget_report(self, report_dir: str) -> str:
        """Generate a report of budget changes.

        Args:
            report_dir: Directory to save the report.

        Returns:
            Path to the generated report.
        """
        if not os.path.exists(report_dir):
            os.makedirs(report_dir)

        # Generate JSON report with all data
        json_report_path = os.path.join(report_dir, "budget_changes.json")
        full_report = {
            "changes": self.budget_changes,
            "skipped": getattr(self, "skipped_assets", []),
            "unchanged": getattr(self, "unchanged_assets", []),
        }
        with open(json_report_path, "w") as f:
            json.dump(full_report, f, indent=2)

        # Generate human-readable report
        report_path = os.path.join(report_dir, "budget_report.txt")
        with open(report_path, "w") as f:
            f.write("BUDGET ADJUSTMENT REPORT\n")
            f.write("=======================\n\n")

            # Summary section
            f.write("SUMMARY:\n")
            f.write("--------\n")
            f.write(f"Total budget changes: {len(self.budget_changes)}\n")
            f.write(f"Skipped assets: {len(getattr(self, 'skipped_assets', []))}\n")
            f.write(f"Unchanged assets: {len(getattr(self, 'unchanged_assets', []))}\n\n")

            # Budget increases section
            if self.budget_changes:
                f.write("BUDGET INCREASES:\n")
                f.write("-----------------\n")
                increases = [change for change in self.budget_changes if change["adjustment_factor"] > 1]
                if increases:
                    for change in increases:
                        f.write(f"Asset: {change['filename']}\n")
                        f.write(f"Ad ID: {change.get('ad_id', 'N/A')}\n")
                        f.write(f"Previous budget: {change['previous_budget']}\n")
                        f.write(f"New budget: {change['new_budget']}\n")
                        f.write(f"Reason: {change['reason']}\n\n")
                else:
                    f.write("No budget increases in this run.\n\n")

                # Budget decreases section
                f.write("BUDGET DECREASES:\n")
                f.write("-----------------\n")
                decreases = [change for change in self.budget_changes if change["adjustment_factor"] < 1]
                if decreases:
                    for change in decreases:
                        f.write(f"Asset: {change['filename']}\n")
                        f.write(f"Ad ID: {change.get('ad_id', 'N/A')}\n")
                        f.write(f"Previous budget: {change['previous_budget']}\n")
                        f.write(f"New budget: {change['new_budget']}\n")
                        f.write(f"Reason: {change['reason']}\n\n")
                else:
                    f.write("No budget decreases in this run.\n\n")
            else:
                f.write("No budget changes were made in this run.\n\n")

            # Unchanged assets section
            f.write("UNCHANGED ASSETS:\n")
            f.write("-----------------\n")
            unchanged = getattr(self, "unchanged_assets", [])
            if unchanged:
                for asset in unchanged:
                    f.write(f"Asset: {asset['filename']}\n")
                    f.write(f"Ad ID: {asset.get('ad_id', 'N/A')}\n")
                    f.write(f"Current budget: {asset.get('budget', 'N/A')}\n")
                    f.write(f"Performance score: {asset.get('performance_score', 'N/A')}\n")
                    f.write(f"Reason: {asset['reason']}\n\n")
            else:
                f.write("No unchanged assets in this run.\n\n")

            # Skipped assets section
            f.write("SKIPPED ASSETS:\n")
            f.write("--------------\n")
            skipped = getattr(self, "skipped_assets", [])
            if skipped:
                for asset in skipped:
                    f.write(f"Asset: {asset['filename']}\n")
                    f.write(f"Asset ID: {asset.get('asset_id', 'N/A')}\n")
                    if "ad_id" in asset:
                        f.write(f"Ad ID: {asset['ad_id']}\n")
                    f.write(f"Reason: {asset['reason']}\n\n")
            else:
                f.write("No assets were skipped in this run.\n")

        logger.info(f"Budget report generated at {report_path}")
        return report_path
