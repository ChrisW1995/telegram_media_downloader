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
        logger.info("🎯 TelegramAuthManager.__init__ - NEW VERSION WITH UPDATE HANDLER!")
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
            logger.info(f"Available user sessions: {list(self.user_sessions.keys())}")

            # Extract user_id from session key
            user_id = None

            # First, check if session_key is already a user_id (numeric)
            if session_key.isdigit() and session_key in self.user_sessions:
                user_id = session_key
                logger.info(f"Session key is user_id: {user_id}")

            # If still no user_id, check active clients
            if not user_id and session_key in self.active_clients:
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

            # 使用 Telegram 原生 API 獲取對話列表
            from pyrogram.raw.functions.messages import GetDialogs
            from pyrogram.raw.types import InputPeerEmpty

            offset_date = 0
            offset_id = 0
            offset_peer = InputPeerEmpty()
            limit = 100

            while True:
                try:
                    # 使用原生 API 呼叫
                    dialogs = await client.invoke(
                        GetDialogs(
                            offset_date=offset_date,
                            offset_id=offset_id,
                            offset_peer=offset_peer,
                            limit=limit,
                            hash=0
                        )
                    )

                    if not dialogs.dialogs:
                        break

                    # 建立 chat 字典以便快速查找
                    chats_dict = {}
                    for chat in dialogs.chats:
                        chats_dict[chat.id] = chat

                    # 處理每個對話
                    for dialog in dialogs.dialogs:
                        try:
                            peer = dialog.peer
                            chat_id = None

                            # 根據 peer 類型獲取 chat_id
                            if hasattr(peer, 'channel_id'):
                                chat_id = peer.channel_id
                            elif hasattr(peer, 'chat_id'):
                                chat_id = peer.chat_id
                            else:
                                continue  # 跳過私人對話

                            # 從字典中獲取 chat 對象
                            chat = chats_dict.get(chat_id)
                            if not chat:
                                continue

                            # 檢查 chat 類型,跳過 forbidden 和私人對話
                            chat_type_name = type(chat).__name__

                            if 'Forbidden' in chat_type_name or 'User' in chat_type_name:
                                logger.debug(f"Skipping {chat_type_name}: {chat_id}")
                                continue

                            # 判斷是否為群組/頻道
                            if chat_type_name in ['Channel', 'Chat']:
                                # 獲取標題
                                title = getattr(chat, 'title', 'Unknown')

                                # 判斷類型
                                if chat_type_name == 'Channel':
                                    if getattr(chat, 'broadcast', False):
                                        type_str = 'channel'
                                    else:
                                        type_str = 'supergroup'
                                else:
                                    type_str = 'group'

                                # 轉換 ID (頻道需要加上 -100 前綴)
                                if chat_type_name == 'Channel':
                                    display_id = str(-1000000000000 - chat_id)
                                else:
                                    display_id = str(-chat_id)

                                logger.info(f"Adding {type_str}: {title} ({display_id})")
                                groups.append({
                                    'id': display_id,
                                    'title': title,
                                    'type': type_str,
                                    'username': getattr(chat, 'username', None),
                                    'members_count': getattr(chat, 'participants_count', 0),
                                    'has_media': True
                                })

                        except Exception as dialog_error:
                            logger.warning(f"Error processing dialog: {dialog_error}")
                            continue

                    # 準備下一次請求的 offset
                    if dialogs.dialogs:
                        last_dialog = dialogs.dialogs[-1]
                        last_message = None
                        for msg in dialogs.messages:
                            if msg.id == last_dialog.top_message:
                                last_message = msg
                                break

                        if last_message:
                            offset_date = last_message.date
                            offset_id = last_message.id
                            offset_peer = last_dialog.peer
                        else:
                            break
                    else:
                        break

                    # 如果返回的對話數少於 limit,說明已經沒有更多了
                    if len(dialogs.dialogs) < limit:
                        break

                except Exception as e:
                    logger.error(f"Error fetching dialogs batch: {e}")
                    break

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
            seen_group_ids = set()  # 記錄已經見過的 media_group_id
            group_count = 0  # 記錄群組數量

            try:
                async for message in client.get_chat_history(
                    int(chat_id),
                    limit=limit * 3,  # 載入更多訊息以確保能獲得足夠的群組
                    offset_id=offset_id
                ):
                    # Skip messages without media or text
                    if not (message.media or message.text):
                        continue

                    # Apply media_only filter
                    if media_only and not message.media:
                        continue

                    # 檢查是否達到群組數量限制
                    media_group_id = message.media_group_id
                    if media_group_id:
                        # 有 media_group_id 的訊息
                        if media_group_id not in seen_group_ids:
                            seen_group_ids.add(media_group_id)
                            group_count += 1
                    else:
                        # 沒有 media_group_id 的訊息，每則算一個群組
                        group_count += 1

                    # 如果已經達到指定的群組數量，記錄訊息後停止
                    if group_count > limit:
                        break

                    msg_data = {
                        'message_id': message.id,
                        'text': message.text[:500] if message.text else '',  # Limit text length
                        'date': message.date.isoformat() if message.date else None,
                        'media_type': None,
                        'file_name': None,
                        'file_size': None,
                        'file_unique_id': None,
                        'caption': message.caption[:300] if message.caption else '',
                        'thumbnail_url': None,
                        'duration': None,
                        'width': None,
                        'height': None,
                        'media_group_id': media_group_id  # 添加媒體組 ID
                    }
                    
                    # Extract media information
                    if message.media:
                        if message.photo:
                            msg_data['media_type'] = 'photo'
                            msg_data['file_unique_id'] = message.photo.file_unique_id
                            msg_data['width'] = message.photo.width
                            msg_data['height'] = message.photo.height
                            # 添加縮圖信息
                            if message.photo.thumbs:
                                # 獲取最小的縮圖作為預覽
                                smallest_thumb = min(message.photo.thumbs, key=lambda x: x.file_size)
                                # 創建縮圖 URL，指向我們的縮圖 API
                                msg_data['thumbnail_url'] = f'/api/thumbnails/{chat_id}/{message.id}'
                                msg_data['thumbnail'] = {
                                    'file_id': smallest_thumb.file_id,
                                    'file_unique_id': smallest_thumb.file_unique_id,
                                    'width': smallest_thumb.width,
                                    'height': smallest_thumb.height,
                                    'file_size': smallest_thumb.file_size
                                }
                        elif message.video:
                            msg_data['media_type'] = 'video'
                            msg_data['file_name'] = message.video.file_name or f"video_{message.id}.mp4"
                            msg_data['file_size'] = message.video.file_size
                            msg_data['file_unique_id'] = message.video.file_unique_id
                            msg_data['duration'] = message.video.duration
                            msg_data['width'] = message.video.width
                            msg_data['height'] = message.video.height
                            # 添加縮圖信息
                            if message.video.thumbs:
                                # 獲取最小的縮圖作為預覽
                                smallest_thumb = min(message.video.thumbs, key=lambda x: x.file_size)
                                # 創建縮圖 URL，指向我們的縮圖 API
                                msg_data['thumbnail_url'] = f'/api/thumbnails/{chat_id}/{message.id}'
                                msg_data['thumbnail'] = {
                                    'file_id': smallest_thumb.file_id,
                                    'file_unique_id': smallest_thumb.file_unique_id,
                                    'width': smallest_thumb.width,
                                    'height': smallest_thumb.height,
                                    'file_size': smallest_thumb.file_size
                                }
                        elif message.audio:
                            msg_data['media_type'] = 'audio'
                            msg_data['file_name'] = message.audio.file_name or f"audio_{message.id}.mp3"
                            msg_data['file_size'] = message.audio.file_size
                            msg_data['file_unique_id'] = message.audio.file_unique_id
                            msg_data['duration'] = message.audio.duration
                        elif message.document:
                            msg_data['media_type'] = 'document'
                            msg_data['file_name'] = message.document.file_name or f"document_{message.id}"
                            msg_data['file_size'] = message.document.file_size
                            msg_data['file_unique_id'] = message.document.file_unique_id
                            # Check if document is actually a video or gif
                            if message.document.mime_type and 'video' in message.document.mime_type:
                                msg_data['media_type'] = 'animation' if 'gif' in message.document.mime_type else 'video'
                        elif message.voice:
                            msg_data['media_type'] = 'voice'
                            msg_data['file_name'] = f"voice_{message.id}.ogg"
                            msg_data['file_size'] = message.voice.file_size
                            msg_data['file_unique_id'] = message.voice.file_unique_id
                            msg_data['duration'] = message.voice.duration
                        elif message.animation:
                            msg_data['media_type'] = 'animation'
                            msg_data['file_name'] = message.animation.file_name or f"animation_{message.id}.gif"
                            msg_data['file_size'] = message.animation.file_size
                            msg_data['file_unique_id'] = message.animation.file_unique_id
                            msg_data['width'] = message.animation.width
                            msg_data['height'] = message.animation.height
                        elif message.sticker:
                            msg_data['media_type'] = 'sticker'
                            msg_data['file_name'] = f"sticker_{message.id}.webp"
                            msg_data['file_size'] = message.sticker.file_size
                            msg_data['file_unique_id'] = message.sticker.file_unique_id
                            msg_data['width'] = message.sticker.width
                            msg_data['height'] = message.sticker.height
                    
                    messages.append(msg_data)

            except Exception as e:
                logger.error(f"Failed to get messages from chat {chat_id}: {e}")
                return {'success': False, 'error': f'獲取訊息失敗: {str(e)}'}

            # 判斷是否還有更多訊息
            has_more = group_count > limit

            logger.info(f"載入完成: {len(messages)} 則訊息，{group_count} 個群組")

            return {
                'success': True,
                'messages': messages,
                'count': len(messages),
                'group_count': group_count,
                'has_more': has_more
            }
            
        except Exception as e:
            logger.error(f"Failed to get group messages: {e}")
            return {'success': False, 'error': str(e)}

    async def get_media_statistics(self, session_key: str, chat_id: str) -> Dict[str, Any]:
        """獲取群組的媒體類型統計"""
        try:
            logger.info(f"Getting media statistics for chat_id: {chat_id}")

            # Get client from session key
            client = self.active_clients.get(session_key)
            if not client:
                # Try to find user client
                for uid in self.active_clients.keys():
                    if uid.isdigit():
                        client = self.active_clients[uid]
                        break

                if not client:
                    return {'success': False, 'error': '無法獲取用戶的Telegram連接'}

            # Initialize statistics
            stats = {
                'photo': 0,
                'video': 0,
                'audio': 0,
                'document': 0,
                'voice': 0,
                'animation': 0,
                'total': 0
            }

            # Scan recent messages (limit to 1000 for performance)
            async for message in client.get_chat_history(int(chat_id), limit=1000):
                stats['total'] += 1

                if message.media:
                    if message.photo:
                        stats['photo'] += 1
                    elif message.video:
                        stats['video'] += 1
                    elif message.audio:
                        stats['audio'] += 1
                    elif message.voice:
                        stats['voice'] += 1
                    elif message.animation:
                        stats['animation'] += 1
                    elif message.document:
                        stats['document'] += 1

            return {
                'success': True,
                'stats': stats
            }

        except Exception as e:
            logger.error(f"Failed to get media statistics: {e}")
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
                client_data = self.active_clients[session_key]
                # Handle both old format (direct client) and new format (dict with client)
                if isinstance(client_data, dict):
                    client = client_data.get('client')
                else:
                    client = client_data

                if client:
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

    async def start_qr_login(self, api_id: int, api_hash: str) -> Dict[str, Any]:
        """Start QR code login process with proper update handler."""
        logger.info("🚀 DEBUG: start_qr_login called - code is loaded!")
        try:
            import uuid
            import base64
            import time
            import asyncio
            from pyrogram.raw.functions.auth import ExportLoginToken
            from pyrogram.raw.types.auth import LoginToken
            from pyrogram import handlers

            session_key = str(uuid.uuid4())

            # Create client for QR login
            client = Client(
                name=f"qr_session_{session_key}",
                api_id=api_id,
                api_hash=api_hash,
                in_memory=True
            )

            # Start client and get QR login token
            await client.connect()

            # Add update handler for login token updates
            login_event = asyncio.Event()
            login_result = {'authenticated': False, 'user_info': None}

            async def handle_update(client, update):
                logger.info(f"🔍 Received update: {type(update).__name__}")
                logger.debug(f"Update details: {update}")

                # Check for updateLoginToken specifically
                update_class_name = type(update).__name__

                # Check for various login-related update types
                if 'LoginToken' in update_class_name or 'updateLoginToken' in update_class_name:
                    logger.info(f"📱 Received LoginToken update! Triggering second ExportLoginToken")
                    try:
                        # Wait a moment for the token to be processed
                        await asyncio.sleep(1)

                        # Trigger second ExportLoginToken as per Telegram docs
                        second_result = await client.invoke(
                            ExportLoginToken(
                                api_id=api_id,
                                api_hash=api_hash,
                                except_ids=[]
                            )
                        )
                        logger.info(f"📄 Second ExportLoginToken result: {type(second_result).__name__}")

                        # Check if we got LoginTokenSuccess
                        from pyrogram.raw.types.auth import LoginTokenSuccess
                        if isinstance(second_result, LoginTokenSuccess):
                            logger.info(f"🎉 QR login successful! Got LoginTokenSuccess")

                            # Get user info after successful authorization
                            me = await client.get_me()

                            if me:
                                user_id = str(me.id)
                                logger.info(f"👤 QR login successful for user: {user_id}")

                                # Save session string for future use
                                session_string = await client.export_session_string()
                                self.user_sessions[user_id] = session_string
                                self._save_sessions()

                                # Store result for retrieval
                                login_result['authenticated'] = True
                                login_result['user_info'] = {
                                    'id': me.id,
                                    'user_id': user_id,
                                    'first_name': me.first_name,
                                    'last_name': me.last_name,
                                    'username': me.username,
                                    'phone_number': me.phone_number
                                }

                                # Move client to permanent storage
                                self.active_clients[user_id] = client

                                # Signal completion
                                login_event.set()
                                logger.info(f"✅ Login event signaled for user {user_id}")

                        else:
                            logger.info(f"⚠️ Second ExportLoginToken did not return LoginTokenSuccess, got: {type(second_result).__name__}")

                    except Exception as e:
                        logger.error(f"❌ Error in update handler: {e}")
                        import traceback
                        logger.error(f"Full traceback: {traceback.format_exc()}")

                # Try to detect any authorization-related updates
                elif ('auth' in update_class_name.lower() or
                      'Auth' in update_class_name or
                      hasattr(update, 'authorization') or
                      hasattr(update, 'user')):
                    logger.info(f"🔐 Received authorization-related update: {update_class_name}")
                    try:
                        # Try to get user info
                        me = await client.get_me()
                        if me:
                            user_id = str(me.id)
                            logger.info(f"👤 Direct authorization successful for user: {user_id}")

                            # Save session string for future use
                            session_string = await client.export_session_string()
                            self.user_sessions[user_id] = session_string
                            self._save_sessions()

                            # Store result for retrieval
                            login_result['authenticated'] = True
                            login_result['user_info'] = {
                                'id': me.id,
                                'user_id': user_id,
                                'first_name': me.first_name,
                                'last_name': me.last_name,
                                'username': me.username,
                                'phone_number': me.phone_number
                            }

                            # Move client to permanent storage
                            self.active_clients[user_id] = client

                            # Signal completion
                            login_event.set()
                            logger.info(f"✅ Direct authorization completed for user {user_id}")

                    except Exception as e:
                        logger.debug(f"Not an actual authorization update: {e}")
                else:
                    logger.debug(f"🔄 Ignoring update type: {update_class_name}")

            # Add the update handler
            client.add_handler(handlers.RawUpdateHandler(handle_update))

            # Export login token using Telegram API
            login_token = await client.invoke(
                ExportLoginToken(
                    api_id=api_id,
                    api_hash=api_hash,
                    except_ids=[]
                )
            )

            if isinstance(login_token, LoginToken):
                # Encode token to base64url format for QR code
                token_b64 = base64.urlsafe_b64encode(login_token.token).decode('ascii').rstrip('=')
                qr_url = f"tg://login?token={token_b64}"

                # Store the client and token temporarily
                self.active_clients[session_key] = {
                    'client': client,
                    'token': login_token.token,
                    'expires': login_token.expires,
                    'login_event': login_event,
                    'login_result': login_result,
                    'api_id': api_id,
                    'api_hash': api_hash
                }

                logger.info(f"QR login started for session: {session_key}")
                logger.info(f"Token expires at: {login_token.expires} (current: {time.time()})")
                logger.info(f"Update handler added, waiting for user interaction")

                return {
                    'success': True,
                    'session_key': session_key,
                    'qr_token': qr_url
                }
            else:
                await client.disconnect()
                return {'success': False, 'error': 'Failed to get login token'}

        except Exception as e:
            logger.error(f"Failed to start QR login: {e}")
            return {'success': False, 'error': str(e)}

    async def check_qr_status(self, session_key: str) -> Dict[str, Any]:
        """Check QR code login status with enhanced detection."""
        try:
            logger.info(f"Checking QR status for session: {session_key}")
            logger.info(f"Active clients: {list(self.active_clients.keys())}")

            if session_key not in self.active_clients:
                logger.info(f"Session {session_key} not found in active clients")
                return {'success': False, 'error': 'QR session not found'}

            client_data = self.active_clients[session_key]
            client = client_data['client']

            # Check if token has expired
            import time
            current_time = time.time()
            expires_time = client_data['expires']
            logger.debug(f"Current time: {current_time}, Expires: {expires_time}")

            if current_time > expires_time:
                # Clean up expired session
                logger.info(f"QR session {session_key} expired")
                await client.disconnect()
                del self.active_clients[session_key]
                return {'success': True, 'expired': True}

            # Check if login was completed via the event handler
            login_result = client_data.get('login_result', {})

            if login_result.get('authenticated'):
                logger.info(f"QR login completed via update handler!")
                user_info = login_result.get('user_info', {})
                user_id = user_info.get('user_id')

                # Clean up temporary session
                if session_key in self.active_clients:
                    del self.active_clients[session_key]

                return {
                    'success': True,
                    'authenticated': True,
                    'user_id': user_id,
                    'user_info': user_info
                }

            # ENHANCED: Proactively check for authorization using multiple methods
            try:
                logger.info("🔍 Proactively checking for QR authorization...")

                # Method 1: Try to get user info (if authorized, this will succeed)
                try:
                    me = await client.get_me()
                    if me:
                        logger.info(f"🎉 QR login detected via get_me()! User: {me.id}")

                        # Save session and user info
                        user_id = str(me.id)
                        session_string = await client.export_session_string()
                        self.user_sessions[user_id] = session_string
                        self._save_sessions()

                        # Store client permanently
                        self.active_clients[user_id] = client

                        # Clean up temp session
                        if session_key in self.active_clients:
                            del self.active_clients[session_key]

                        return {
                            'success': True,
                            'authenticated': True,
                            'user_id': user_id,
                            'user_info': {
                                'id': me.id,
                                'user_id': user_id,
                                'first_name': me.first_name,
                                'last_name': me.last_name,
                                'username': me.username,
                                'phone_number': me.phone_number
                            }
                        }
                except Exception as auth_check_error:
                    logger.debug(f"get_me() check failed (expected if not authorized): {auth_check_error}")

                # Method 2: Try second ExportLoginToken as per Telegram docs
                try:
                    from pyrogram.raw.functions.auth import ExportLoginToken
                    from pyrogram.raw.types.auth import LoginTokenSuccess

                    logger.info("🔄 Attempting second ExportLoginToken check...")
                    second_result = await client.invoke(
                        ExportLoginToken(
                            api_id=client_data.get('api_id', client.api_id),
                            api_hash=client_data.get('api_hash', client.api_hash),
                            except_ids=[]
                        )
                    )

                    if isinstance(second_result, LoginTokenSuccess):
                        logger.info(f"🎉 QR login successful via second ExportLoginToken!")

                        # Get user info after successful authorization
                        me = await client.get_me()
                        if me:
                            user_id = str(me.id)
                            logger.info(f"👤 QR login successful for user: {user_id}")

                            # Save session string for future use
                            session_string = await client.export_session_string()
                            self.user_sessions[user_id] = session_string
                            self._save_sessions()

                            # Store client permanently
                            self.active_clients[user_id] = client

                            # Clean up temporary session
                            if session_key in self.active_clients:
                                del self.active_clients[session_key]

                            return {
                                'success': True,
                                'authenticated': True,
                                'user_id': user_id,
                                'user_info': {
                                    'id': me.id,
                                    'user_id': user_id,
                                    'first_name': me.first_name,
                                    'last_name': me.last_name,
                                    'username': me.username,
                                    'phone_number': me.phone_number
                                }
                            }
                    else:
                        logger.debug(f"Second ExportLoginToken not yet successful: {type(second_result)}")

                except Exception as token_check_error:
                    logger.debug(f"Second ExportLoginToken check failed (expected if not authorized): {token_check_error}")

            except Exception as enhanced_check_error:
                logger.debug(f"Enhanced authorization check failed: {enhanced_check_error}")

            # Fallback: Check client connection status
            if not client.is_connected:
                logger.info(f"Client disconnected for session {session_key}")
                self.cleanup_session(session_key)
                return {
                    'success': True,
                    'authenticated': False,
                    'expired': True
                }

            # Still waiting for user to scan/approve
            return {
                'success': True,
                'authenticated': False,
                'expired': False
            }

        except Exception as e:
            logger.error(f"Failed to check QR status: {e}")
            return {'success': False, 'error': str(e)}


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