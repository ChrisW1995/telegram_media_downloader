# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in the module/web/message_downloader directory.

## Message Downloader Module Overview

The `module/web/message_downloader/` directory contains the modularized implementation of the Message Downloader feature, a comprehensive browser-based interface for Telegram message browsing and selective downloading.

## Module Structure

### Core Module (`__init__.py`)
- **Blueprint Registration** - Main Blueprint (`message_downloader`) for page routes
- **Route Handlers**:
  - `GET /message_downloader` - Main Message Downloader interface
  - `GET /message_downloader/login` - Dedicated login page
- **Authentication Flow** - Session-based authentication with redirect handling
- **Blueprint Coordination** - Registers all sub-module Blueprints
- **App Instance Management** - Distributes main application reference to sub-modules

### Authentication Module (`auth.py`) - 22.5KB
**Purpose**: Handles all `/api/auth/*` authentication endpoints

**Key Features**:
- **Multi-method Authentication**: Phone/code, password, QR code login
- **Session Management**: Flask session integration with Telegram authentication
- **Thread-safe Async Execution**: Event loop coordination for Pyrogram operations
- **Error Handling**: Comprehensive exception handling with user-friendly messages

**API Endpoints**:
- `POST /api/auth/send_code` - Initiate phone verification
- `POST /api/auth/verify_code` - Verify SMS/call code
- `POST /api/auth/verify_password` - Two-factor authentication
- `GET /api/auth/status` - Authentication status check
- `POST /api/auth/logout` - Session termination
- `POST /api/auth/qr_login` - QR code authentication initiation
- `POST /api/auth/check_qr_status` - QR login progress monitoring

**Critical Components**:
```python
# Thread-safe async execution pattern
def run_async_in_thread(coro):
    future = asyncio.run_coroutine_threadsafe(coro, _app.loop)
    return future.result(timeout=30)
```

### Group Management Module (`groups.py`) - 9.1KB
**Purpose**: Handles group/channel listing and message retrieval

**API Endpoints**:
- `GET /api/groups/list` - List available groups and channels
- `POST /api/groups/messages` - Fetch initial message batch
- `POST /api/groups/load_more` - Load additional messages with pagination

**Key Features**:
- **Group Discovery**: Automatic detection of available chats
- **Message Pagination**: Efficient message loading with offset/limit
- **Media Detection**: Identifies messages with downloadable media
- **Performance Optimization**: Lazy loading and memory-efficient message handling

### Download Management Module (`downloads.py`) - 30.1KB
**Purpose**: Handles download task management and progress tracking

**API Endpoints**:
- `POST /api/fast_download/add_tasks` - Queue selected messages for download
- `GET /api/fast_download/status` - Real-time download progress monitoring
- `POST /api/download/zip` - Create and download ZIP archives
- `GET /api/download/zip/<task_id>` - Download completed ZIP files

**Key Features**:
- **Custom Download Integration**: Interfaces with existing `custom_download.py` system
- **Progress Tracking**: Real-time download status and statistics
- **ZIP Archive Creation**: Automatic compression of downloaded media
- **Task Management**: Queue management and concurrent download handling
- **Auto-trigger Downloads**: Automatic download initiation after task creation

**Critical Integration Points**:
```python
# Config integration for custom downloads
custom_downloads = _app.config['custom_downloads']
target_ids[chat_id].extend(new_ids)
_app.update_config()

# Progress system integration
from ..core.progress_system import download_progress, active_download_session
```

### Thumbnail Generation Module (`thumbnails.py`) - 8.1KB
**Purpose**: Generates and serves media thumbnails

**API Endpoints**:
- `GET /api/message_downloader_thumbnail/<chat_id>/<message_id>` - Generate message thumbnails

**Key Features**:
- **In-memory Processing**: Downloads media to memory without disk storage
- **Image Processing**: PIL-based thumbnail generation with size optimization
- **Base64 Encoding**: Data URL format for frontend integration
- **Performance Caching**: Efficient thumbnail generation with size limits
- **Media Type Support**: Photos, documents with preview capability

**Thumbnail Generation Process**:
1. **Media Download**: In-memory download using Pyrogram client
2. **Image Processing**: PIL thumbnail generation (max 300x300px)
3. **Format Optimization**: JPEG compression for size reduction
4. **Base64 Encoding**: Data URL creation for direct browser use

