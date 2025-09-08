"""Multi-user authentication system for TGDL."""

import asyncio
import base64
import json
import os
from datetime import datetime
from typing import Optional, Dict, Any, Tuple
from functools import wraps

from loguru import logger
from flask import request, jsonify, session, current_app
from pyrogram import Client
from pyrogram.errors import (
    SessionPasswordNeeded, PhoneCodeInvalid, PhoneCodeExpired,
    PhoneNumberInvalid, PasswordHashInvalid, AuthKeyUnregistered
)

# from database.multiuser_manager import get_multiuser_db_manager


class TelegramAuthManager:
    """Manages Telegram authentication for multiple users."""
    
    def __init__(self):
        # self.db_manager = get_multiuser_db_manager()  # Disabled for now
        self.active_clients: Dict[str, Client] = {}
        self.user_sessions: Dict[str, str] = {}  # user_id -> session_string
        self.sessions_file = "user_sessions.json"  # Simple file storage
        self._load_sessions()
        
    async def start_auth_process(self, phone_number: str, api_id: int, api_hash: str) -> Dict[str, Any]:
        """Start Telegram authentication process."""
        try:
            # Create a temporary client for authentication
            session_name = f"auth_temp_{phone_number.replace('+', '').replace(' ', '')}"
            client = Client(
                session_name,
                api_id=api_id,
                api_hash=api_hash,
                phone_number=phone_number,
                in_memory=True  # Don't save session to disk yet
            )
            
            # Start the client and send code
            await client.connect()
            sent_code = await client.send_code(phone_number)
            
            # Store temporary client for later use
            temp_session_key = f"temp_auth_{phone_number}"
            self.active_clients[temp_session_key] = client
            
            return {
                'success': True,
                'phone_code_hash': sent_code.phone_code_hash,
                'next_type': sent_code.type.name if sent_code.type else None,
                'session_key': temp_session_key
            }
            
        except PhoneNumberInvalid:
            return {'success': False, 'error': '電話號碼格式無效'}
        except Exception as e:
            logger.error(f"Failed to start auth process: {e}")
            return {'success': False, 'error': f'驗證過程啟動失敗: {str(e)}'}
    
    async def verify_code(self, session_key: str, phone_code: str, 
                         phone_code_hash: str) -> Dict[str, Any]:
        """Verify phone code and complete authentication."""
        try:
            if session_key not in self.active_clients:
                return {'success': False, 'error': '會話已過期，請重新開始'}
            
            client = self.active_clients[session_key]
            
            try:
                # Try to sign in with the code
                user = await client.sign_in(
                    client.phone_number,
                    phone_code_hash,
                    phone_code
                )
                
                # Authentication successful
                return await self._complete_authentication(client, user)
                
            except SessionPasswordNeeded:
                # 2FA is enabled, need password
                return {
                    'success': True,
                    'requires_password': True,
                    'session_key': session_key
                }
                
        except PhoneCodeInvalid:
            return {'success': False, 'error': '驗證碼無效'}
        except PhoneCodeExpired:
            return {'success': False, 'error': '驗證碼已過期，請重新發送'}
        except Exception as e:
            logger.error(f"Failed to verify code: {e}")
            return {'success': False, 'error': f'驗證碼驗證失敗: {str(e)}'}
    
    async def verify_password(self, session_key: str, password: str) -> Dict[str, Any]:
        """Verify 2FA password."""
        try:
            if session_key not in self.active_clients:
                return {'success': False, 'error': '會話已過期，請重新開始'}
            
            client = self.active_clients[session_key]
            
            try:
                user = await client.check_password(password)
                return await self._complete_authentication(client, user)
                
            except PasswordHashInvalid:
                return {'success': False, 'error': '密碼錯誤'}
            except Exception as e:
                logger.error(f"Password verification failed: {e}")
                return {'success': False, 'error': f'密碼驗證失敗: {str(e)}'}
                
        except Exception as e:
            logger.error(f"Failed to verify password: {e}")
            return {'success': False, 'error': str(e)}
    
    async def _complete_authentication(self, client: Client, user) -> Dict[str, Any]:
        """Complete authentication process and save user data."""
        try:
            # Get user information
            user_id = str(user.id)
            username = user.username
            first_name = user.first_name
            last_name = user.last_name
            phone_number = client.phone_number
            
            # Export session string for future use
            session_string = await client.export_session_string()
            
            # Save session string in memory and to file
            self.user_sessions[user_id] = session_string
            self._save_sessions()
            
            # Store authenticated client under user_id
            self.active_clients[user_id] = client
            
            # Clean up temporary client (but don't disconnect the current client)
            temp_keys_to_remove = [key for key in self.active_clients.keys() if key.startswith('temp_auth_')]
            for key in temp_keys_to_remove:
                try:
                    temp_client = self.active_clients[key]
                    if temp_client != client:  # Don't disconnect the client we just authenticated
                        await temp_client.disconnect()
                    del self.active_clients[key]
                except:
                    pass
            
            return {
                'success': True,
                'user_id': user_id,
                'username': username,
                'first_name': first_name,
                'last_name': last_name,
                'phone_number': phone_number,
                'user_info': {
                    'user_id': user_id,
                    'username': username,
                    'first_name': first_name,
                    'last_name': last_name,
                    'phone_number': phone_number
                }
            }
            
        except Exception as e:
            logger.error(f"Failed to complete authentication: {e}")
            return {'success': False, 'error': f'完成驗證失敗: {str(e)}'}
    
    async def get_user_client(self, user_id: str) -> Optional[Client]:
        """Get authenticated Telegram client for user."""
        try:
            # Check if client is already active
            if user_id in self.active_clients:
                client = self.active_clients[user_id]
                if client.is_connected:
                    return client
            
            # Load client from session string
            session_string = self.user_sessions.get(user_id)
            
            if not session_string:
                return None
            
            # Get API credentials from global app
            import utils
            from module.app import Application
            app_config_path = "config.yaml"
            app_data_path = "data.yaml"
            temp_app = Application(app_config_path, app_data_path, "temp")
            temp_app.load_config()
            
            # Create client from session string
            client = Client(
                f"user_{user_id}",
                api_id=int(temp_app.api_id),
                api_hash=temp_app.api_hash,
                session_string=session_string
            )
            
            try:
                await client.start()
                self.active_clients[user_id] = client
                return client
            except AuthKeyUnregistered:
                # Session is invalid, remove it
                self.user_sessions.pop(user_id, None)
                return None
            except Exception as e:
                logger.error(f"Failed to start client for user {user_id}: {e}")
                return None
                
        except Exception as e:
            logger.error(f"Failed to get client for user {user_id}: {e}")
            return None
    
    async def sync_user_groups(self, user_id: str) -> Dict[str, Any]:
        """Sync user's Telegram groups."""
        try:
            client = await self.get_user_client(user_id)
            if not client:
                return {'success': False, 'error': '無法獲取用戶的Telegram連接'}
            
            groups = []
            async for dialog in client.get_dialogs():
                chat = dialog.chat
                if chat.type.name in ['GROUP', 'SUPERGROUP', 'CHANNEL']:
                    groups.append({
                        'id': chat.id,
                        'title': chat.title,
                        'type': chat.type.name.lower(),
                        'username': chat.username,
                        'members_count': getattr(chat, 'members_count', 0)
                    })
            
            # Return groups (no database storage for now)
            return {
                'success': True,
                'groups_count': len(groups),
                'groups': groups
            }
            
        except Exception as e:
            logger.error(f"Failed to sync groups for user {user_id}: {e}")
            return {'success': False, 'error': str(e)}
    
    async def get_user_groups(self, session_key: str) -> list:
        """Get user's groups from session key."""
        try:
            logger.info(f"Getting groups for session_key: {session_key}")
            logger.info(f"Active clients keys: {list(self.active_clients.keys())}")
            
            # Extract user_id from session key or active clients
            user_id = None
            if session_key in self.active_clients:
                logger.info(f"Found session_key in active_clients")
                # Find user_id by client
                for uid, client in self.active_clients.items():
                    if uid.isdigit() and client == self.active_clients[session_key]:
                        user_id = uid
                        logger.info(f"Found matching user_id: {user_id}")
                        break
            
            # Try to find user_id among active clients by checking all numeric keys
            if not user_id:
                logger.info("Checking all active clients for user connections")
                for uid in self.active_clients.keys():
                    if uid.isdigit():
                        logger.info(f"Found potential user_id: {uid}")
                        user_id = uid
                        break
            
            if not user_id:
                logger.info("No user_id found, trying temp auth session")
                # Get from temp auth session
                temp_client = self.active_clients.get(session_key)
                if temp_client:
                    logger.info("Found temp client, getting user info")
                    # Get user info to identify user_id
                    me = await temp_client.get_me()
                    user_id = str(me.id)
                    logger.info(f"Got user_id from temp client: {user_id}")
            
            if not user_id:
                logger.warning("No user_id found, returning empty groups")
                return []
            
            client = await self.get_user_client(user_id)
            if not client:
                logger.info("No stored client found, using temp client")
                # Use temp client if available
                client = self.active_clients.get(session_key)
                
            if not client:
                logger.error("No client available for groups fetching")
                return []
            
            logger.info("Fetching dialogs from Telegram...")
            groups = []
            async for dialog in client.get_dialogs():
                chat = dialog.chat
                if chat.type.name in ['GROUP', 'SUPERGROUP', 'CHANNEL']:
                    groups.append({
                        'id': str(chat.id),
                        'title': chat.title,
                        'type': chat.type.name.lower(),
                        'username': chat.username,
                        'members_count': getattr(chat, 'members_count', 0),
                        'has_media': True  # Assume all groups can have media
                    })
            
            logger.info(f"Found {len(groups)} groups")
            # Log first few groups for debugging
            for i, group in enumerate(groups[:3]):
                logger.info(f"Group {i+1}: {group['title']} ({group['id']})")
            return groups
            
        except Exception as e:
            logger.error(f"Failed to get user groups: {e}")
            return []
    
    async def get_group_messages(self, session_key: str, chat_id: str, 
                                limit: int = 50, offset_id: int = 0, media_only: bool = False) -> Dict[str, Any]:
        """Get messages from a specific group."""
        try:
            logger.info(f"Getting messages for chat_id: {chat_id}, session_key: {session_key}")
            logger.info(f"Active clients keys: {list(self.active_clients.keys())}")
            
            # Get client from session key
            client = self.active_clients.get(session_key)
            if not client:
                logger.info("No client found for session_key, trying to find user client")
                # Try to find user_id and get client
                user_id = None
                for uid in self.active_clients.keys():
                    if uid.isdigit():
                        user_id = uid
                        client = self.active_clients[uid]
                        logger.info(f"Using client for user_id: {user_id}")
                        break
                
                if not client:
                    logger.error("No client available for messages fetching")
                    return {'success': False, 'error': '無法獲取用戶的Telegram連接'}
            
            messages = []
            try:
                async for message in client.get_chat_history(
                    int(chat_id), 
                    limit=limit, 
                    offset_id=offset_id
                ):
                    # Skip messages without media or text
                    if not (message.media or message.text):
                        continue
                    
                    # Apply media_only filter
                    if media_only and not message.media:
                        continue
                    
                    msg_data = {
                        'message_id': message.id,
                        'text': message.text[:500] if message.text else '',  # Limit text length
                        'date': message.date.isoformat() if message.date else None,
                        'media_type': None,
                        'file_name': None,
                        'file_size': None,
                        'file_unique_id': None,
                        'caption': message.caption[:300] if message.caption else ''
                    }
                    
                    # Extract media information
                    if message.media:
                        if message.photo:
                            msg_data['media_type'] = 'photo'
                            msg_data['file_unique_id'] = message.photo.file_unique_id
                        elif message.video:
                            msg_data['media_type'] = 'video'
                            msg_data['file_name'] = message.video.file_name or f"video_{message.id}.mp4"
                            msg_data['file_size'] = message.video.file_size
                            msg_data['file_unique_id'] = message.video.file_unique_id
                        elif message.audio:
                            msg_data['media_type'] = 'audio'
                            msg_data['file_name'] = message.audio.file_name or f"audio_{message.id}.mp3"
                            msg_data['file_size'] = message.audio.file_size
                            msg_data['file_unique_id'] = message.audio.file_unique_id
                        elif message.document:
                            msg_data['media_type'] = 'document'
                            msg_data['file_name'] = message.document.file_name or f"document_{message.id}"
                            msg_data['file_size'] = message.document.file_size
                            msg_data['file_unique_id'] = message.document.file_unique_id
                        elif message.voice:
                            msg_data['media_type'] = 'voice'
                            msg_data['file_name'] = f"voice_{message.id}.ogg"
                            msg_data['file_size'] = message.voice.file_size
                            msg_data['file_unique_id'] = message.voice.file_unique_id
                        elif message.animation:
                            msg_data['media_type'] = 'animation'
                            msg_data['file_name'] = message.animation.file_name or f"animation_{message.id}.gif"
                            msg_data['file_size'] = message.animation.file_size
                            msg_data['file_unique_id'] = message.animation.file_unique_id
                        elif message.sticker:
                            msg_data['media_type'] = 'sticker'
                            msg_data['file_name'] = f"sticker_{message.id}.webp"
                            msg_data['file_size'] = message.sticker.file_size
                            msg_data['file_unique_id'] = message.sticker.file_unique_id
                    
                    messages.append(msg_data)
                    
            except Exception as e:
                logger.error(f"Failed to get messages from chat {chat_id}: {e}")
                return {'success': False, 'error': f'獲取訊息失敗: {str(e)}'}
            
            # Note: Cache messages functionality requires user_id, so we skip it for now
            # message_repo = self.db_manager.group_message_repo
            # if messages:
            #     message_repo.cache_messages(user_id, chat_id, messages)
            
            return {
                'success': True,
                'messages': messages,
                'count': len(messages)
            }
            
        except Exception as e:
            logger.error(f"Failed to get group messages: {e}")
            return {'success': False, 'error': str(e)}
    
    async def disconnect_session(self, session_key: str):
        """Disconnect and clean up a specific session."""
        try:
            if session_key in self.active_clients:
                client = self.active_clients[session_key]
                if client.is_connected:
                    await client.disconnect()
                del self.active_clients[session_key]
                logger.info(f"Disconnected session: {session_key}")
        except Exception as e:
            logger.error(f"Failed to disconnect session {session_key}: {e}")
    
    def cleanup_session(self, session_key: str):
        """Clean up temporary authentication session."""
        if session_key in self.active_clients:
            try:
                client = self.active_clients[session_key]
                asyncio.create_task(client.disconnect())
                del self.active_clients[session_key]
            except:
                pass

    def _load_sessions(self):
        """Load user sessions from file."""
        try:
            import json
            import os
            if os.path.exists(self.sessions_file):
                with open(self.sessions_file, 'r') as f:
                    data = json.load(f)
                    self.user_sessions = data.get('user_sessions', {})
                    logger.info(f"Loaded {len(self.user_sessions)} user sessions from file")
        except Exception as e:
            logger.error(f"Failed to load sessions from file: {e}")

    def _save_sessions(self):
        """Save user sessions to file."""
        try:
            import json
            data = {
                'user_sessions': self.user_sessions,
                'timestamp': datetime.now().isoformat()
            }
            with open(self.sessions_file, 'w') as f:
                json.dump(data, f, indent=2)
            logger.info(f"Saved {len(self.user_sessions)} user sessions to file")
        except Exception as e:
            logger.error(f"Failed to save sessions to file: {e}")


