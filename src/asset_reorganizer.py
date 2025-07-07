import json
import logging
import os
from typing import Dict, List, Optional

from dotenv import load_dotenv

from src.services.asset_validator import AssetValidator
from src.services.budget_manager import BudgetManager
from src.services.google_drive import GoogleDriveService
from src.services.google_sheets import GoogleSheetsService
from src.utils.asset_parser import AssetParser

load_dotenv()

logger = logging.getLogger(__name__)


class AssetReorganizer:
    """Asset reorganizer for Marketing Asset Manager."""

    def __init__(
        self,
        credentials_file: str,
        spreadsheet_id: str,
        source_folder_id: str,
        target_folder_id: str,
        shared_drive_id: Optional[str] = None,
        openai_api_key: Optional[str] = None,
        google_ads_api_key: Optional[str] = None,
    ):
        """Initialize the asset reorganizer.

        Args:
            credentials_file: Path to the Google API credentials file.
            spreadsheet_id: ID of the Google Sheets spreadsheet.
            source_folder_id: ID of the source folder in Google Drive.
            target_folder_id: ID of the target folder in Google Drive.
            shared_drive_id: Optional ID of the shared drive to use.
            openai_api_key: Optional API key for OpenAI.
            google_ads_api_key: Optional API key for Google Ads.
        """
        self.shared_drive_id = shared_drive_id
        self.drive_service = GoogleDriveService(credentials_file, shared_drive_id)
        self.sheets_service = GoogleSheetsService(credentials_file, spreadsheet_id)
        self.asset_parser = AssetParser()
        self.source_folder_id = source_folder_id
        self.target_folder_id = target_folder_id
        self.tmp_dir = "tmp/"
        self.assets_dir = self.tmp_dir + "assets/"
        self.processed_dir = self.tmp_dir + "processed_assets/"
        self.reports_dir = self.tmp_dir + "reports/"

        # Create temporary directories if they don't exist
        for directory in [
            self.tmp_dir,
            self.assets_dir,
            self.processed_dir,
            self.reports_dir,
        ]:
            if not os.path.exists(directory):
                os.makedirs(directory)
                logger.info(f"Created directory: {directory}")

        # Initialize services if API keys are provided
        self.asset_validator = None
        self.budget_manager = None
        if openai_api_key and google_ads_api_key:
            self.asset_validator = AssetValidator(openai_api_key, google_ads_api_key)
            self.budget_manager = BudgetManager(google_ads_api_key)
            logger.info("Asset validator and budget manager initialized")

    def run(self) -> None:
        logger.info("Starting asset reorganization")

        ui_settings = self.sheets_service.get_ui_settings()
        hierarchy_settings = ui_settings.get("hierarchy_settings")

        if not hierarchy_settings or not hierarchy_settings.levels:
            logger.error("No hierarchy levels defined in UI settings")
            return

        logger.info(f"Hierarchy levels: {[level.field for level in hierarchy_settings.get_sorted_levels()]}")

        asset_data = self.sheets_service.get_asset_data()
        logger.info(f"Found {len(asset_data)} assets in sheet data")

        buyout_data = self.sheets_service.get_buyout_data()
        logger.info(f"Found {len(buyout_data)} buyout codes in buyout data")

        source_files = self.drive_service.list_files(self.source_folder_id)
        logger.info(f"Found {len(source_files)} files in source folder")

        processed_assets = []

        for file in source_files:
            # Remove limit for production use
            if source_files.index(file) < 10:
                continue
            if source_files.index(file) == 20:
                break

            file_id = file.get("id")
            file_name = file.get("name")

            if not file_id or not file_name:
                continue

            logger.info(f"Processing file: {file_name}")

            parsed_data = self.asset_parser.parse_filename(file_name)
            if not parsed_data:
                logger.warning(f"Failed to parse filename: {file_name}, skipping")
                continue

            matching_sheet_data = {}
            for item in asset_data:
                if item.get("filename") == file_name:
                    matching_sheet_data = item
                    break

            asset = self.sheets_service.create_asset_from_sheet_data(
                filename=file_name,
                parsed_data=parsed_data,
                sheet_data=matching_sheet_data,
            )

            asset_file_path = os.path.join(self.assets_dir, file_name)
            self.drive_service.download_file(file_id, asset_file_path)

            processed_file_path = os.path.join(self.processed_dir, f"processed_{file_name}")
            self.drive_service.process_image(asset_file_path, processed_file_path)

            # Validate asset if validator is available
            if self.asset_validator:
                logger.info(f"Validating asset: {file_name}")
                asset = self.asset_validator.validate_asset(asset, processed_file_path, buyout_data)

            # Track processed asset
            processed_assets.append(asset)

            # Skip invalid assets for upload
            if self.asset_validator and not asset.is_valid:
                logger.warning(f"Asset {file_name} failed validation, skipping upload")
                continue

            # Generate hierarchy path
            hierarchy_path = self.asset_parser.get_hierarchy_path(asset, hierarchy_settings)
            logger.info(f"Hierarchy path for {file_name}: {hierarchy_path}")

            # Upload to target folder with hierarchy
            self._upload_to_hierarchy(processed_file_path, hierarchy_path)

            # Clean up temp files (uncomment for production)
            # os.remove(asset_file_path)
            # os.remove(processed_file_path)

        # Generate validation report if validator was used
        if self.asset_validator and processed_assets:
            self._generate_validation_report()

        # Feature 3: Update budgets based on asset performance
        if self.budget_manager and processed_assets:
            self._update_budgets_by_performance(processed_assets)

        logger.info("Asset reorganization completed")

    def _upload_to_hierarchy(self, file_path: str, hierarchy_path: List[str]) -> None:
        """Upload a file to the target folder with the specified hierarchy.

        Args:
            file_path: Path to the file to upload.
            hierarchy_path: List of folder names representing the hierarchy.
        """
        current_folder_id = self.target_folder_id

        for folder_name in hierarchy_path:
            folder_id = self.drive_service.find_folder(current_folder_id, folder_name)

            if not folder_id:
                folder_id = self.drive_service.create_folder(current_folder_id, folder_name)

            current_folder_id = folder_id

        self.drive_service.upload_file(file_path, current_folder_id)

        logger.info(f"Uploaded {os.path.basename(file_path)} to target folder")

    def _generate_validation_report(self) -> None:
        """Generate and save a validation report."""
        report = self.asset_validator.get_validation_report()

        # Log summary
        logger.info("Validation report summary:")
        logger.info(f"- Total assets: {report['total_assets']}")
        logger.info(f"- Valid assets: {report['valid_assets']}")
        logger.info(f"- Invalid assets: {report['invalid_assets']}")
        logger.info(f"- Errors: {report['errors']}")

        report_path = os.path.join(self.reports_dir, "validation_report.json")
        with open(report_path, "w") as f:
            json.dump(report, f, indent=2)

        logger.info(f"Detailed validation report saved to: {report_path}")

        # Save invalid assets list to a more readable format
        if report["invalid_assets"] > 0:
            invalid_report_path = os.path.join(self.reports_dir, "invalid_assets.txt")
            with open(invalid_report_path, "w") as f:
                f.write("INVALID ASSETS REPORT\n")
                f.write("====================\n\n")

                for item in report["invalid_details"]:
                    f.write(f"Filename: {item['filename']}\n")
                    f.write("Reasons:\n")
                    for reason in item["reasons"]:
                        f.write(f"- {reason}\n")
                    f.write("\n")

            logger.info(f"Invalid assets report saved to: {invalid_report_path}")

        if report["errors"] > 0:
            error_report_path = os.path.join(self.reports_dir, "error_report.txt")
            with open(error_report_path, "w") as f:
                f.write("ERROR REPORT\n")
                f.write("============\n\n")

                for item in report["error_details"]:
                    f.write(f"Filename: {item['filename']}\n")
                    f.write(f"Error: {item.get('error', 'Unknown error')}\n")
                    f.write("\n")

            logger.info(f"Error report saved to: {error_report_path}")

    def _update_budgets_by_performance(self, assets: List[Dict]) -> None:
        """Update budgets based on asset performance.

        Args:
            assets: List of assets to process.
        """
        if not self.budget_manager:
            logger.warning("Budget manager not initialized, skipping budget updates")
            return

        logger.info("Starting budget updates based on asset performance")

        # Filter out assets without performance data
        valid_assets = [asset for asset in assets if asset.is_valid]

        if not valid_assets:
            logger.warning("No valid assets with performance data found, skipping budget updates")
            return

        # Adjust budgets based on performance
        budget_summary = self.budget_manager.adjust_budgets_by_performance(valid_assets)

        # Log summary
        logger.info("Budget update summary:")
        logger.info(f"- Total assets processed: {budget_summary['total_assets']}")
        logger.info(f"- Total ads: {budget_summary['total_ads']}")
        logger.info(f"- Budgets increased: {budget_summary['budgets_increased']}")
        logger.info(f"- Budgets decreased: {budget_summary['budgets_decreased']}")
        logger.info(f"- Budgets unchanged: {budget_summary['budgets_unchanged']}")

        # Generate budget report
        self.budget_manager.generate_budget_report(self.reports_dir)

        logger.info("Budget updates completed")
