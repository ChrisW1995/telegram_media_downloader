# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in the module directory.

## Module Architecture Overview

The `module/` directory contains the core architectural components of the Telegram Media Downloader application, organized into functional layers:

### Core Application Layer
- **`app.py`** - Central application class managing configuration, data persistence, and core application state
  - Defines status enums: `DownloadStatus`, `ForwardStatus`, `UploadStatus`
  - Contains `Application` class with configuration management and task orchestration
  - Handles YAML config/data file loading and saving
  - Manages media type filtering and file path generation

- **`app_db.py`** - Database abstraction layer (currently using SQLite for session management)

### Telegram Integration Layer
- **`bot.py`** - Telegram bot implementation for remote control via bot commands
  - Contains `DownloadBot` class with command handlers
  - Implements progress reporting and task management through bot interface
  - Key methods: download commands, forward commands, status reporting

- **`pyrogram_extension.py`** - Extended Pyrogram functionality and client management
  - Core download logic and Telegram API interactions
  - Progress tracking and bot status reporting functions
  - Client session management and authentication handling

- **`get_chat_history_v2.py`** - Enhanced chat history retrieval with filtering capabilities
- **`send_media_group_v2.py`** - Media group handling for Telegram message forwarding

### Web Interface Layer
- **`web_original.py`** - Traditional Flask web interface for browser-based control
- **`web_zip_api.py`** - ZIP download functionality API endpoints
- **`multiuser_auth.py`** - Multi-user authentication system for web interface
  - Contains `TelegramAuthManager` class for handling multiple user sessions
  - Manages phone/code/password authentication flow
  - Handles session persistence and user management

### Download Management Layer
- **`custom_download.py`** - Custom download functionality for specific message IDs
  - Handles targeted downloads and custom filtering
  - Integrates with progress tracking system

- **`download_stat.py`** - Download statistics and progress tracking
  - Manages download counters and status updates
  - Handles TaskNode statistics for bot progress reporting

- **`session_storage.py`** - Session management for Fast Test and user authentication
  - Temporary session storage for testing functionality
  - User session lifecycle management

### Utility and Support Layer
- **`filter.py`** - Message filtering system based on date ranges and content
  - Date-based filtering logic
  - Content filtering capabilities

- **`cloud_drive.py`** - Cloud upload functionality (rclone, aligo integration)
  - Upload adapters for different cloud services
  - File compression and cleanup after upload

- **`language.py`** - Internationalization and localization support
  - Language switching functionality
  - Translation key management

### Static Resources (`static/`)

**CSS Architecture** (`static/css/message_downloader/`):
- **`main.css`** - CSS module index file
- **`base.css`** - Base styles and CSS variables system
- **`theme.css`** - Theme management (light/dark mode)
- **`layout.css`** - Layout and structural styles
- **`components.css`** - UI component styles (buttons, forms, cards)
- **`chat.css`** - Chat interface and message bubble styles
- **`controls.css`** - Chat controls and navigation components
- **`animations.css`** - Animation effects and transitions
- **`responsive.css`** - Responsive design and media queries

**JavaScript Architecture** (`static/js/message_downloader/`):
- **`index.js`** - Module architecture documentation
- **`core.js`** - Core variables, constants, and utility functions
- **`theme.js`** - Theme switching logic
- **`auth.js`** - Telegram authentication functionality
- **`groups.js`** - Group management and sidebar rendering
- **`messages.js`** - Message loading, rendering, and scroll handling
- **`selection.js`** - Message selection and download management
- **`notifications.js`** - Notification system and progress tracking
- **`ui.js`** - UI interaction logic and event handling
- **`main.js`** - Application initialization

## Key Data Flows

### Download Flow
1. **Configuration Loading**: `app.py` loads `config.yaml` and `data.yaml`
2. **Client Initialization**: `pyrogram_extension.py` creates Pyrogram client
3. **Message Retrieval**: `get_chat_history_v2.py` fetches filtered messages
4. **Download Execution**: `pyrogram_extension.py` handles media download with progress tracking
5. **Status Updates**: `download_stat.py` updates statistics, `bot.py` reports progress
6. **Post-Processing**: `cloud_drive.py` handles optional cloud upload

### Web Interface Flow
1. **Authentication**: `multiuser_auth.py` handles user login
2. **Session Management**: `session_storage.py` manages user sessions
3. **Message Browsing**: Frontend JS modules load and display messages
4. **Download Requests**: API endpoints process download selections
5. **Progress Tracking**: Real-time updates through WebSocket or polling

### Bot Command Flow
1. **Command Reception**: `bot.py` receives Telegram bot commands
2. **Task Creation**: Creates TaskNode for progress tracking
3. **Download Execution**: Delegates to `custom_download.py` or core download logic
4. **Progress Reporting**: Uses `report_bot_download_status` for real-time updates
5. **Completion Notification**: Bot sends final status with statistics

## Critical Integration Points

### TaskNode System
- **Purpose**: Unified progress tracking across bot and web interfaces
- **Key Requirement**: TaskNode IDs must match between creation and progress updates
- **Location**: Managed in `app.py`, used throughout download modules

### Session Management
- **Pyrogram Sessions**: Stored as SQLite files, managed by `pyrogram_extension.py`
- **Web Sessions**: Managed by `multiuser_auth.py` with file-based persistence
- **Database Locks**: Use `fix_database_lock.sh` to resolve SQLite WAL/journal conflicts

### Progress Tracking
- **Real-time Updates**: `download_stat.py` updates, `bot.py` reports immediately
- **Web Interface**: JavaScript modules poll for progress updates
- **Bot Interface**: Uses TaskNode system for live progress messages

## Development Guidelines

### Module Dependencies
- Core modules (`app.py`, `pyrogram_extension.py`) are foundation dependencies
- Web modules depend on authentication layer
- Download modules integrate with progress tracking system
- Static resources follow modular loading order defined in `main.js`

### Error Handling
- Session conflicts: Use utility scripts (`fix_database_lock.sh`)
- Authentication failures: Handled by `multiuser_auth.py` with proper error responses
- Download failures: Tracked in `download_stat.py` with retry mechanisms

### Testing Considerations
- Mock Pyrogram client for unit tests
- Test TaskNode ID consistency across modules
- Verify session persistence and cleanup
- Test progress tracking accuracy

## Critical Bug Fix Notes

### TaskNode ID Consistency (2025-09-20)
- **Issue**: Progress updates skipped due to TaskNode ID mismatch
- **Solution**: Ensure single TaskNode creation uses consistent `task_id`
- **Location**: `custom_download.py:347-357`

### Message Downloader Modularization (2025-09-21)
- **Achievement**: 3,693-line monolithic HTML split into 19 modular files
- **Architecture**: CSS and JS modules with clear dependency chain
- **Benefits**: Improved maintainability and parallel development capability