## Authentication Flow Architecture

### Session Management
- **Flask Session**: Primary authentication state storage
- **Multi-user Support**: Individual user authentication tracking
- **Session Persistence**: Authentication state maintained across requests
- **Secure Logout**: Complete session cleanup and state clearing

### Authentication States
```python
# Authentication status tracking
session['message_downloader_authenticated'] = True
session['message_downloader_user_info'] = user_data
session['message_downloader_client_id'] = client_identifier
```

### Error Handling Strategy
Consistent error response format:
```python
# Success response
{"success": True, "data": {...}}

# Error response with details
{"success": False, "error": "User message", "details": "Technical details"}
```

## Download System Integration

### Custom Download System
- **Config Integration**: Updates `custom_downloads` configuration section
- **Target ID Management**: Manages `target_ids` per chat
- **Automatic Triggering**: Initiates downloads after task creation
- **Progress Integration**: Connects with main progress tracking system

### Progress Tracking Flow
1. **Task Creation** → Updates config with target message IDs
2. **Download Trigger** → Automatic custom download initiation
3. **Progress Monitoring** → Real-time status via progress system
4. **Completion Handling** → ZIP creation and download availability

### ZIP Archive Management
- **Temporary File Handling**: Secure temporary file creation and cleanup
- **Archive Structure**: Organized file structure within ZIP
- **Download Serving**: Flask send_file integration for ZIP delivery
- **Cleanup Process**: Automatic temporary file removal

## Frontend Integration Points

### JavaScript Module Interaction
- **Authentication API**: Called by `auth.js` module
- **Group Management**: Integrated with `groups.js` for sidebar population
- **Download Control**: Connected to `selection.js` for download management
- **Progress Updates**: Polled by `notifications.js` for status display

### Real-time Communication
- **Polling Strategy**: Regular status checks for progress updates
- **Error Propagation**: Frontend-friendly error message formatting
- **State Synchronization**: Session state consistency between frontend and backend

## Development Guidelines

### Adding New API Endpoints
1. **Module Selection**: Choose appropriate module based on functionality
2. **Blueprint Registration**: Add route to respective Blueprint
3. **Authentication**: Use `@require_message_downloader_auth` decorator
4. **Error Handling**: Use `@handle_api_exception` decorator
5. **Response Format**: Follow standard success/error response patterns

### Async Operation Handling
```python
# Standard async execution pattern
def api_endpoint():
    result = run_async_in_thread(async_operation())
    return success_response(result)
```

### Progress System Integration
```python
# Progress tracking pattern
initialize_download_session(session_id)
update_download_progress(session_id, progress_data)
progress = get_download_progress_data(session_id)
```

## Testing Considerations

### Unit Testing
- **Authentication Flow**: Test all authentication states and transitions
- **API Endpoints**: Validate request/response handling
- **Error Scenarios**: Test error handling and recovery
- **Session Management**: Verify session state consistency

### Integration Testing
- **Download Flow**: End-to-end download task creation and completion
- **Progress Tracking**: Verify real-time progress updates
- **ZIP Generation**: Test archive creation and download
- **Authentication Integration**: Verify Telegram client integration

### Performance Testing
- **Concurrent Downloads**: Multiple simultaneous download tasks
- **Large Message Batches**: Performance with high message volumes
- **Memory Usage**: Monitor memory consumption during operations
- **Thumbnail Generation**: Performance with various media types

## Critical Dependencies

### External Modules
- **`module.multiuser_auth`** - Telegram authentication management
- **`module.custom_download`** - Core download functionality
- **`module.session_storage`** - Session persistence
- **`..core.progress_system`** - Progress tracking infrastructure

### Configuration Requirements
- **`custom_downloads`** configuration section must exist
- **Event loop** must be available in main application
- **Telegram client** must be initialized and accessible

## Security Considerations

### Authentication Security
- **Session Validation**: All API endpoints require authentication
- **Secure Session Storage**: Flask session security configuration
- **Input Validation**: Request data validation and sanitization
- **Error Message Security**: Avoid exposing internal system details

### Download Security
- **File Path Validation**: Secure filename handling
- **Temporary File Management**: Secure temporary file creation and cleanup
- **ZIP Bomb Prevention**: File size and compression ratio limits
- **Access Control**: User-specific download access validation