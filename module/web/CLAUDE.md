# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in the module/web directory.

## Web Module Architecture Overview

The `module/web/` directory represents a complete modular refactoring of the original 3,378-line `web.py` file, creating a maintainable, scalable architecture while preserving full backward compatibility.

## Architecture Structure

### Core Foundation (`core/`)
- **`app_factory.py`** - Flask application factory and initialization
  - Creates and configures Flask application instances
  - Manages event loop integration for async operations
  - Handles global application state and configuration
  - Provides user authentication infrastructure (LoginManager, User class)

- **`decorators.py`** - Authentication and authorization decorators
  - Request authentication validation
  - Session management decorators
  - API endpoint protection

- **`error_handlers.py`** - Unified error handling and response formatting
  - Standardized API response formats (`success_response`, `error_response`)
  - Exception handling for API endpoints
  - Error logging and debugging support

- **`session_manager.py`** - Flask session management
  - User session lifecycle management
  - Session storage and persistence
  - Multi-user session tracking

- **`async_utils.py`** - Asynchronous operation utilities
  - Event loop management for Flask integration
  - Thread-safe async coroutine execution
  - Async-to-sync adapters

- **`progress_system.py`** - Progress tracking and reporting system
  - Download progress monitoring
  - Real-time status updates
  - Integration with TaskNode system

### Message Downloader Module (`message_downloader/`)
- **`__init__.py`** - Main Blueprint registration and route organization
  - Registers all Message Downloader routes
  - Provides module initialization interface
  - Coordinates sub-modules

- **`auth.py`** - Authentication API endpoints (`/api/auth/*`)
  - `POST /api/auth/send_code` - Send phone verification code
  - `POST /api/auth/verify_code` - Verify phone code
  - `POST /api/auth/verify_password` - Two-factor authentication
  - `GET /api/auth/status` - Authentication status check
  - `POST /api/auth/logout` - User logout
  - `POST /api/auth/qr_login` - QR code login
  - `POST /api/auth/check_qr_status` - QR login status

- **`groups.py`** - Group management API endpoints (`/api/groups/*`)
  - `GET /api/groups/list` - List available groups/channels
  - `POST /api/groups/messages` - Fetch group messages
  - `POST /api/groups/load_more` - Load additional messages

- **`downloads.py`** - Download management API (`/api/fast_download/*`)
  - `POST /api/fast_download/add_tasks` - Add download tasks
  - `GET /api/fast_download/status` - Download status monitoring
  - Integration with custom download system

- **`thumbnails.py`** - Media thumbnail generation API
  - `GET /api/message_downloader_thumbnail/<chat_id>/<message_id>`
  - In-memory thumbnail generation
  - Base64 Data URL optimization for performance

### Legacy Support (`legacy/`)
- **`__init__.py`** - Placeholder for traditional web interface functions
  - Reserved for future migration of 30+ legacy routes
  - Backward compatibility preservation

### Transition Infrastructure
- **`transition_helper.py`** - Migration assistance utilities
  - Smooth transition from monolithic to modular architecture
  - Compatibility layer for existing code
- **`REFACTOR_SUMMARY.md`** - Comprehensive refactoring documentation

## Key Design Patterns

### Blueprint Architecture
Each module registers as a Flask Blueprint with clear namespace separation:
- `message_downloader_auth` - Authentication endpoints
- `message_downloader_groups` - Group management
- `message_downloader_downloads` - Download operations
- `message_downloader_thumbnails` - Media thumbnails

### Async-Flask Integration
Manages asyncio integration with Flask's synchronous nature:
```python
# Pattern: Thread-safe async execution
def run_async_in_thread(coro):
    future = asyncio.run_coroutine_threadsafe(coro, _app.loop)
    return future.result(timeout=30)
```

### Error Handling Strategy
Unified error response format across all API endpoints:
```python
# Success response
{"success": True, "data": {...}}

# Error response
{"success": False, "error": "Error message", "details": {...}}
```

## Integration Points

### Session Management
- **Flask Sessions**: Traditional web sessions for login state
- **Telegram Sessions**: Pyrogram client session persistence
- **Multi-user Sessions**: Individual user authentication tracking

### Event Loop Coordination
- **Main Loop**: Application's primary event loop for Pyrogram clients
- **Thread Safety**: Coroutines executed safely from Flask threads
- **Background Tasks**: Download operations run in main loop context

### Progress Tracking Integration
- **TaskNode System**: Unified progress tracking across bot and web
- **Real-time Updates**: WebSocket-like polling for download status
- **Statistics**: Integration with `download_stat.py` for metrics

## API Endpoint Organization

### Authentication Flow (`/api/auth/`)
1. **Phone Number** → `send_code` → Code sent to user
2. **Verification Code** → `verify_code` → User authenticated or 2FA required
3. **2FA Password** → `verify_password` → Complete authentication
4. **Status Check** → `status` → Current auth state
5. **Logout** → `logout` → Clear user session

### Group Management Flow (`/api/groups/`)
1. **List Groups** → `list` → Available channels/groups
2. **Load Messages** → `messages` → Initial message batch
3. **Load More** → `load_more` → Additional messages with pagination

### Download Flow (`/api/fast_download/`)
1. **Add Tasks** → `add_tasks` → Queue selected messages
2. **Monitor Status** → `status` → Real-time download progress
3. **Completion** → Progress system handles notifications

## Development Guidelines

### Module Extension
When adding new functionality:
1. Create appropriate Blueprint in relevant module
2. Follow existing error handling patterns
3. Use async utilities for Telegram operations
4. Integrate with progress tracking if applicable

### Testing Strategy
- **Unit Tests**: Individual module functionality
- **Integration Tests**: Blueprint registration and routing
- **API Tests**: Endpoint response validation
- **Session Tests**: Authentication flow validation

### Backward Compatibility
Current implementation maintains full backward compatibility:
- All existing routes preserved
- Original initialization interface unchanged
- Global variables and state maintained
- Seamless fallback to original `web.py` if needed

## Migration Status

### Completed
✅ Core architecture established
✅ Message Downloader fully modularized
✅ All Message Downloader APIs implemented
✅ Error handling standardized
✅ Session management centralized
✅ Async integration working
✅ 16 routes successfully registered

### Pending (If Full Migration Required)
- Migration of 30+ legacy routes to `legacy/` module
- Complete business logic porting from original `web.py`
- Full test suite for new architecture
- Performance optimization utilizing modular benefits

## Critical Integration Notes

### Flask App Initialization
```python
# Initialize with original interface
from module.web import init_web, get_flask_app

init_web(app, client, queue)  # Same as original web.py
flask_app = get_flask_app()   # Gets modular Flask instance
```

### Event Loop Management
The module automatically manages event loop integration:
- Uses main application event loop when available
- Falls back to thread-based execution when needed
- Maintains thread safety across all async operations

### Error Handling Standards
All API endpoints use consistent error handling:
- JSON responses with success/error indicators
- Detailed error logging for debugging
- User-friendly error messages for frontend
- Exception handling with graceful fallbacks