# Global auth manager instance
_auth_manager: Optional[TelegramAuthManager] = None


def get_auth_manager() -> TelegramAuthManager:
    """Get or create global auth manager instance."""
    global _auth_manager
    if _auth_manager is None:
        _auth_manager = TelegramAuthManager()
    return _auth_manager


def require_auth(f):
    """Decorator to require user authentication for API endpoints."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        try:
            # Check session from different sources
            session_id = None
            
            # Try to get from Authorization header
            auth_header = request.headers.get('Authorization', '')
            if auth_header.startswith('Bearer '):
                session_id = auth_header[7:]
            
            # Try to get from session cookie
            if not session_id:
                session_id = session.get('session_id')
            
            # Try to get from request JSON
            if not session_id and request.is_json:
                session_id = request.json.get('session_id')
            
            if not session_id:
                return jsonify({'success': False, 'error': '需要登入', 'auth_required': True}), 401
            
            # Validate session
            db_manager = get_multiuser_db_manager()
            user_id = db_manager.user_session_repo.validate_session(session_id)
            
            if not user_id:
                return jsonify({'success': False, 'error': '會話已過期', 'auth_required': True}), 401
            
            # Add user_id to request context
            request.current_user_id = user_id
            
            return f(*args, **kwargs)
            
        except Exception as e:
            logger.error(f"Auth check failed: {e}")
            return jsonify({'success': False, 'error': '驗證失敗'}), 500
    
    return decorated_function


def get_current_user_id() -> Optional[str]:
    """Get current authenticated user ID from request context."""
    return getattr(request, 'current_user_id', None)