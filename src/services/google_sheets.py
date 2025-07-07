import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from google.oauth2 import service_account
from googleapiclient.discovery import build

from src.models.asset import Asset
from src.models.hierarchy_settings import HierarchySettings

logger = logging.getLogger(__name__)


class GoogleSheetsService:
    """Service for interacting with Google Sheets."""

    def __init__(self, credentials_file: str, spreadsheet_id: str):
        """Initialize the Google Sheets service.

        Args:
            credentials_file: Path to the Google API credentials file.
            spreadsheet_id: ID of the Google Sheets spreadsheet.
        """
        self.credentials = service_account.Credentials.from_service_account_file(
            credentials_file,
            scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"],
        )
        self.service = build("sheets", "v4", credentials=self.credentials)
        self.spreadsheet_id = spreadsheet_id

    def get_sheet_data(self, sheet_name: str, range_name: Optional[str] = None) -> List[List[Any]]:
        """Get data from a sheet.

        Args:
            sheet_name: Name of the sheet to get data from.
            range_name: Optional range to get data from. If None, the entire sheet is returned.

        Returns:
            List of rows, where each row is a list of cell values.
        """
        if range_name:
            range_to_read = f"{sheet_name}!{range_name}"
        else:
            range_to_read = sheet_name

        result = (
            self.service.spreadsheets().values().get(spreadsheetId=self.spreadsheet_id, range=range_to_read).execute()
        )

        return result.get("values", [])

    def get_ui_settings(self) -> Dict[str, Any]:
        """Get UI settings from the UI tab.

        Returns:
            Dictionary containing the UI settings with HierarchySettings object.
        """
        ui_data = self.get_sheet_data("UI")

        logger.info(f"UI data retrieved: {ui_data}")

        if not ui_data or len(ui_data) < 2:
            logger.error("UI settings not found or invalid format")
            return {}

        # Create HierarchySettings from sheet data
        hierarchy_settings = HierarchySettings.from_sheet_data(ui_data[1:])

        logger.info(f"Created hierarchy settings with {len(hierarchy_settings.levels)} levels")
        if hierarchy_settings.levels:
            logger.info(f"Hierarchy fields: {[level.field for level in hierarchy_settings.get_sorted_levels()]}")

        return {"hierarchy_settings": hierarchy_settings}

    def get_asset_data(self) -> List[Dict[str, Any]]:
        """Get asset data from the uac_assets_data tab.

        Returns:
            List of dictionaries containing asset data.
        """
        asset_data = self.get_sheet_data("uac_assets_data")

        if not asset_data or len(asset_data) < 2:
            logger.error("Asset data not found or invalid format")
            return []

        # Extract headers and data
        headers = asset_data[0]
        result = []

        for i in range(1, len(asset_data)):
            row = asset_data[i]
            if len(row) < len(headers):
                # Pad row with empty values if needed
                row.extend([""] * (len(headers) - len(row)))

            asset_dict = {headers[j]: row[j] for j in range(len(headers))}
            result.append(asset_dict)

        return result

    def get_ads_data(self) -> List[Dict[str, Any]]:
        """Get ads data from the uac_ads_data tab.

        Returns:
            List of dictionaries containing ads data.
        """
        ads_data = self.get_sheet_data("uac_ads_data")

        if not ads_data or len(ads_data) < 2:
            logger.error("Ads data not found or invalid format")
            return []

        # Extract headers and data
        headers = ads_data[0]
        result = []

        for i in range(1, len(ads_data)):
            row = ads_data[i]
            if len(row) < len(headers):
                # Pad row with empty values if needed
                row.extend([""] * (len(headers) - len(row)))

            ad_dict = {headers[j]: row[j] for j in range(len(headers))}
            result.append(ad_dict)

        logger.info(f"Found {len(result)} ads in uac_ads_data tab")
        return result

    def find_matching_asset_in_sheets(self, filename: str) -> Dict[str, Any]:
        """Find a matching asset in the Google Sheets data based on filename.

        Args:
            filename: The local filename to match

        Returns:
            Matching asset data from sheets or empty dict if no match found
        """
        # Get all assets from the sheet
        all_assets = self.get_asset_data()

        # Try exact match first
        for asset in all_assets:
            if asset.get("asset_name") == filename:
                logger.info(f"Found exact match for {filename} in Google Sheets")
                return asset

        # Try partial match - look for key components in the filename
        # Extract components from filename that might be in the sheet
        parts = filename.split("|")
        if len(parts) >= 3:
            country_lang = parts[0].strip()
            concept = parts[2].strip()
            audience = parts[3].strip() if len(parts) > 3 else ""

            for asset in all_assets:
                asset_name = asset.get("asset_name", "")
                # Check if key parts are in the asset name
                if country_lang in asset_name and concept in asset_name and audience in asset_name:
                    logger.info(f"Found partial match for {filename} in Google Sheets: {asset_name}")
                    return asset

        # If we get here, we couldn't find a match
        logger.warning(f"No matching asset found in Google Sheets for {filename}")
        return {}

    def create_asset_from_sheet_data(
        self, filename: str, parsed_data: Dict[str, str], sheet_data: Dict[str, Any]
    ) -> Asset:
        """Create an Asset object from parsed filename data and sheet data.

        Args:
            filename: Original filename
            parsed_data: Data parsed from the filename
            sheet_data: Data from the Google Sheet

        Returns:
            Asset object with combined data
        """
        # Extract country and language from country_language
        country_language = parsed_data.get("country_language", "")
        country = country_language.split("-")[0] if "-" in country_language else ""
        language = country_language.split("-")[1] if "-" in country_language else ""

        # Parse production date if available
        production_date = None

        if "asset_production_date" in sheet_data and sheet_data["asset_production_date"]:
            production_date = datetime.strptime(sheet_data["asset_production_date"], "%Y-%m-%d %H:%M:%S")

        # Get asset_id from sheet_data or try to find a matching asset
        asset_id = sheet_data.get("asset_id")
        if not asset_id:
            # Try to find a matching asset in the sheets
            matching_asset = self.find_matching_asset_in_sheets(filename)
            if matching_asset:
                asset_id = matching_asset.get("asset_id")
                # Update sheet_data with the matching asset data
                sheet_data.update(matching_asset)
                logger.info(f"Found matching asset_id {asset_id} for {filename}")

        # Look up performance metrics from ads data if we have asset_id
        budget = 1000  # Default budget
        clicks = None
        impressions = None
        conversions = None
        ad_id = None

        # Get ads data for this asset if available
        if asset_id:
            logger.debug(f"Looking up ads data for asset_id: {asset_id}")
            ads_data = self.get_ads_data()

            # Try to find exact match first
            for ad_data in ads_data:
                if str(ad_data.get("asset_id")) == str(asset_id):
                    # Found matching ad data
                    ad_id = ad_data.get("ad_id")
                    budget = int(float(ad_data.get("budget", 1000))) if ad_data.get("budget") else 1000

                    # Handle numeric values properly
                    try:
                        clicks = int(float(ad_data.get("clicks", 0)))
                    except (ValueError, TypeError):
                        clicks = 0

                    try:
                        impressions = int(float(ad_data.get("impressions", 0)))
                    except (ValueError, TypeError):
                        impressions = 0

                    try:
                        conversions = int(float(ad_data.get("conversions", 0)))
                    except (ValueError, TypeError):
                        conversions = 0

                    logger.info(
                        f"Found matching ad data for asset {filename}: ad_id={ad_id}, budget={budget}, "
                        f"clicks={clicks}, impressions={impressions}, conversions={conversions}"
                    )
                    break

            # If we still don't have ad_id, try matching by asset name
            if not ad_id and "asset_name" in sheet_data:
                asset_name = sheet_data.get("asset_name")
                if asset_name:
                    for ad_data in ads_data:
                        if ad_data.get("asset_name") == asset_name:
                            ad_id = ad_data.get("ad_id")
                            budget = int(float(ad_data.get("budget", 1000))) if ad_data.get("budget") else 1000

                            # Handle numeric values properly
                            try:
                                clicks = int(float(ad_data.get("clicks", 0)))
                            except (ValueError, TypeError):
                                clicks = 0

                            try:
                                impressions = int(float(ad_data.get("impressions", 0)))
                            except (ValueError, TypeError):
                                impressions = 0

                            try:
                                conversions = int(float(ad_data.get("conversions", 0)))
                            except (ValueError, TypeError):
                                conversions = 0

                            logger.info(
                                f"Found matching ad data by name for asset {filename}: ad_id={ad_id}, budget={budget}"
                            )
                            break

        # If we still don't have ad_id, try to find a similar asset in ads data
        if not ad_id:
            # Extract key parts from filename for matching
            parts = filename.split("|")
            if len(parts) >= 3:
                country_lang = parts[0].strip()  # noqa: F841
                audience = parts[3].strip() if len(parts) > 3 else ""

                # Try to find an ad with similar characteristics
                if audience and country:
                    for ad_data in self.get_ads_data():
                        ad_name = ad_data.get("adgroup_name", "")
                        # If the ad group name matches the audience and country code is in the account name
                        if audience in ad_name and country in ad_data.get("account_name", ""):
                            ad_id = ad_data.get("ad_id")
                            budget = int(float(ad_data.get("budget", 1000))) if ad_data.get("budget") else 1000
                            clicks = int(float(ad_data.get("clicks", 0))) if ad_data.get("clicks") else 0
                            impressions = int(float(ad_data.get("impressions", 0))) if ad_data.get("impressions") else 0
                            conversions = int(float(ad_data.get("conversions", 0))) if ad_data.get("conversions") else 0
                            logger.info(f"Found similar ad for asset {filename}: ad_id={ad_id}, budget={budget}")
                            break

        return Asset(
            filename=filename,
            country=country,
            language=language,
            buyout_code=parsed_data.get("buyout_code", ""),
            concept=parsed_data.get("concept", ""),
            audience=parsed_data.get("audience", ""),
            transaction_side=parsed_data.get("transaction_side", ""),
            asset_format=parsed_data.get("asset_format", ""),
            duration=parsed_data.get("duration", ""),
            file_format=parsed_data.get("file_format", ""),
            file_id=asset_id,  # Use asset_id from sheet data
            mime_type=sheet_data.get("asset_mime_type"),
            production_date=production_date,
            budget=budget,
            ad_id=ad_id,
            clicks=clicks,
            impressions=impressions,
            conversions=conversions,
        )

    def get_buyout_data(self) -> Dict[str, str]:
        """Get buyout data from the buyouts_to_date tab.

        Returns:
            Dictionary mapping buyout codes to expiration dates.
        """
        buyout_data = self.get_sheet_data("buyouts_to_date")

        if not buyout_data or len(buyout_data) < 2:
            logger.error("Buyout data not found or invalid format")
            return {}

        # Extract buyout codes and dates
        result = {}

        for i in range(1, len(buyout_data)):
            row = buyout_data[i]
            if len(row) >= 2:
                buyout_code = row[0]
                expiration_date = row[1]
                result[buyout_code] = expiration_date

        return result
