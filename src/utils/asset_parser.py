import logging
import os
import re
from typing import Dict, Optional

from src.models.asset import Asset
from src.models.hierarchy_settings import HierarchySettings

logger = logging.getLogger(__name__)


class AssetParser:
    """Parser for asset filenames."""

    # Asset filename format:
    # {country - language} | {buyout-code} | {concept} | {audience} | {transaction_side} | {asset_format} | {duration} | {file_format} # noqa: E501

    def __init__(self):
        """Initialize the asset parser."""
        self.pattern = r"^([A-Z]{2}-[A-Z]{2})\s*\|\s*([A-Za-z0-9]+)\s*\|\s*(.+?)\s*\|\s*(.+?)\s*\|\s*(.+?)\s*\|\s*(.+?)\s*\|\s*(.+?)\s*\|\s*(.+)$"  # noqa: E501

    def parse_filename(self, filename: str) -> Optional[Dict[str, str]]:
        """Parse an asset filename and extract its components.

        Args:
            filename: The filename to parse.

        Returns:
            Dictionary containing the extracted components, or None if parsing failed.
        """

        # Remove file extension for parsing
        base_name = os.path.basename(filename)

        match = re.match(self.pattern, base_name)

        if not match:
            logger.warning(f"Failed to parse filename: {filename}")
            return None

        (
            country_language,
            buyout_code,
            concept,
            audience,
            transaction_side,
            asset_format,
            duration,
            file_format,
        ) = match.groups()

        return {
            "country_language": country_language.strip(),
            "buyout_code": buyout_code.strip(),
            "concept": concept.strip(),
            "audience": audience.strip(),
            "transaction_side": transaction_side.strip(),
            "asset_format": asset_format.strip(),
            "duration": duration.strip(),
            "file_format": file_format.strip(),
            "original_filename": base_name,
        }

    def extract_country(self, country_language: str) -> str:
        """Extract country code from country-language code.

        Args:
            country_language: Country-language code (e.g., 'UK-EN').

        Returns:
            Country code.
        """
        if "-" in country_language:
            return country_language.split("-")[0]
        return country_language

    def get_field_value(self, asset: Asset, field_name: str) -> str:
        """Get the value of a field from an Asset object.

        Args:
            asset: Asset object.
            field_name: Name of the field to get.

        Returns:
            Value of the field, or 'Unset' if the field is not found.
        """
        field_mapping = {
            "country": lambda a: a.country,
            "language": lambda a: a.language,
            "buyout_code": lambda a: a.buyout_code,
            "concept": lambda a: a.concept,
            "audience": lambda a: a.audience,
            "transaction_side": lambda a: a.transaction_side,
            "asset_format": lambda a: a.asset_format,
            "duration": lambda a: a.duration,
            "year": lambda a: str(a.production_date.year) if a.production_date else "",
            "month": lambda a: (
                str(a.production_date.month) if a.production_date else ""
            ),
        }

        if field_name in field_mapping:
            value = field_mapping[field_name](asset)
            return value if value else "Unset"

        return "Unset"

    def get_hierarchy_path(
        self, asset: Asset, hierarchy_settings: HierarchySettings
    ) -> list:
        """Get the hierarchy path for an asset based on hierarchy levels.

        Args:
            asset: Asset object.
            hierarchy_settings: HierarchySettings object with sorted levels.

        Returns:
            List of folder names representing the hierarchy path.
        """
        path = []

        for level in hierarchy_settings.get_sorted_levels():
            field = level.field
            value = self.get_field_value(asset, field)
            path.append(value)

        return path

    def create_asset_from_parsed_data(
        self, filename: str, parsed_data: Dict[str, str]
    ) -> Asset:
        """Create an Asset object from parsed filename data.

        Args:
            filename: Original filename
            parsed_data: Data parsed from the filename

        Returns:
            Asset object with basic data from filename
        """
        # Extract country and language from country_language
        country_language = parsed_data.get("country_language", "")
        country = country_language.split("-")[0] if "-" in country_language else ""
        language = country_language.split("-")[1] if "-" in country_language else ""

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
            is_valid_name=True,  # Assume valid if parsing succeeded
        )
