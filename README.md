# Marketing Asset Manager

Marketing Asset Manager is a system for managing, organizing, validating, and optimizing marketing assets for Google Ads campaigns. It streamlines the workflow for marketing teams by automating asset processing, validation, organization, and budget optimization.

## Table of Contents

- [Features](#features)
- [Project Architecture](#project-architecture)
- [Requirements](#requirements)
- [Installation](#installation)
- [Configuration](#configuration)
- [Usage](#usage)
- [Project Structure](#project-structure)
- [Asset Naming Convention](#asset-naming-convention)
- [Google Sheets Structure](#google-sheets-structure)
- [Reports](#reports)
- [License](#license)

## Features

### 1. Asset Reorganization

- **Dynamic Hierarchy Structure**: Reads hierarchy settings from Google Spreadsheet (UI tab) to determine folder structure
- **Smart Organization**: Reorganizes assets in Google Drive according to the defined hierarchy (e.g., by country, audience, format)
- **Image Processing**: Converts assets to PNG format and optimizes to size < 100KB for faster loading in ad platforms
- **Customizable Structure**: Hierarchy levels can be configured through the UI tab in Google Sheets

### 2. Asset Processing & Validation

- **Naming Convention Validation**: Ensures assets follow the required naming pattern
- **Buyout Code Verification**: Checks buyout code expiration dates against the database and sets budget to zero for expired assets
- **AI-Powered Analysis**: Integrates with OpenAI API to analyze image quality and privacy compliance
- **Validation Reports**: Generates detailed feedback reports about validation results, including specific issues found

### 3. Ads Budget Management

- **Performance-Based Optimization**: Updates budgets based on asset performance metrics (CTR, conversion rate)
- **Smart Budget Allocation**: Increases budget of top-performing assets within each ad by 20% while decreasing budget of low-performing assets by 20%
- **Budget Tracking**: Maintains history of budget changes with timestamps and reasons
- **Performance Reporting**: Generates comprehensive reports on budget adjustments and performance metrics

## Project Architecture

The project follows a modular architecture with clear separation of concerns:

1. **Core Functionality** (`asset_reorganizer.py`): Orchestrates the entire process
2. **Data Models** (`models/`): Defines the structure for assets and hierarchy settings
3. **Services** (`services/`): Handles interactions with external APIs (Google Drive, Sheets, OpenAI)
4. **Utilities** (`utils/`): Provides helper functions for parsing and processing assets

## Requirements

- Python 3.10 or higher
- Google API credentials with access to:
  - Google Drive API
  - Google Sheets API
- Google Drive folders for source and target assets
- Google Sheets spreadsheet with the required tabs:
  - UI (hierarchy settings)
  - uac_assets_data (asset metadata)
  - uac_ads_data (ads metadata)
  - buyout_to_date (buyout code expiration dates)
- OpenAI API key (for image quality and privacy analysis)
- Google Ads API key (for budget management)

## Installation

1. Clone the repository:

```bash
git clone https://github.com/bgunebakan/marketing-asset-manager.git
cd marketing-asset-manager
```

2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Configure environment variables:
   - Copy the `.env.example` file to `.env` and update the values
   - Or set the environment variables manually

## Configuration

The following environment variables are required:

- `GOOGLE_CREDENTIALS_FILE`: Path to the Google API credentials JSON file
- `GOOGLE_SHEET_ID`: ID of the Google Sheets spreadsheet
- `SOURCE_FOLDER_ID`: ID of the source folder in Google Drive
- `TARGET_FOLDER_ID`: ID of the target folder in Google Drive
- `SHARED_DRIVE_ID`: ID of the shared drive (optional)
- `OPENAI_API_KEY`: OpenAI API key for image analysis (optional)
- `GOOGLE_ADS_API_KEY`: Google Ads API key for budget management (optional)

## Usage

Run the asset reorganizer:

```bash
python main.py
```

The tool will:

1. Read settings from Google Sheets
2. Download assets from the source folder
3. Process and validate assets
4. Organize assets according to the hierarchy structure
5. Upload processed assets to the target folder
6. Generate validation and budget reports

## Running Tests

The project uses pytest for running tests. To run the tests, follow these steps:

1. Make sure you have installed all the dependencies including the testing ones:

```bash
pip install -r requirements.txt
```

2. Run all tests:

```bash
pytest
```

3. Run specific test files:

```bash
pytest tests/unit/services/test_budget_manager.py
pytest tests/unit/services/test_asset_validator.py
```

4. Run a specific test class:

```bash
pytest tests/unit/services/test_budget_manager.py::TestBudgetManager
```

5. Run a specific test method:

```bash
pytest tests/unit/services/test_budget_manager.py::TestBudgetManager::test_generate_budget_report
```

6. Run tests with verbose output:

```bash
pytest -v
```

## Project Structure

```
marketing-asset-manager/
├── .env                      # Environment variables
├── .pre-commit-config.yaml   # Pre-commit hooks configuration
├── credentials.json          # Google API credentials
├── main.py                   # Main entry point
├── requirements.txt          # Python dependencies
├── src/
│   ├── __init__.py
│   ├── asset_reorganizer.py  # Core logic
│   ├── models/
│   │   ├── __init__.py
│   │   ├── asset.py               # Asset data model
│   │   └── hierarchy_settings.py  # Hierarchy configuration model
│   ├── services/
│   │   ├── __init__.py
│   │   ├── asset_validator.py    # Asset validation service
│   │   ├── budget_manager.py     # Budget optimization service
│   │   ├── google_ads.py         # Google Ads API integration
│   │   ├── google_drive.py       # Google Drive API integration
│   │   ├── google_sheets.py      # Google Sheets API integration
│   │   └── openai_api.py         # OpenAI API integration
│   └── utils/
│       ├── __init__.py
│       └── asset_parser.py       # Asset filename parsing utilities
└── tmp/                      # Temporary directory for processing
    ├── assets/               # Downloaded original assets
    ├── processed_assets/     # Processed assets
    └── reports/              # Generated reports
```

## Asset Naming Convention

Assets must follow this naming pattern:

```
{country-language} | {buyout-code} | {concept} | {audience} | {transaction_side} | {asset_format} | {duration} | {file_format}
```

Example:

```
FR-FR | P0020 | HVF Seller | Women | Seller | 16x9 | 0s | 1.png
```

Components:

- **country-language**: Country and language codes (e.g., FR-FR)
- **buyout-code**: Code for tracking buyout rights (e.g., P0020)
- **concept**: Creative concept name (e.g., HVF Seller)
- **audience**: Target audience (e.g., Women, Men, Kids)
- **transaction_side**: Buyer or Seller
- **asset_format**: Aspect ratio (e.g., 16x9, 1x1, 4x5)
- **duration**: Video duration or 0s for images
- **file_format**: Additional format information

## Reports

The system generates several types of reports in the `tmp/reports/` directory:

1. **Validation Report** (`validation_report.json`): Summary of validation results
2. **Invalid Assets Report** (`invalid_assets.txt`): Detailed list of invalid assets and reasons
3. **Error Report** (`error_report.txt`): List of errors encountered during processing
4. **Budget Report** (`budget_report.json`): Summary of budget changes and performance metrics
