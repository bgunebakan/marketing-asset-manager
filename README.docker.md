# Docker Setup for Marketing Asset Manager

This document explains how to run the Marketing Asset Manager using Docker.

## Prerequisites

- Docker and Docker Compose installed on your system
- Google API credentials file (`credentials.json`)
- Environment variables configured in `.env` file

## Setup

1. Make sure your `.env` file is properly configured with all required variables:

```
GOOGLE_CREDENTIALS_FILE=credentials.json
GOOGLE_SHEET_ID=your_sheet_id
SOURCE_FOLDER_ID=your_source_folder_id
TARGET_FOLDER_ID=your_target_folder_id
SHARED_DRIVE_ID=your_shared_drive_id
LOG_LEVEL=INFO
GOOGLE_ADS_API_KEY=your_google_ads_api_key
OPENAI_API_KEY=your_openai_api_key
```

2. Ensure your Google API credentials file (`credentials.json`) is in the project root directory.

## Running with Docker Compose

To build and start the application:

```bash
docker-compose up --build
```

To run in detached mode (background):

```bash
docker-compose up -d
```

To stop the application:

```bash
docker-compose down
```

## Volumes

The Docker setup includes the following volume mounts:

- Project directory: Mounted to `/app` in the container
- Credentials file: Mounted as read-only to `/app/credentials.json`
- Temporary files: The `tmp` directory is shared between host and container

## Customization

You can modify the `docker-compose.yml` file to adjust resource limits, add more services, or change environment variables as needed.

## Troubleshooting

If you encounter issues:

1. Check the logs: `docker-compose logs`
2. Verify your credentials file is valid and has the necessary permissions
3. Ensure all required environment variables are set in the `.env` file
4. Make sure Docker has sufficient resources allocated
