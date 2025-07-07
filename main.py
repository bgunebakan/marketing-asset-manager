#!/usr/bin/env python3
import logging
import os

from dotenv import load_dotenv

from src.asset_reorganizer import AssetReorganizer

load_dotenv()

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def main():
    """Main entry point."""
    try:
        reorganizer = AssetReorganizer(
            credentials_file=os.getenv("GOOGLE_CREDENTIALS_FILE", "credentials.json"),
            spreadsheet_id=os.getenv("GOOGLE_SHEET_ID"),
            source_folder_id=os.getenv("SOURCE_FOLDER_ID"),
            target_folder_id=os.getenv("TARGET_FOLDER_ID"),
            shared_drive_id=os.getenv("SHARED_DRIVE_ID"),
            openai_api_key=os.getenv("OPENAI_API_KEY"),
            google_ads_api_key=os.getenv("GOOGLE_ADS_API_KEY"),
        )

        reorganizer.run()
    except Exception as e:
        logger.exception(f"Error running asset reorganizer: {e}")
        return 1

    return 0


if __name__ == "__main__":
    exit(main())
