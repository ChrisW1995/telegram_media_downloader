# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Telegram Media Downloader - a Python application that downloads media files from Telegram channels and chats. It supports both one-time downloads and continuous bot operation.

## Development Commands

### Setup
```bash
# Install dependencies
make install

# Install development dependencies  
make dev_install

# For systems without make:
pip3 install -r requirements.txt
pip3 install -r dev-requirements.txt
```

### Code Quality
```bash
# Run type checking
make static_type_check
# Or directly: mypy media_downloader.py utils module --ignore-missing-imports

# Run linting
make pylint  
# Or directly: pylint media_downloader.py utils module -r y

# Run both type checking and linting
make style_check

# Run tests
make test
# Or directly: py.test --cov media_downloader --doctest-modules --cov utils --cov-report term-missing tests/
```

### Running the Application
```bash
# Main script - starts either web UI or one-time download
python3 media_downloader.py

# Web interface available at localhost:5000 (configurable via web_port in config.yaml)
```

## Architecture

### Core Components

- **`media_downloader.py`** - Main entry point and download logic
- **`module/app.py`** - Application class managing configuration, data persistence, and core application state
- **`module/bot.py`** - Telegram bot implementation for remote control via bot commands
- **`module/web.py`** - Flask web interface for browser-based control
- **`module/pyrogram_extension.py`** - Extended Pyrogram functionality and client management
- **`module/filter.py`** - Message filtering system based on date ranges and content
- **`module/cloud_drive.py`** - Cloud upload functionality (rclone, aligo)

### Configuration System

- **`config.yaml`** - Main configuration file containing:
  - Telegram API credentials (api_id, api_hash) 
  - Bot token for remote control
  - Chat configurations with download filters
  - Media types and file format preferences
  - Save paths and file naming conventions
  - Web interface settings
  - Cloud upload settings

- **`data.yaml`** - Runtime data storage for:
  - Download progress tracking
  - Failed download retry queue
  - Message ID bookmarks

### Download Flow

1. Application reads config.yaml and data.yaml
2. Initializes Pyrogram client with API credentials
3. For each configured chat:
   - Fetches message history using `get_chat_history_v2`
   - Applies filters to determine which messages to process
   - Downloads media files with organized directory structure
   - Updates progress in data.yaml
   - Optionally uploads to cloud storage

### File Organization

Downloads are saved with configurable directory structure via `file_path_prefix`:
- `chat_title` - Channel/group name
- `media_datetime` - Date-based folders (format configurable via `date_format`)
- `media_type` - Organized by media type

File naming supports prefix customization via `file_name_prefix`:
- `message_id` - Telegram message ID
- `file_name` - Original filename
- `caption` - Message caption text

## Key Features

- **Dual Operation Modes**: Web interface (localhost:5000) and Telegram bot control
- **Filtering System**: Date range and content-based filtering of messages
- **Cloud Integration**: Upload to cloud storage via rclone or aligo
- **Progress Tracking**: Persistent download state and retry mechanism
- **Multi-format Support**: Audio, video, photo, document, voice, animation
- **Custom Downloads**: Targeted download of specific message IDs

## Testing

Test files are organized in `tests/` with coverage for:
- Core downloader functionality
- Utility modules (crypto, file management, formatting)
- Application configuration and filters

## Code Style

- **Linting**: Configured via `pylintrc` with max line length 90
- **Type Checking**: mypy configuration in `mypy.ini`
- **Python Version**: Supports Python 3.7+

## Dependencies

- **Pyrogram**: Telegram client library (custom fork)
- **Flask**: Web interface framework
- **PyYAML**: Configuration file parsing
- **Rich/Loguru**: Enhanced logging and console output
- **Cryptographic Libraries**: For Telegram protocol support