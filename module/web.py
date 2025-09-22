"""web ui for media download"""

import logging
import os
import threading

from flask import Flask, jsonify, render_template, request, session
from flask_login import LoginManager, UserMixin, login_required, login_user
from flask_cors import CORS
from loguru import logger

import utils
from module.app_db import DatabaseApplication as Application
from module.download_stat import (
    DownloadState,
    get_download_result,
    get_download_state,
    get_total_download_speed,
    set_download_state,
)
from utils.crypto import AesBase64
from utils.format import format_byte

log = logging.getLogger("werkzeug")
log.setLevel(logging.ERROR)

_flask_app = Flask(__name__)
CORS(_flask_app)

_flask_app.secret_key = "tdl"
# Configure persistent sessions (30 days)
from datetime import timedelta
_flask_app.permanent_session_lifetime = timedelta(days=30)
_login_manager = LoginManager()
_login_manager.login_view = "login"
_login_manager.init_app(_flask_app)
web_login_users: dict = {}
deAesCrypt = AesBase64("1234123412ABCDEF", "ABCDEF1234123412")

# Telegram authentication state
telegram_auth_state = {
    "needs_auth": False,
    "waiting_for_phone": False,
    "waiting_for_code": False,
    "waiting_for_password": False,
    "phone_number": None,
    "verification_code": None,
    "password": None,
    "error_message": None,
    "auth_complete": False
}

# 全局錯誤狀態追蹤
telegram_error_state = {
    "auth_key_unregistered": False,
    "last_error_time": None,
    "error_count": 0
}


class User(UserMixin):
    """Web Login User"""

    def __init__(self):
        self.sid = "root"

    @property
    def id(self):
        """ID"""
        return self.sid


@_login_manager.user_loader
def load_user(_):
    """
    Load a user object from the user ID.

    Returns:
        User: The user object.
    """
    return User()


def get_flask_app() -> Flask:
    """get flask app instance"""
    return _flask_app


def run_web_server(app: Application):
    """
    Runs a web server using the Flask framework.
    """

    get_flask_app().run(
        app.web_host, app.web_port, debug=app.debug_web, use_reloader=False
    )


# 全域變數存儲Application實例
_app = None
_client = None
_queue = None

# pylint: disable = W0603
def init_web(app: Application, client=None, queue=None):
    """
    Set the value of the users variable.

    Args:
        users: The list of users to set.
        client: Pyrogram client instance.
        queue: Download queue reference.

    Returns:
        None.
    """
    global web_login_users, _app, _client, _queue
    _app = app  # 設置全域app實例
    _client = client  # 設置全域client實例
    _queue = queue  # 設置全域queue實例
    
    if app.web_login_secret:
        web_login_users = {"root": app.web_login_secret}
    else:
        _flask_app.config["LOGIN_DISABLED"] = True
    if app.debug_web:
        threading.Thread(target=run_web_server, args=(app,)).start()
    else:
        threading.Thread(
            target=get_flask_app().run, daemon=True, args=(app.web_host, app.web_port)
        ).start()


@_flask_app.route("/login", methods=["GET", "POST"])
def login():
    """
    Function to handle the login route.

    Parameters:
    - No parameters

    Returns:
    - If the request method is "POST" and the username and
      password match the ones in the web_login_users dictionary,
      it returns a JSON response with a code of "1".
    - Otherwise, it returns a JSON response with a code of "0".
    - If the request method is not "POST", it returns the rendered "login.html" template.
    """
    if request.method == "POST":
        username = "root"
        web_login_form = {}
        for key, value in request.form.items():
            if value:
                value = deAesCrypt.decrypt(value)
            web_login_form[key] = value

        if not web_login_form.get("password"):
            return jsonify({"code": "0"})

        password = web_login_form["password"]
        if username in web_login_users and web_login_users[username] == password:
            user = User()
            login_user(user)
            return jsonify({"code": "1"})

        return jsonify({"code": "0"})

    return render_template("login.html")


@_flask_app.route("/")
@login_required
def index():
    """Index html"""
    return render_template(
        "index.html",
        download_state=(
            "pause" if get_download_state() is DownloadState.Downloading else "continue"
        ),
    )


@_flask_app.route("/fast_test")
@login_required
def fast_test():
    """Fast Test 獨立頁面"""
    return render_template("fast_test.html")


@_flask_app.route("/api/get_user_groups")
@login_required
def get_user_groups():
    """獲取用戶群組列表 - 用於Fast Test頁面"""
    try:
        # 使用配置文件中的群組資訊
        groups = [
            {'chat_id': str(chat_id), 'name': group_name}
            for chat_id, group_name in _app.config['custom_downloads']['group_tags'].items()
        ]
            
        return jsonify({
            'success': True,
            'groups': groups
        })
            
    except Exception as e:
        logger.error(f"獲取用戶群組失敗: {e}")
        return jsonify({
            'success': False, 
            'message': f'獲取群組失敗: {str(e)}'
        })


@_flask_app.route("/api/get_group_messages")
@login_required
def get_fast_test_group_messages():
    """獲取群組訊息 - 用於Fast Test頁面"""
    try:
        chat_id = request.args.get('chat_id')
        if not chat_id:
            return jsonify({'success': False, 'message': '缺少chat_id參數'})
            
        # 使用現有的multiuser_auth模塊獲取訊息
        if hasattr(_app, 'auth_manager') and _app.auth_manager:
            # 創建一個臨時session_key (使用第一個可用的用戶ID)
            temp_session_key = None
            if hasattr(_app.auth_manager, 'active_clients') and _app.auth_manager.active_clients:
                temp_session_key = f"temp_auth_{list(_app.auth_manager.active_clients.keys())[0]}"
            
            if temp_session_key:
                try:
                    # 獲取群組訊息
                    messages_data = _app.auth_manager.get_group_messages(chat_id, temp_session_key)
                    
                    if messages_data and 'messages' in messages_data:
                        return jsonify({
                            'success': True,
                            'messages': messages_data['messages']
                        })
                    else:
                        return jsonify({
                            'success': False,
                            'message': '無法獲取訊息'
                        })
                        
                except Exception as e:
                    logger.error(f"獲取群組訊息錯誤: {e}")
                    return jsonify({
                        'success': False,
                        'message': f'獲取訊息失敗: {str(e)}'
                    })
            else:
                return jsonify({
                    'success': False,
                    'message': '沒有有效的認證會話'
                })
        else:
            return jsonify({
                'success': False,
                'message': '認證管理器未初始化'
            })
            
    except Exception as e:
        logger.error(f"獲取群組訊息API錯誤: {e}")
        return jsonify({
            'success': False,
            'message': f'API錯誤: {str(e)}'
        })


@_flask_app.route("/api/add_fast_download_tasks", methods=["POST"])
@login_required
def add_fast_test_download_tasks():
    """添加快速下載任務 - 用於Fast Test頁面"""
    try:
        data = request.get_json()
        chat_id = data.get('chat_id')
        message_ids = data.get('message_ids', [])
        
        logger.info(f"Fast Test API called with chat_id: {chat_id}, message_ids: {message_ids}")
        
        if not chat_id or not message_ids:
            return jsonify({
                'success': False,
                'message': '缺少必要參數'
            })
        
        # 獲取現有的配置
        if not _app.config.get('custom_downloads'):
            _app.config['custom_downloads'] = {'enable': True, 'group_tags': {}, 'target_ids': {}}
        
        # 確保target_ids存在
        if 'target_ids' not in _app.config['custom_downloads']:
            _app.config['custom_downloads']['target_ids'] = {}
        
        # 獲取該群組現有的message_ids
        existing_ids = set(_app.config['custom_downloads']['target_ids'].get(chat_id, []))
        logger.info(f"Existing message IDs for {chat_id}: {existing_ids}")
        
        # 添加新的message_ids，過濾掉已存在的
        new_ids = []
        for msg_id in message_ids:
            if msg_id not in existing_ids:
                new_ids.append(msg_id)
                existing_ids.add(msg_id)
        
        if new_ids:
            # 更新配置
            _app.config['custom_downloads']['target_ids'][chat_id] = list(existing_ids)
            
            # 保存配置到數據庫
            _app.update_config()
            
            logger.info(f"Added {len(new_ids)} new download tasks for chat {chat_id}")
            
            return jsonify({
                'success': True,
                'message': f'已新增 {len(new_ids)} 個下載任務',
                'added_count': len(new_ids),
                'total_count': len(existing_ids)
            })
        else:
            logger.info("All selected messages are already in the download queue")
            return jsonify({
                'success': True,
                'message': '所選訊息已在下載佇列中',
                'added_count': 0,
                'total_count': len(existing_ids)
            })
            
    except Exception as e:
        logger.error(f"Failed to add fast download tasks: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'message': f'添加下載任務失敗: {str(e)}'
        })


@_flask_app.route("/get_download_status")
@login_required
def get_download_speed():
    """Get download speed"""
    return (
        '{ "download_speed" : "'
        + format_byte(get_total_download_speed())
        + '/s" , "upload_speed" : "0.00 B/s" } '
    )


@_flask_app.route("/set_download_state", methods=["POST"])
@login_required
def web_set_download_state():
    """Set download state"""
    state = request.args.get("state")

    if state == "continue" and get_download_state() is DownloadState.StopDownload:
        set_download_state(DownloadState.Downloading)
        return "continue"

    if state == "pause" and get_download_state() is DownloadState.Downloading:
        set_download_state(DownloadState.StopDownload)
        return "pause"
        
    if state == "cancel":
        set_download_state(DownloadState.Cancelled)
        # Reset download progress when cancelled
        global download_progress, active_download_session
        download_progress['completed_count'] = 0
        download_progress['total_count'] = 0
        download_progress['active'] = False
        download_progress['current_files'] = {}
        active_download_session['active'] = False
        active_download_session['total_tasks'] = 0
        return "cancelled"

    return state


@_flask_app.route("/get_download_state")
def get_download_state_api():
    """Get current download state"""
    current_state = get_download_state()
    state_map = {
        DownloadState.Downloading: "downloading",
        DownloadState.StopDownload: "paused", 
        DownloadState.Cancelled: "cancelled",
        DownloadState.Completed: "completed",
        DownloadState.Idle: "idle"
    }
    return state_map.get(current_state, "idle")

@_flask_app.route("/get_app_version")
def get_app_version():
    """Get telegram_media_downloader version"""
    return utils.__version__


@_flask_app.route("/get_download_list")
@login_required
def get_download_list():
    """get download list"""
    if request.args.get("already_down") is None:
        return "[]"

    already_down = request.args.get("already_down") == "true"

    download_result = get_download_result()
    result = "["
    for chat_id, messages in download_result.items():
        for idx, value in messages.items():
            is_already_down = value["down_byte"] == value["total_size"]

            if already_down and not is_already_down:
                continue

            if result != "[":
                result += ","
            download_speed = format_byte(value["download_speed"]) + "/s"
            result += (
                '{ "chat":"'
                + f"{chat_id}"
                + '", "id":"'
                + f"{idx}"
                + '", "filename":"'
                + os.path.basename(value["file_name"])
                + '", "total_size":"'
                + f'{format_byte(value["total_size"])}'
                + '" ,"download_progress":"'
            )
            result += (
                f'{round(value["down_byte"] / value["total_size"] * 100, 1)}'
                + '" ,"download_speed":"'
                + download_speed
                + '" ,"save_path":"'
                + value["file_name"].replace("\\", "/")
                + '"}'
            )

    result += "]"
    return result


@_flask_app.route("/get_groups")
@login_required
def get_groups():
    """獲取群組列表和自訂下載配置"""
    try:
        print("=== get_groups API called ===")
        print(f"_app.config: {getattr(_app, 'config', None)}")
        groups = []
        
        # 從配置中獲取群組資訊
        if hasattr(_app, 'config') and 'custom_downloads' in _app.config:
            custom_config = _app.config['custom_downloads']
            group_tags = custom_config.get('group_tags', {})
            target_ids = custom_config.get('target_ids', {})
            
            for chat_id, tag in group_tags.items():
                pending_count = len(target_ids.get(chat_id, []))
                groups.append({
                    'chat_id': chat_id,
                    'name': tag,
                    'pending_count': pending_count
                })
        
        # 也從chat配置中獲取群組（只添加不在group_tags中的）
        if hasattr(_app, 'config') and 'chat' in _app.config:
            custom_config = _app.config.get('custom_downloads', {})
            group_tags = custom_config.get('group_tags', {})
            target_ids = custom_config.get('target_ids', {})
            
            chat_configs = _app.config.get('chat', [])
            if isinstance(chat_configs, list):
                for chat_config in chat_configs:
                    chat_id = str(chat_config.get('chat_id', ''))
                    # 只有當群組不在group_tags中且不在現有groups列表中時才添加
                    if chat_id not in group_tags and not any(g['chat_id'] == chat_id for g in groups):
                        pending_count = len(target_ids.get(chat_id, []))
                        groups.append({
                            'chat_id': chat_id,
                            'name': f'Chat {chat_id}',
                            'pending_count': pending_count
                        })
        
        print(f"Returning groups: {groups}")
        return jsonify({'success': True, 'groups': groups})
    except Exception as e:
        print(f"ERROR in get_groups: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)})


@_flask_app.route("/add_group", methods=["POST"])
@login_required
def add_group():
    """新增群組"""
    try:
        data = request.get_json()
        chat_id = data.get('chat_id')
        name = data.get('name', f'Chat {chat_id}')
        
        if not chat_id:
            return jsonify({'success': False, 'error': '請提供 Chat ID'})
        
        # 初始化配置
        if not hasattr(_app, 'config') or 'custom_downloads' not in _app.config:
            _app.config['custom_downloads'] = {'enable': True, 'target_ids': {}, 'group_tags': {}}
        
        # 添加群組標籤
        _app.config['custom_downloads']['group_tags'][chat_id] = name
        
        # 確保 target_ids 有這個群組
        if chat_id not in _app.config['custom_downloads']['target_ids']:
            _app.config['custom_downloads']['target_ids'][chat_id] = []
        
        # 保存配置
        _app.update_config()
        
        return jsonify({
            'success': True, 
            'message': f'已新增群組 "{name}" (ID: {chat_id})',
            'group': {'chat_id': chat_id, 'name': name, 'pending_count': 0}
        })
    except Exception as e:
        print(f"ERROR in add_group: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)})


@_flask_app.route("/edit_group", methods=["POST"])
@login_required
def edit_group():
    """編輯群組名稱"""
    try:
        data = request.get_json()
        chat_id = data.get('chat_id')
        new_name = data.get('name')
        
        if not chat_id or not new_name:
            return jsonify({'success': False, 'error': '請提供 Chat ID 和新名稱'})
        
        # 初始化配置
        if not hasattr(_app, 'config') or 'custom_downloads' not in _app.config:
            _app.config['custom_downloads'] = {'enable': True, 'target_ids': {}, 'group_tags': {}}
        
        # 更新群組標籤
        _app.config['custom_downloads']['group_tags'][chat_id] = new_name
        
        # 保存配置
        _app.update_config()
        
        return jsonify({
            'success': True, 
            'message': f'已更新群組名稱為 "{new_name}"'
        })
    except Exception as e:
        print(f"ERROR in edit_group: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)})


@_flask_app.route("/delete_group", methods=["POST"])
@login_required
def delete_group():
    """刪除群組"""
    try:
        data = request.get_json()
        chat_id = data.get('chat_id')
        
        if not chat_id:
            return jsonify({'success': False, 'error': '請提供 Chat ID'})
        
        # 初始化配置
        if not hasattr(_app, 'config') or 'custom_downloads' not in _app.config:
            return jsonify({'success': False, 'error': '群組不存在'})
        
        # 刪除群組標籤和目標IDs
        if 'group_tags' in _app.config['custom_downloads']:
            _app.config['custom_downloads']['group_tags'].pop(chat_id, None)
        if 'target_ids' in _app.config['custom_downloads']:
            _app.config['custom_downloads']['target_ids'].pop(chat_id, None)
        
        # 保存配置
        _app.update_config()
        
        return jsonify({
            'success': True, 
            'message': f'已刪除群組 (ID: {chat_id})'
        })
    except Exception as e:
        print(f"ERROR in delete_group: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)})


@_flask_app.route("/delete_multiple_groups", methods=["POST"])
@login_required
def delete_multiple_groups():
    """批量刪除群組"""
    try:
        data = request.get_json()
        chat_ids = data.get('chat_ids', [])
        
        if not chat_ids:
            return jsonify({'success': False, 'error': '請選擇要刪除的群組'})
        
        # 初始化配置
        if not hasattr(_app, 'config') or 'custom_downloads' not in _app.config:
            return jsonify({'success': False, 'error': '沒有群組可刪除'})
        
        deleted_count = 0
        for chat_id in chat_ids:
            # 刪除群組標籤和目標IDs
            if 'group_tags' in _app.config['custom_downloads']:
                if _app.config['custom_downloads']['group_tags'].pop(chat_id, None):
                    deleted_count += 1
            if 'target_ids' in _app.config['custom_downloads']:
                _app.config['custom_downloads']['target_ids'].pop(chat_id, None)
        
        # 保存配置
        _app.update_config()
        
        return jsonify({
            'success': True, 
            'message': f'已刪除 {deleted_count} 個群組'
        })
    except Exception as e:
        print(f"ERROR in delete_multiple_groups: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)})


@_flask_app.route("/clear_multiple_groups", methods=["POST"])
@login_required
def clear_multiple_groups():
    """批量清空群組訊息"""
    try:
        data = request.get_json()
        chat_ids = data.get('chat_ids', [])
        
        if not chat_ids:
            return jsonify({'success': False, 'error': '請選擇要清空的群組'})
        
        # 初始化配置
        if not hasattr(_app, 'config') or 'custom_downloads' not in _app.config:
            return jsonify({'success': False, 'error': '沒有群組可清空'})
        
        cleared_count = 0
        total_messages = 0
        for chat_id in chat_ids:
            if 'target_ids' in _app.config['custom_downloads'] and chat_id in _app.config['custom_downloads']['target_ids']:
                message_count = len(_app.config['custom_downloads']['target_ids'][chat_id])
                total_messages += message_count
                _app.config['custom_downloads']['target_ids'][chat_id] = []
                cleared_count += 1
        
        # 保存配置
        _app.update_config()
        
        return jsonify({
            'success': True, 
            'message': f'已清空 {cleared_count} 個群組的 {total_messages} 條訊息'
        })
    except Exception as e:
        print(f"ERROR in clear_multiple_groups: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)})


@_flask_app.route("/check_group_access", methods=["POST"])
@login_required
def check_group_access():
    """檢查群組訪問權限"""
    try:
        data = request.get_json()
        chat_id = data.get('chat_id')
        
        if not chat_id:
            return jsonify({'success': False, 'error': '請提供 Chat ID'})
        
        if not _client:
            return jsonify({'success': False, 'error': '客戶端未初始化'})
        
        # 使用事件循環檢查群組訪問權限
        async def check_access():
            try:
                chat_info = await _client.get_chat(int(chat_id))
                return {
                    'accessible': True,
                    'title': chat_info.title if hasattr(chat_info, 'title') else 'Unknown',
                    'type': str(chat_info.type) if hasattr(chat_info, 'type') else 'Unknown',
                    'members_count': chat_info.members_count if hasattr(chat_info, 'members_count') else 'Unknown'
                }
            except Exception as e:
                return {
                    'accessible': False,
                    'error': str(e)
                }
        
        if hasattr(_app, 'loop') and _app.loop:
            import asyncio
            result = asyncio.run_coroutine_threadsafe(check_access(), _app.loop).result(timeout=10)
        else:
            return jsonify({'success': False, 'error': '事件循環不可用'})
        
        return jsonify({
            'success': True,
            'chat_id': chat_id,
            'accessible': result['accessible'],
            'info': result
        })
        
    except Exception as e:
        print(f"ERROR in check_group_access: {e}")
        return jsonify({'success': False, 'error': str(e)})

@_flask_app.route("/get_group_details", methods=["POST"])
@login_required
def get_group_details():
    """獲取群組詳細資訊"""
    try:
        data = request.get_json()
        chat_id = data.get('chat_id')
        
        if not chat_id:
            return jsonify({'success': False, 'error': '請提供 Chat ID'})
        
        # 從配置中獲取群組資訊
        group_info = None
        if hasattr(_app, 'config') and 'custom_downloads' in _app.config:
            custom_config = _app.config['custom_downloads']
            group_tags = custom_config.get('group_tags', {})
            target_ids = custom_config.get('target_ids', {})
            
            if chat_id in group_tags:
                pending_count = len(target_ids.get(chat_id, []))
                group_info = {
                    'chat_id': chat_id,
                    'name': group_tags[chat_id],
                    'pending_count': pending_count,
                    'created_time': 'Unknown',
                    'last_activity': 'Unknown'
                }
        
        if not group_info:
            return jsonify({'success': False, 'error': '群組不存在'})
        
        return jsonify({
            'success': True, 
            'group': group_info
        })
    except Exception as e:
        print(f"ERROR in get_group_details: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)})


@_flask_app.route("/add_custom_download", methods=["POST"])
@login_required
def add_custom_download():
    """添加自訂下載任務"""
    try:
        print("=== add_custom_download API called ===")
        print(f"Request data: {request.get_json()}")
        data = request.get_json()
        chat_id = data.get('chat_id')
        message_ids_text = data.get('message_ids', '')
        
        if not chat_id or not message_ids_text:
            return jsonify({'success': False, 'error': '群組ID和訊息ID不能為空'})
        
        # 解析訊息ID
        message_ids = []
        for line in message_ids_text.strip().split('\n'):
            line = line.strip()
            if not line:
                continue
                
            # 處理逗號分隔的ID
            for part in line.split(','):
                part = part.strip()
                if '-' in part and part.count('-') == 1:
                    # 處理範圍 (例如: 123-130)
                    try:
                        start, end = map(int, part.split('-'))
                        message_ids.extend(range(start, end + 1))
                    except ValueError:
                        return jsonify({'success': False, 'error': f'無效的範圍格式: {part}'})
                else:
                    # 處理單個ID
                    try:
                        message_ids.append(int(part))
                    except ValueError:
                        return jsonify({'success': False, 'error': f'無效的訊息ID: {part}'})
        
        if not message_ids:
            return jsonify({'success': False, 'error': '沒有有效的訊息ID'})
        
        # 添加到配置中
        if not hasattr(_app, 'config'):
            _app.config = {}
        if 'custom_downloads' not in _app.config:
            _app.config['custom_downloads'] = {'enable': True, 'target_ids': {}, 'group_tags': {}}
        
        current_ids = _app.config['custom_downloads']['target_ids'].get(chat_id, [])
        # 去重並添加新的ID
        new_ids = list(set(current_ids + message_ids))
        _app.config['custom_downloads']['target_ids'][chat_id] = sorted(new_ids)
        
        # 記錄新添加的項目
        global newly_added_items
        for msg_id in message_ids:
            newly_added_items.add((chat_id, msg_id))
        
        # 更新配置文件
        _app.update_config()
        print(f"Config updated. Current target_ids: {_app.config.get('custom_downloads', {}).get('target_ids', {})}")
        
        # 不自動觸發下載，讓使用者手動控制
        download_message = f'成功添加 {len(message_ids)} 個訊息ID到下載隊列，請手動啟動下載'
        
        return jsonify({
            'success': True, 
            'message': download_message,
            'added_count': len(message_ids),
            'total_count': len(new_ids)
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@_flask_app.route("/clear_auto_select", methods=["POST"])
@login_required
def clear_auto_select():
    """清除自動選取標記"""
    try:
        # 這個API不需要做任何事情，因為auto_select標記是動態生成的
        # 只要用戶刷新頁面或重新載入歷史，標記就會消失
        return jsonify({'success': True, 'message': '已清除自動選取標記'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@_flask_app.route("/clean_downloaded_from_targets", methods=["POST"])
@login_required
def clean_downloaded_from_targets():
    """清理已下載項目從target_ids中"""
    try:
        print("=== clean_downloaded_from_targets API called ===")
        
        # 讀取下載歷史
        history_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'custom_download_history.yaml')
        downloaded_items = set()
        
        if os.path.exists(history_file):
            import yaml
            with open(history_file, 'r', encoding='utf-8') as f:
                history_data = yaml.safe_load(f) or {}
            downloaded_ids = history_data.get('downloaded_ids', {})
            for chat_id, ids in downloaded_ids.items():
                for msg_id in ids:
                    downloaded_items.add((chat_id, msg_id))
        
        # 清理target_ids
        if hasattr(_app, 'config') and 'custom_downloads' in _app.config:
            target_ids = _app.config['custom_downloads'].get('target_ids', {})
            updated_target_ids = {}
            removed_count = 0
            
            for chat_id, message_ids in target_ids.items():
                remaining_ids = []
                for msg_id in message_ids:
                    if (chat_id, msg_id) not in downloaded_items:
                        remaining_ids.append(msg_id)
                    else:
                        removed_count += 1
                        print(f"Removing downloaded item from target_ids: {chat_id}:{msg_id}")
                
                if remaining_ids:
                    updated_target_ids[chat_id] = remaining_ids
            
            # 更新配置
            _app.config['custom_downloads']['target_ids'] = updated_target_ids
            _app.update_config()
            
            return jsonify({
                'success': True,
                'message': f'已清理 {removed_count} 個已下載項目',
                'removed_count': removed_count
            })
        
        return jsonify({'success': False, 'error': '沒有找到配置'})
        
    except Exception as e:
        print(f"ERROR in clean_downloaded_from_targets: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)})


@_flask_app.route("/get_all_groups")
@login_required 
def get_all_groups():
    """獲取所有可用的群組名稱（用於篩選）"""
    try:
        all_groups = set()
        
        # 從config中獲取群組標籤
        if hasattr(_app, 'config') and 'custom_downloads' in _app.config:
            group_tags = _app.config['custom_downloads'].get('group_tags', {})
            all_groups.update(group_tags.values())
        
        return jsonify({
            'success': True,
            'groups': sorted(list(all_groups))
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@_flask_app.route("/get_download_history")
@login_required
def get_download_history():
    """獲取下載歷史"""
    try:
        print("=== get_download_history API called ===")
        print(f"_app: {_app}")
        print(f"_app.config: {getattr(_app, 'config', None)}")
        # 獲取分頁參數
        page = int(request.args.get('page', 1))
        limit = int(request.args.get('limit', 50))  # 默認每頁50條
        offset = (page - 1) * limit
        
        # 獲取篩選參數
        group_filter = request.args.get('group_filter', '')
        status_filter = request.args.get('status_filter', '')
        
        # Check if this is a force refresh request (after download completion)
        force_refresh = request.args.get('_t', '')
        if force_refresh and _app:
            # Force reload config to get the latest target_ids
            print(f"Force refresh requested with timestamp: {force_refresh}")
            try:
                _app.load_config()
                print("Config reloaded successfully")
            except Exception as e:
                print(f"Failed to reload config: {e}")
        
        history = []
        
        # 獲取群組標籤映射
        group_tags = {}
        if hasattr(_app, 'config') and 'custom_downloads' in _app.config:
            group_tags = _app.config['custom_downloads'].get('group_tags', {})
        
        # 從custom_download_history.yaml讀取歷史記錄
        history_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'custom_download_history.yaml')
        if os.path.exists(history_file):
            import yaml
            from datetime import datetime
            try:
                with open(history_file, 'r', encoding='utf-8') as f:
                    history_data = yaml.safe_load(f) or {}
                
                # 獲取文件修改時間作為大致的時間參考
                file_mtime = os.path.getmtime(history_file)
                timestamp = datetime.fromtimestamp(file_mtime).strftime('%Y-%m-%d %H:%M')
                
                # 修正數據結構解析
                for status, chat_data in history_data.items():
                    if isinstance(chat_data, dict):
                        for chat_id, ids in chat_data.items():
                            if isinstance(ids, list):
                                # 獲取群組名稱
                                group_name = group_tags.get(chat_id, f'群組 {chat_id}')
                                
                                for msg_id in ids:
                                    history.append({
                                        'chat_id': chat_id,
                                        'chat_name': group_name,
                                        'message_id': msg_id,
                                        'status': status,
                                        'timestamp': timestamp
                                    })
            except Exception as e:
                print(f"讀取歷史文件錯誤: {e}")
        
        # 添加配置文件中的待下載項目
        if hasattr(_app, 'config') and 'custom_downloads' in _app.config:
            target_ids = _app.config['custom_downloads'].get('target_ids', {})
            print(f"Found target_ids in config: {target_ids}")
            
            # 創建目標項目集合
            target_items = set()
            for chat_id, message_ids in target_ids.items():
                for msg_id in message_ids:
                    target_items.add((chat_id, msg_id))
            
            # 讀取下載歷史以檢查哪些項目已經下載
            downloaded_items = set()
            failed_items = set()
            if os.path.exists(history_file):
                try:
                    import yaml
                    with open(history_file, 'r', encoding='utf-8') as f:
                        history_data = yaml.safe_load(f) or {}
                    downloaded_ids = history_data.get('downloaded_ids', {})
                    failed_ids = history_data.get('failed_ids', {})
                    for chat_id, ids in downloaded_ids.items():
                        for msg_id in ids:
                            downloaded_items.add((chat_id, msg_id))
                    for chat_id, ids in failed_ids.items():
                        for msg_id in ids:
                            failed_items.add((chat_id, msg_id))
                except Exception as e:
                    print(f"Error reading download history: {e}")
            
            # 更新現有歷史項目的狀態
            for item in history:
                item_key = (item['chat_id'], item['message_id'])
                if item_key in target_items:
                    # 檢查實際下載狀態，不要強制覆蓋為pending
                    if item_key in downloaded_items:
                        # 已下載，但在target_ids中 - 可能是要重新下載
                        from datetime import datetime
                        current_time = datetime.now().strftime('%Y-%m-%d %H:%M')
                        item['status'] = 'pending'
                        item['timestamp'] = f'重新加入佇列 - {current_time}'
                        item['add_time'] = datetime.now().timestamp()
                    elif item_key in failed_items:
                        # 失敗，但在target_ids中 - 標記為重試
                        from datetime import datetime
                        current_time = datetime.now().strftime('%Y-%m-%d %H:%M')
                        item['status'] = 'pending'
                        item['timestamp'] = f'準備重試 - {current_time}'
                        item['add_time'] = datetime.now().timestamp()
                    else:
                        # 新加入的項目
                        from datetime import datetime
                        current_time = datetime.now().strftime('%Y-%m-%d %H:%M')
                        item['status'] = 'pending'
                        item['timestamp'] = f'加入佇列 - {current_time}'
                        item['add_time'] = datetime.now().timestamp()
                    
                    # 檢查是否為新添加的項目或待下載項目
                    global newly_added_items
                    item['auto_select'] = (item_key in newly_added_items) or (item['status'] == 'pending')
                    print(f"Updated item: {item['chat_id']}:{item['message_id']} -> {item['status']}")
            
            # 添加不在歷史中的新項目
            existing_items = set()
            for item in history:
                existing_items.add((item['chat_id'], item['message_id']))
            
            for chat_id, message_ids in target_ids.items():
                group_name = group_tags.get(chat_id, f'群組 {chat_id}')
                for msg_id in message_ids:
                    if (chat_id, msg_id) not in existing_items:
                        # 檢查是否已經下載
                        if (chat_id, msg_id) in downloaded_items:
                            # 已下載，但不在歷史列表中，添加為已下載狀態
                            history.append({
                                'chat_id': chat_id,
                                'chat_name': group_name,
                                'message_id': msg_id,
                                'status': 'downloaded_ids',
                                'timestamp': timestamp
                            })
                            print(f"Added downloaded item to history: {chat_id}:{msg_id}")
                        elif (chat_id, msg_id) in failed_items:
                            # 失敗的項目，添加為失敗狀態
                            history.append({
                                'chat_id': chat_id,
                                'chat_name': group_name,
                                'message_id': msg_id,
                                'status': 'failed_ids',
                                'timestamp': timestamp
                            })
                            print(f"Added failed item to history: {chat_id}:{msg_id}")
                        else:
                            # 未下載，添加為待下載，使用當前時間戳確保顯示在前面
                            from datetime import datetime
                            current_time = datetime.now().strftime('%Y-%m-%d %H:%M')
                            history.append({
                                'chat_id': chat_id,
                                'chat_name': group_name,
                                'message_id': msg_id,
                                'status': 'pending',
                                'timestamp': f'加入佇列 - {current_time}',
                                'add_time': datetime.now().timestamp(),  # 用於排序
                                'auto_select': True  # pending 狀態的項目總是自動選取
                            })
                            print(f"Added new pending item: {chat_id}:{msg_id}")
        
        # 排序規則：
        # 1. 狀態優先級：pending(待下載) > failed(失敗) > downloaded(已下載)
        # 2. 對於 pending 狀態：最新加入的在最前面（add_time降序）
        # 3. 對於其他狀態：message_id 降序排列
        status_priority = {'pending': 0, 'failed_ids': 1, 'failed': 1, 'downloaded_ids': 2, 'downloaded': 2}
        
        def sort_key(x):
            status_pri = status_priority.get(x['status'], 3)
            if x['status'] == 'pending' and 'add_time' in x:
                # pending 狀態按加入時間降序（新的在前）
                return (status_pri, -x['add_time'])
            else:
                # 其他狀態按 message_id 降序
                return (status_pri, -int(x['message_id']) if str(x['message_id']).isdigit() else 0)
        
        # 應用篩選條件
        if group_filter or status_filter:
            filtered_history = []
            for item in history:
                show_item = True
                
                # 群組篩選
                if group_filter:
                    chat_name = item.get('chat_name', '')
                    if group_filter not in chat_name:
                        show_item = False
                
                # 狀態篩選
                if status_filter and show_item:
                    if status_filter == 'pending' and item.get('status') != 'pending':
                        show_item = False
                    elif status_filter == 'downloaded' and item.get('status') not in ['downloaded', 'downloaded_ids']:
                        show_item = False
                    elif status_filter == 'failed' and item.get('status') not in ['failed', 'failed_ids']:
                        show_item = False
                
                if show_item:
                    filtered_history.append(item)
            
            history = filtered_history
        
        history.sort(key=sort_key)
        
        # 計算總數和分頁
        total = len(history)
        paged_history = history[offset:offset + limit]
        
        return jsonify({
            'success': True, 
            'history': paged_history,
            'pagination': {
                'page': page,
                'limit': limit,
                'total': total,
                'total_pages': (total + limit - 1) // limit
            }
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@_flask_app.route("/clear_download_ids", methods=["POST"])
@login_required
def clear_download_ids():
    """清空指定群組的下載ID"""
    try:
        data = request.get_json()
        chat_id = data.get('chat_id')
        
        if not chat_id:
            return jsonify({'success': False, 'error': '群組ID不能為空'})
        
        if hasattr(_app, 'config') and 'custom_downloads' in _app.config:
            if chat_id in _app.config['custom_downloads'].get('target_ids', {}):
                _app.config['custom_downloads']['target_ids'][chat_id] = []
                _app.update_config()
                return jsonify({'success': True, 'message': '已清空該群組的下載隊列'})
        
        return jsonify({'success': False, 'error': '找不到該群組'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@_flask_app.route("/retry_download", methods=["POST"])
@login_required
def retry_download():
    """重試下載失敗的訊息"""
    try:
        data = request.get_json()
        chat_id = data.get('chat_id')
        message_id = data.get('message_id')
        
        if not chat_id or not message_id:
            return jsonify({'success': False, 'error': '群組ID和訊息ID不能為空'})
        
        # 將失敗的訊息ID重新添加到目標下載列表
        message_id = int(message_id)
        
        if not hasattr(_app, 'config'):
            _app.config = {}
        if 'custom_downloads' not in _app.config:
            _app.config['custom_downloads'] = {'enable': True, 'target_ids': {}, 'group_tags': {}}
        
        current_ids = _app.config['custom_downloads']['target_ids'].get(chat_id, [])
        if message_id not in current_ids:
            current_ids.append(message_id)
            _app.config['custom_downloads']['target_ids'][chat_id] = sorted(current_ids)
            _app.update_config()
        
        # 從失敗列表中移除（如果存在）
        history_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'custom_download_history.yaml')
        if os.path.exists(history_file):
            try:
                import yaml
                with open(history_file, 'r', encoding='utf-8') as f:
                    history_data = yaml.safe_load(f) or {}
                
                failed_ids = history_data.get('failed_ids', {})
                if chat_id in failed_ids and message_id in failed_ids[chat_id]:
                    failed_ids[chat_id].remove(message_id)
                    if not failed_ids[chat_id]:
                        del failed_ids[chat_id]
                    
                    history_data['failed_ids'] = failed_ids
                    with open(history_file, 'w', encoding='utf-8') as f:
                        yaml.dump(history_data, f, default_flow_style=False, allow_unicode=True)
            except Exception as e:
                print(f"Error updating history file: {e}")
        
        # 觸發下載
        download_message = '已將訊息重新加入下載隊列'
        if _client and _queue:
            try:
                from module.custom_download import run_custom_download
                
                # 使用主事件循環
                if hasattr(_app, 'loop') and _app.loop:
                    _app.loop.create_task(run_custom_download(_app, _client, _queue))
                    download_message += '，已開始重試下載'
                    print("Retry download task created in main event loop")
                else:
                    download_message += '，但事件循環不可用'
                    print("ERROR: Main event loop not available for retry")
            except Exception as e:
                download_message += f'，但觸發下載時出現錯誤: {str(e)}'
        
        return jsonify({'success': True, 'message': download_message})
        
    except Exception as e:
        print(f"ERROR in start_custom_download: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)})


@_flask_app.route("/remove_selected_tasks", methods=["POST"])
@login_required
def remove_selected_tasks():
    """從配置中移除選中的任務"""
    try:
        data = request.get_json()
        tasks = data.get('tasks', [])
        
        if not tasks:
            return jsonify({'success': False, 'error': '沒有選擇要移除的項目'})
        
        if not hasattr(_app, 'config') or 'custom_downloads' not in _app.config:
            return jsonify({'success': False, 'error': '沒有配置自訂下載'})
        
        removed_count = 0
        target_ids = _app.config['custom_downloads']['target_ids']
        
        for task in tasks:
            chat_id = task.get('chat_id')
            message_id = int(task.get('message_id'))
            
            if chat_id in target_ids and message_id in target_ids[chat_id]:
                target_ids[chat_id].remove(message_id)
                removed_count += 1
                print(f"Removed task: {chat_id}:{message_id}")
                
                # 如果該聊天室沒有更多ID，刪除該條目
                if not target_ids[chat_id]:
                    del target_ids[chat_id]
        
        # 更新配置文件
        _app.update_config()
        print(f"Removed {removed_count} tasks from config")
        
        return jsonify({
            'success': True,
            'message': f'成功移除 {removed_count} 個項目'
        })
        
    except Exception as e:
        print(f"ERROR in remove_selected_tasks: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)})


@_flask_app.route("/start_selected_download", methods=["POST"])
@login_required
def start_selected_download():
    """啟動選中項目的下載"""
    try:
        print("=== start_selected_download API called ===")
        
        data = request.get_json()
        tasks = data.get('tasks', [])
        
        if not tasks:
            return jsonify({'success': False, 'error': '沒有選擇要下載的項目'})
        
        if not _client or not _queue:
            return jsonify({'success': False, 'error': '客戶端或隊列未初始化'})
        
        # 將選中的任務組織成 target_ids 格式
        selected_target_ids = {}
        for task in tasks:
            chat_id = task.get('chat_id')
            message_id = int(task.get('message_id'))
            
            if chat_id not in selected_target_ids:
                selected_target_ids[chat_id] = []
            selected_target_ids[chat_id].append(message_id)
        
        print(f"Selected target_ids: {selected_target_ids}")
        
        # 使用主事件循環創建自訂下載任務
        try:
            from module.custom_download import run_custom_download_for_selected
            
            if hasattr(_app, 'loop') and _app.loop:
                total_tasks = sum(len(ids) for ids in selected_target_ids.values())
                
                # 清理已選取的項目的auto_select標記
                global newly_added_items
                for chat_id, message_ids in selected_target_ids.items():
                    for msg_id in message_ids:
                        newly_added_items.discard((chat_id, msg_id))
                
                # 設置下載狀態為下載中
                from module.download_stat import set_download_state, DownloadState
                set_download_state(DownloadState.Downloading)
                
                # 初始化進度追蹤
                update_download_progress(0, total_tasks, "開始下載...")
                
                _app.loop.create_task(run_custom_download_for_selected(_app, _client, _queue, selected_target_ids))
                print("Selected download task created in main event loop")
                
                return jsonify({
                    'success': True, 
                    'message': f'已啟動下載，共 {total_tasks} 個選中項目'
                })
            else:
                return jsonify({'success': False, 'error': '事件循環不可用'})
                
        except Exception as e:
            return jsonify({'success': False, 'error': f'啟動下載時出現錯誤: {str(e)}'})
        
    except Exception as e:
        print(f"ERROR in start_selected_download: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)})


# 全局變量來追蹤下載進度
download_progress = {
    'total_count': 0,
    'completed_count': 0,
    'status_text': '準備中...',
    'active': False,
    'current_files': {},  # 改為字典，追蹤多個並發下載
    'current_file': {     # 保留兼容性
        'name': '',
        'downloaded_bytes': 0,
        'total_bytes': 0,
        'download_speed': 0
    }
}

# 全局變數來追蹤新加入的項目（會話期間）
newly_added_items = set()

# 全局變數來追蹤活躍的下載會話
active_download_session = {
    'active': False,
    'session_id': None,
    'start_time': None,
    'target_ids': {},
    'total_tasks': 0
}

@_flask_app.route("/get_download_progress", methods=["GET"])
@login_required
def get_download_progress():
    """獲取當前下載進度"""
    global download_progress
    print(f"Progress API called: {download_progress}")
    
    # 選擇一個活躍的下載作為主要顯示（包括正在下載和剛完成的）
    all_files = [f for f in download_progress['current_files'].values() if f['total_bytes'] > 0]
    active_files = [f for f in all_files if f['downloaded_bytes'] < f['total_bytes']]
    
    if active_files:
        # 優先選擇正在下載的檔案
        main_file = max(active_files, key=lambda x: x['downloaded_bytes'] / max(x['total_bytes'], 1))
        download_progress['current_file'] = main_file
    elif all_files:
        # 如果沒有正在下載的，選擇最近完成的
        main_file = max(all_files, key=lambda x: x['downloaded_bytes'] / max(x['total_bytes'], 1))
        download_progress['current_file'] = main_file
    
    # 獲取總下載速度，參考原始設計
    total_download_speed = format_byte(get_total_download_speed()) + '/s'
    
    return jsonify({
        'success': True,
        'total_count': download_progress['total_count'],
        'completed_count': download_progress['completed_count'],
        'status_text': download_progress['status_text'],
        'active': download_progress['active'],
        'current_file': download_progress['current_file'],
        'current_files': download_progress['current_files'],  # 返回所有並發文件信息
        'concurrent_downloads': len(all_files),  # 新增：顯示所有檔案數量（包括完成的）
        'total_download_speed': total_download_speed,  # 新增：總下載速度
        'session': {
            'active': active_download_session['active'],
            'session_id': active_download_session['session_id'],
            'start_time': active_download_session['start_time'],
            'total_tasks': active_download_session['total_tasks']
        }
    })


def update_download_progress(completed, total, status_text="下載中..."):
    """更新任務總進度"""
    global download_progress, active_download_session
    download_progress['completed_count'] = completed
    download_progress['total_count'] = total
    download_progress['status_text'] = status_text
    print(f"✅ Progress updated: {completed}/{total} - {status_text}")
    
    # 更新會話狀態
    _update_download_session_status(completed, total)


@_flask_app.route("/force_update_progress", methods=["POST"])
@login_required
def force_update_progress():
    """強制更新進度 - 測試用途"""
    try:
        data = request.get_json()
        completed = data.get('completed_count', 0)
        total = data.get('total_count', 0)
        status_text = data.get('status_text', '測試中...')
        
        update_download_progress(completed, total, status_text)
        
        # Also set active to true for testing
        global download_progress
        download_progress['active'] = True
        
        return jsonify({
            'success': True,
            'message': f'Progress forced to {completed}/{total}',
            'current_progress': download_progress
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})


def _update_download_session_status(completed, total):
    """更新下載會話狀態"""
    global download_progress, active_download_session
    download_progress['active'] = completed < total
    
    # 更新會話狀態
    if completed < total and total > 0:
        active_download_session['active'] = True
        active_download_session['total_tasks'] = total
        if not active_download_session['session_id']:
            import time
            active_download_session['session_id'] = str(int(time.time()))
            active_download_session['start_time'] = time.time()
    elif completed >= total and total > 0:
        # 下載完成，設置狀態並清除會話
        from module.download_stat import set_download_state, DownloadState, get_download_state
        if get_download_state() != DownloadState.Cancelled:  # 只有非取消狀態才設為完成
            set_download_state(DownloadState.Completed)
        
        active_download_session['active'] = False
        active_download_session['session_id'] = None
        active_download_session['start_time'] = None
        active_download_session['target_ids'] = {}
        active_download_session['total_tasks'] = 0
    
    print(f"Task session status updated: {completed}/{total} - Active: {download_progress['active']}")


def update_file_progress(file_name="", downloaded_bytes=0, total_bytes=0, download_speed=0, message_id=None):
    """更新當前文件下載進度"""
    global download_progress
    
    # 如果有文件名和message_id，更新並發下載追蹤
    if file_name and message_id:
        file_key = f"{message_id}_{file_name}"
        download_progress['current_files'][file_key] = {
            'name': file_name,
            'downloaded_bytes': downloaded_bytes,
            'total_bytes': total_bytes,
            'download_speed': download_speed,
            'message_id': message_id
        }
        
        # 如果下載完成，標記為完成但保持顯示一會兒
        if downloaded_bytes >= total_bytes and total_bytes > 0:
            download_progress['current_files'][file_key]['completed'] = True
        
        print(f"File progress updated: {file_name} (ID:{message_id}) - {downloaded_bytes}/{total_bytes} bytes @ {download_speed} B/s")
    else:
        # 清空所有進度
        if not file_name:
            download_progress['current_files'].clear()
        
        # 兼容舊的單一文件進度更新


def clear_specific_file_progress(message_id, file_name):
    """清除特定檔案的進度，而不影響其他正在下載的檔案"""
    global download_progress
    file_key = f"{message_id}_{file_name}"
    
    if file_key in download_progress['current_files']:
        del download_progress['current_files'][file_key]
        print(f"Cleared completed file progress: {file_name} (ID:{message_id})")


@_flask_app.route("/test", methods=["GET"])
def test_api():
    """測試API是否正常工作"""
    return jsonify({
        'success': True,
        'message': 'API working',
        'app_available': _app is not None,
        'client_available': _client is not None,
        'queue_available': _queue is not None,
        'config_available': hasattr(_app, 'config') if _app else False
    })


@_flask_app.route("/start_custom_download", methods=["POST"])
@login_required
def start_custom_download():
    """手動啟動自訂下載"""
    try:
        print("=== start_custom_download API called ===")
        print(f"_client: {_client}")
        print(f"_queue: {_queue}")
        print(f"_app: {_app}")
        
        if not _client or not _queue:
            return jsonify({'success': False, 'error': '客戶端或隊列未初始化'})
        
        # 檢查是否有待下載的項目
        if not hasattr(_app, 'config') or 'custom_downloads' not in _app.config:
            return jsonify({'success': False, 'error': '沒有配置自訂下載'})
        
        target_ids = _app.config['custom_downloads'].get('target_ids', {})
        print(f"target_ids: {target_ids}")
        
        if not target_ids:
            return jsonify({'success': False, 'error': '沒有待下載的訊息'})
        
        # 計算待下載數量 (包括失敗的ID作為重試項目)
        total_pending = 0
        from module.custom_download import CustomDownloadManager
        manager = CustomDownloadManager(_app)
        
        # 計算待下載的項目（包含所有target_ids中的項目，允許重新下載）
        pending_downloads = {}
        for chat_id, message_ids in target_ids.items():
            chat_key = str(chat_id)
            pending_for_chat = []
            for msg_id in message_ids:
                # 包含所有target_ids中的項目，包括已下載的（允許重新下載）
                pending_for_chat.append(msg_id)
            if pending_for_chat:
                pending_downloads[chat_key] = pending_for_chat
        
        total_pending = sum(len(ids) for ids in pending_downloads.values())
        
        if total_pending == 0:
            return jsonify({'success': False, 'error': '所有訊息都已成功下載'})
        
        # 觸發下載 - 使用正確的事件循環
        try:
            import asyncio
            from module.custom_download import run_custom_download
            
            # 設置下載狀態為下載中
            from module.download_stat import set_download_state, DownloadState
            set_download_state(DownloadState.Downloading)
            
            # 獲取當前的事件循環並在其中調度任務
            if hasattr(_app, 'loop') and _app.loop:
                # 在主事件循環中創建任務
                _app.loop.create_task(run_custom_download(_app, _client, _queue))
                print("Download task created in main event loop")
            else:
                print("ERROR: Main event loop not available")
            
            return jsonify({
                'success': True, 
                'message': f'已啟動下載，共 {total_pending} 個待下載項目'
            })
        except Exception as e:
            return jsonify({'success': False, 'error': f'啟動下載時出現錯誤: {str(e)}'})
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@_flask_app.route("/check_session_status")
@login_required
def check_session_status():
    """檢查當前Telegram session狀態"""
    try:
        if not _client:
            return jsonify({
                'success': False,
                'valid': False,
                'message': '客戶端未初始化',
                'error': 'CLIENT_NOT_INITIALIZED'
            })
        
        # 檢查客戶端連接狀態
        is_connected = _client.is_connected if hasattr(_client, 'is_connected') else False
        
        if not is_connected:
            return jsonify({
                'success': True,
                'valid': False,
                'message': 'Telegram session已斷開',
                'error': 'SESSION_DISCONNECTED'
            })
        
        # 檢查是否有AUTH_KEY_UNREGISTERED錯誤的跡象
        # 檢查最近的日誌或錯誤狀態
        import os
        import time
        
        # 檢查session文件是否存在且有效
        session_files = [
            "sessions/media_downloader.session",
            "sessions/media_downloader_bot.session"
        ]
        
        valid_session_exists = False
        for session_file in session_files:
            if os.path.exists(session_file):
                # 檢查文件是否不為空且最近修改過
                try:
                    stat = os.stat(session_file)
                    if stat.st_size > 0:
                        valid_session_exists = True
                        break
                except Exception:
                    continue
        
        if not valid_session_exists:
            return jsonify({
                'success': True,
                'valid': False,
                'message': 'Session文件無效或不存在',
                'error': 'SESSION_FILES_INVALID'
            })
        
        # 檢查是否有AUTH_KEY_UNREGISTERED錯誤
        if telegram_error_state["auth_key_unregistered"]:
            return jsonify({
                'success': True,
                'valid': False,
                'message': 'Telegram授權已失效，需要重新驗證',
                'error': 'AUTH_KEY_UNREGISTERED'
            })
        
        # 檢查client的基本屬性來判斷session狀態
        try:
            # 檢查client是否已經有用戶信息
            if hasattr(_client, 'storage') and _client.storage:
                # 檢查storage是否包含session信息
                try:
                    # 檢查是否存在用戶ID (表示已登入)
                    user_id = None
                    is_bot = False
                    
                    # 安全地獲取user_id
                    if hasattr(_client.storage, 'user_id'):
                        try:
                            user_id_attr = getattr(_client.storage, 'user_id')
                            # 如果是方法，調用它
                            if callable(user_id_attr):
                                user_id = user_id_attr()
                            else:
                                user_id = user_id_attr
                        except Exception:
                            user_id = None
                    
                    # 安全地獲取is_bot
                    if hasattr(_client.storage, 'is_bot'):
                        try:
                            is_bot_attr = getattr(_client.storage, 'is_bot')
                            # 如果是方法，調用它
                            if callable(is_bot_attr):
                                is_bot = is_bot_attr()
                            else:
                                is_bot = is_bot_attr
                        except Exception:
                            is_bot = False
                    
                    if user_id:
                        
                        # 確保返回值是可序列化的
                        try:
                            user_id_safe = int(user_id) if user_id else None
                            is_bot_safe = bool(is_bot) if is_bot is not None else False
                        except (ValueError, TypeError):
                            user_id_safe = None
                            is_bot_safe = False
                            
                        return jsonify({
                            'success': True,
                            'valid': True,
                            'message': '連接正常',
                            'user_info': {
                                'id': user_id_safe,
                                'first_name': 'User',
                                'username': None,
                                'is_bot': is_bot_safe
                            }
                        })
                    else:
                        return jsonify({
                            'success': True,
                            'valid': False,
                            'message': 'Session未授權，需要重新登入',
                            'error': 'SESSION_NOT_AUTHORIZED'
                        })
                except Exception as storage_error:
                    return jsonify({
                        'success': True,
                        'valid': False,
                        'message': f'Storage讀取失敗: {str(storage_error)[:100]}',
                        'error': 'STORAGE_ERROR'
                    })
            else:
                return jsonify({
                    'success': False,
                    'valid': False,
                    'message': 'Session storage不可用',
                    'error': 'STORAGE_UNAVAILABLE'
                })
                
        except Exception as check_error:
            return jsonify({
                'success': True,
                'valid': False,
                'message': f'Session狀態檢查失敗: {str(check_error)[:100]}',
                'error': 'SESSION_CHECK_FAILED'
            })
    
    except Exception as e:
        return jsonify({
            'success': False,
            'valid': False,
            'message': f'檢查session狀態時出現錯誤: {str(e)}',
            'error': 'CHECK_FAILED'
        })


@_flask_app.route("/force_reconnect", methods=["POST"])
@login_required  
def force_reconnect():
    """強制重新連接Telegram"""
    try:
        if not _client:
            return jsonify({
                'success': False,
                'message': '客戶端未初始化'
            })
        
        # 使用session manager來清理和重建連接
        try:
            from utils.session_manager import create_session_manager
            
            # 創建session manager
            session_manager = create_session_manager(_app)
            
            # 先停止客戶端並清理session文件
            if _client.is_connected:
                # 使用session manager的安全停止方法
                import asyncio
                if hasattr(_app, 'loop') and _app.loop:
                    try:
                        future = asyncio.run_coroutine_threadsafe(
                            session_manager.safe_client_stop(_client, timeout=10), 
                            _app.loop
                        )
                        stopped = future.result(timeout=15)
                        if not stopped:
                            # 如果正常停止失敗，進行強制清理
                            session_manager.force_cleanup_on_error()
                    except Exception as stop_error:
                        print(f"Client stop error: {stop_error}")
                        session_manager.force_cleanup_on_error()
                else:
                    # 沒有事件循環時，直接進行強制清理
                    session_manager.force_cleanup_on_error()
            
            # 清理任何殘留的session文件
            session_manager.cleanup_stale_sessions()
            
            # 檢查是否需要重新驗證
            import os
            session_files = [
                os.path.join("sessions", "media_downloader.session"),
                os.path.join("sessions", "media_downloader_bot.session")
            ]
            
            # 優先檢查是否有 AUTH_KEY_UNREGISTERED 錯誤
            needs_auth = (telegram_error_state.get("auth_key_unregistered", False) or 
                         not any(os.path.exists(f) for f in session_files))
            
            if needs_auth:
                # 如果有 AUTH_KEY_UNREGISTERED 錯誤，強制刪除無效的 session 文件
                if telegram_error_state.get("auth_key_unregistered", False):
                    for session_file in session_files:
                        if os.path.exists(session_file):
                            try:
                                os.remove(session_file)
                                print(f"Removed invalid session file: {session_file}")
                            except Exception as e:
                                print(f"Failed to remove session file {session_file}: {e}")
                    
                    # 清除錯誤狀態，因為我們即將開始重新認證
                    telegram_error_state.update({
                        "auth_key_unregistered": False,
                        "last_error_time": None,
                        "error_count": 0
                    })
                
                # 設置驗證狀態並返回跳轉指令
                telegram_auth_state.update({
                    "needs_auth": True,
                    "waiting_for_phone": True,
                    "waiting_for_code": False,
                    "waiting_for_password": False,
                    "phone_number": None,
                    "verification_code": None,
                    "password": None,
                    "error_message": None,
                    "auth_complete": False
                })
                
                # 觸發客戶端重新認證流程
                if _client and hasattr(_client, 'web_authorize'):
                    import threading
                    def start_reauth():
                        try:
                            if hasattr(_app, 'loop') and _app.loop:
                                import asyncio
                                future = asyncio.run_coroutine_threadsafe(
                                    _client.web_authorize(), 
                                    _app.loop
                                )
                                # 不等待完成，讓認證在背景進行
                        except Exception as e:
                            print(f"Failed to start reauth: {e}")
                    
                    # 在背景線程中啟動重新認證
                    threading.Thread(target=start_reauth, daemon=True).start()
                
                return jsonify({
                    'success': True,
                    'needs_auth': True,
                    'message': 'Session文件已清理，需要重新驗證Telegram',
                    'redirect_url': '/telegram_auth'
                })
            else:
                return jsonify({
                    'success': True,
                    'needs_auth': False,
                    'message': 'Session文件已清理，請重新啟動應用程序以重新建立連接'
                })
            
        except ImportError:
            # 回退到基本的建議
            return jsonify({
                'success': False,
                'message': '請重新啟動應用程序以修復連接問題'
            })
        except Exception as cleanup_error:
            return jsonify({
                'success': False,
                'message': f'清理過程中出現錯誤，請手動重新啟動應用程序: {str(cleanup_error)[:100]}'
            })
            
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'重新連接時出現錯誤: {str(e)}'
        })


# Telegram Authentication API Endpoints
@_flask_app.route("/api/telegram/auth_status", methods=["GET"])
def get_telegram_auth_status():
    """Get current Telegram authentication status."""
    return jsonify(telegram_auth_state)


@_flask_app.route("/api/telegram/submit_phone", methods=["POST"])
def submit_telegram_phone():
    """Submit phone number for Telegram authentication."""
    global telegram_auth_state, _client, _app
    try:
        data = request.get_json()
        phone_number = data.get("phone_number", "").strip()
        
        if not phone_number:
            return jsonify({"success": False, "error": "請輸入電話號碼"})
        
        # 只更新狀態，讓 HookClient.web_authorize() 處理實際的 API 調用
        telegram_auth_state["phone_number"] = phone_number
        telegram_auth_state["waiting_for_phone"] = False
        telegram_auth_state["waiting_for_code"] = True
        telegram_auth_state["error_message"] = None
        
        return jsonify({"success": True, "message": "電話號碼已提交，正在發送驗證碼..."})
        
    except Exception as e:
        telegram_auth_state["error_message"] = str(e)
        return jsonify({"success": False, "error": str(e)})


@_flask_app.route("/api/telegram/submit_code", methods=["POST"])  
def submit_telegram_code():
    """Submit verification code for Telegram authentication."""
    global telegram_auth_state
    try:
        data = request.get_json()
        verification_code = data.get("verification_code", "").strip()
        
        if not verification_code:
            return jsonify({"success": False, "error": "請輸入驗證碼"})
        
        # 簡單版本：只更新狀態，不直接調用 Pyrogram API
        telegram_auth_state.update({
            "verification_code": verification_code,
            "waiting_for_code": False,
            "error_message": None
        })
        
        return jsonify({"success": True, "message": "驗證碼已提交"})
        
    except Exception as e:
        telegram_auth_state["error_message"] = str(e)
        return jsonify({"success": False, "error": str(e)})


@_flask_app.route("/api/telegram/submit_password", methods=["POST"])
def submit_telegram_password():
    """Submit 2FA password for Telegram authentication."""
    global telegram_auth_state  
    try:
        data = request.get_json()
        password = data.get("password", "").strip()
        
        if not password:
            return jsonify({"success": False, "error": "請輸入兩步驗證密碼"})
        
        telegram_auth_state["password"] = password
        telegram_auth_state["waiting_for_password"] = False
        telegram_auth_state["error_message"] = None
        
        return jsonify({"success": True, "message": "密碼已提交"})
    
    except Exception as e:
        telegram_auth_state["error_message"] = str(e)
        return jsonify({"success": False, "error": str(e)})


@_flask_app.route("/telegram_auth")
def telegram_auth_page():
    """Render Telegram authentication page."""
    return render_template("telegram_auth.html")


@_flask_app.route("/api/telegram/report_error", methods=["POST"])
def report_telegram_error():
    """Report Telegram authentication errors."""
    global telegram_error_state
    import time
    
    try:
        data = request.get_json() or {}
        error_type = data.get("error_type", "")
        
        if error_type == "AUTH_KEY_UNREGISTERED":
            telegram_error_state["auth_key_unregistered"] = True
            telegram_error_state["last_error_time"] = time.time()
            telegram_error_state["error_count"] += 1
            
            return jsonify({
                "success": True,
                "message": "錯誤已記錄"
            })
        
        return jsonify({
            "success": False,
            "message": "未知錯誤類型"
        })
    
    except Exception as e:
        return jsonify({
            "success": False,
            "message": f"報告錯誤失敗: {str(e)}"
        })


@_flask_app.route("/api/telegram/clear_errors", methods=["POST"])
def clear_telegram_errors():
    """Clear Telegram error state."""
    global telegram_error_state
    
    telegram_error_state.update({
        "auth_key_unregistered": False,
        "last_error_time": None,
        "error_count": 0
    })
    
    return jsonify({
        "success": True,
        "message": "錯誤狀態已清除"
    })


@_flask_app.route("/api/telegram/debug_state", methods=["GET"])
def debug_telegram_state():
    """Debug: Get current Telegram error and auth state."""
    global telegram_error_state, telegram_auth_state
    
    return jsonify({
        "error_state": telegram_error_state,
        "auth_state": telegram_auth_state
    })


# =============================================================================
# Multi-user Authentication APIs for Fast Test
# =============================================================================

# Global storage for fast test auth sessions
fast_test_auth_sessions = {}


def run_async_in_thread(coro):
    """Run async coroutine using the app's main event loop"""
    import asyncio
    import concurrent.futures
    
    # Always try to use the app's main event loop
    if hasattr(_app, 'loop') and _app.loop and not _app.loop.is_closed():
        try:
            # Submit coroutine to the app's event loop in a thread-safe way
            future = asyncio.run_coroutine_threadsafe(coro, _app.loop)
            return future.result(timeout=30)  # 30 second timeout
        except Exception as e:
            logger.error(f"Failed to run coroutine in app loop: {e}")
            # Fall back to creating a new loop
    
    # Fallback: run in new event loop in separate thread
    def run_in_new_loop():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(coro)
        finally:
            try:
                loop.close()
            except:
                pass
    
    with concurrent.futures.ThreadPoolExecutor() as executor:
        future = executor.submit(run_in_new_loop)
        return future.result()

@_flask_app.route("/api/auth/send_code", methods=["POST"])
def send_verification_code():
    """Send verification code for fast test authentication"""
    try:
        data = request.get_json()
        phone_number = data.get('phone_number', '').strip()
        
        if not phone_number:
            return jsonify({'success': False, 'error': '請輸入電話號碼'})
        
        # Get API credentials from main app config
        api_id = _app.api_id
        api_hash = _app.api_hash
        
        if not api_id or not api_hash:
            return jsonify({'success': False, 'error': 'API 憑證未設定'})
        
        # Initialize auth manager if not exists
        from module.multiuser_auth import TelegramAuthManager
        auth_manager = TelegramAuthManager()
        
        # Start auth process
        result = run_async_in_thread(
            auth_manager.start_auth_process(phone_number, api_id, api_hash)
        )
        
        if result['success']:
            # Store session info
            session_key = result['session_key']
            fast_test_auth_sessions[session_key] = {
                'phone_number': phone_number,
                'phone_code_hash': result['phone_code_hash'],
                'auth_manager': auth_manager
            }
            
            # Store session key in Flask session for this user
            session['fast_test_session_key'] = session_key
            session.permanent = True  # Make session persistent
        
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Failed to send verification code: {e}")
        return jsonify({'success': False, 'error': f'發送驗證碼失敗: {str(e)}'})


@_flask_app.route("/api/auth/verify_code", methods=["POST"])
def verify_verification_code():
    """Verify phone code for fast test authentication"""
    try:
        data = request.get_json()
        verification_code = data.get('verification_code', '').strip()
        
        # Get session key from Flask session
        session_key = session.get('fast_test_session_key')
        
        if not session_key or session_key not in fast_test_auth_sessions:
            return jsonify({'success': False, 'error': '會話已過期，請重新開始'})
        
        if not verification_code:
            return jsonify({'success': False, 'error': '請輸入驗證碼'})
        
        session_info = fast_test_auth_sessions[session_key]
        auth_manager = session_info['auth_manager']
        phone_code_hash = session_info['phone_code_hash']
        
        # Verify code
        result = run_async_in_thread(
            auth_manager.verify_code(session_key, verification_code, phone_code_hash)
        )
        
        if result['success'] and not result.get('requires_password'):
            # Authentication completed successfully
            session['fast_test_authenticated'] = True
            session['fast_test_user_info'] = result.get('user_info', {})
            session.permanent = True  # Make session persistent
            
            # Store user session in database for persistence
            if 'user_id' in result:
                session['fast_test_user_id'] = result['user_id']
        
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Failed to verify code: {e}")
        return jsonify({'success': False, 'error': f'驗證碼驗證失敗: {str(e)}'})


@_flask_app.route("/api/auth/verify_password", methods=["POST"])
def verify_two_factor_password():
    """Verify 2FA password for fast test authentication"""
    try:
        data = request.get_json()
        password = data.get('password', '')
        
        # Get session key from Flask session
        session_key = session.get('fast_test_session_key')
        
        if not session_key or session_key not in fast_test_auth_sessions:
            return jsonify({'success': False, 'error': '會話已過期，請重新開始'})
        
        if not password:
            return jsonify({'success': False, 'error': '請輸入兩步驗證密碼'})
        
        session_info = fast_test_auth_sessions[session_key]
        auth_manager = session_info['auth_manager']
        
        # Verify password
        result = run_async_in_thread(
            auth_manager.verify_password(session_key, password)
        )
        
        if result['success']:
            # Authentication completed successfully
            session['fast_test_authenticated'] = True
            session['fast_test_user_info'] = result.get('user_info', {})
            session.permanent = True  # Make session persistent
            
            # Store user session in database for persistence
            if 'user_id' in result:
                session['fast_test_user_id'] = result['user_id']
        
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Failed to verify password: {e}")
        return jsonify({'success': False, 'error': f'密碼驗證失敗: {str(e)}'})


@_flask_app.route("/api/auth/status", methods=["GET"])
def get_auth_status():
    """Get current authentication status for fast test"""
    try:
        authenticated = session.get('fast_test_authenticated', False)
        user_info = session.get('fast_test_user_info', {})
        user_id = session.get('fast_test_user_id')
        
        # If session shows authenticated but we don't have an active session_key,
        # try to restore it from database
        if authenticated and user_id and not session.get('fast_test_session_key'):
            try:
                # Try to restore the Telegram client session for this user
                from module.multiuser_auth import TelegramAuthManager
                auth_manager = TelegramAuthManager()
                
                # Create a session key for this restored session
                import uuid
                new_session_key = f"restored_{user_id}_{str(uuid.uuid4())[:8]}"
                
                # Try to get client for this user using our async helper
                client = run_async_in_thread(auth_manager.get_user_client(user_id))
                
                if client:
                    # Restore session
                    session['fast_test_session_key'] = new_session_key
                    fast_test_auth_sessions[new_session_key] = {
                        'phone_number': user_info.get('phone_number', ''),
                        'auth_manager': auth_manager
                    }
                    auth_manager.active_clients[new_session_key] = client
                    
                    logger.info(f"Restored session for user {user_id}")
                else:
                    # Session is invalid, clear authentication
                    authenticated = False
                    session.pop('fast_test_authenticated', None)
                    session.pop('fast_test_user_info', None)
                    session.pop('fast_test_user_id', None)
                    session.pop('fast_test_session_key', None)
                    user_info = {}
                    
                    logger.warning(f"Failed to restore session for user {user_id}, clearing auth")
                    
            except Exception as restore_error:
                logger.error(f"Failed to restore session for user {user_id}: {restore_error}")
                # Don't clear auth here, just log the error
        
        return jsonify({
            'success': True,
            'authenticated': authenticated,
            'user_info': user_info
        })
        
    except Exception as e:
        logger.error(f"Failed to get auth status: {e}")
        return jsonify({'success': False, 'error': f'獲取認證狀態失敗: {str(e)}'})


@_flask_app.route("/api/auth/logout", methods=["POST"])
def fast_test_logout():
    """Logout from fast test authentication"""
    try:
        # Get session key and clean up
        session_key = session.get('fast_test_session_key')
        
        if session_key and session_key in fast_test_auth_sessions:
            # Clean up auth session
            session_info = fast_test_auth_sessions[session_key]
            auth_manager = session_info.get('auth_manager')
            
            # Disconnect client if exists
            import asyncio
            if auth_manager and hasattr(auth_manager, 'disconnect_session'):
                if hasattr(_app, 'loop') and _app.loop:
                    _app.loop.run_until_complete(
                        auth_manager.disconnect_session(session_key)
                    )
                else:
                    asyncio.run(auth_manager.disconnect_session(session_key))
            
            # Remove from global storage
            del fast_test_auth_sessions[session_key]
        
        # Clear Flask session
        session.pop('fast_test_session_key', None)
        session.pop('fast_test_authenticated', None)
        session.pop('fast_test_user_info', None)
        
        return jsonify({'success': True, 'message': '已成功登出'})
        
    except Exception as e:
        logger.error(f"Failed to logout: {e}")
        return jsonify({'success': False, 'error': f'登出失敗: {str(e)}'})


def require_fast_test_auth(f):
    """Decorator to require fast test authentication"""
    from functools import wraps
    
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('fast_test_authenticated', False):
            return jsonify({'success': False, 'error': '需要先進行認證'})
        return f(*args, **kwargs)
    return decorated_function


# =============================================================================
# Group Management APIs for Fast Test
# =============================================================================

@_flask_app.route("/api/groups/list", methods=["GET"])
@require_fast_test_auth
def get_groups_list():
    """Get list of joined groups for fast test"""
    try:
        # Get authenticated user's session
        session_key = session.get('fast_test_session_key')
        
        if not session_key or session_key not in fast_test_auth_sessions:
            return jsonify({'success': False, 'error': '會話已過期，請重新登入'})
        
        session_info = fast_test_auth_sessions[session_key]
        auth_manager = session_info['auth_manager']
        
        # Get client for this user using our async helper
        groups = run_async_in_thread(
            auth_manager.get_user_groups(session_key)
        )
        
        return jsonify({
            'success': True,
            'groups': groups
        })
        
    except Exception as e:
        logger.error(f"Failed to get groups list: {e}")
        return jsonify({'success': False, 'error': f'獲取群組列表失敗: {str(e)}'})


@_flask_app.route("/api/groups/messages", methods=["POST"])
@require_fast_test_auth
def get_group_messages():
    """Get messages from a specific group for fast test"""
    try:
        data = request.get_json()
        chat_id = data.get('chat_id')
        limit = data.get('limit', 50)  # Default 50 messages
        offset_id = data.get('offset_id', 0)  # For pagination
        media_only = data.get('media_only', False)  # Filter for media messages only
        
        if not chat_id:
            return jsonify({'success': False, 'error': '請提供群組 ID'})
        
        # Get authenticated user's session
        session_key = session.get('fast_test_session_key')
        
        if not session_key or session_key not in fast_test_auth_sessions:
            return jsonify({'success': False, 'error': '會話已過期，請重新登入'})
        
        session_info = fast_test_auth_sessions[session_key]
        auth_manager = session_info['auth_manager']
        
        # Get messages for this group using our async helper
        result = run_async_in_thread(
            auth_manager.get_group_messages(
                session_key, chat_id, limit, offset_id, media_only
            )
        )
        
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Failed to get group messages: {e}")
        return jsonify({'success': False, 'error': f'獲取群組訊息失敗: {str(e)}'})


@_flask_app.route("/api/groups/load_more", methods=["POST"])
@require_fast_test_auth
def load_more_messages():
    """Load more messages for pagination"""
    try:
        data = request.get_json()
        chat_id = data.get('chat_id')
        offset_id = data.get('offset_id')
        limit = data.get('limit', 50)
        media_only = data.get('media_only', False)
        
        if not chat_id or not offset_id:
            return jsonify({'success': False, 'error': '缺少必要參數'})
        
        # Get authenticated user's session
        session_key = session.get('fast_test_session_key')
        
        if not session_key or session_key not in fast_test_auth_sessions:
            return jsonify({'success': False, 'error': '會話已過期，請重新登入'})
        
        session_info = fast_test_auth_sessions[session_key]
        auth_manager = session_info['auth_manager']
        
        # Load more messages using our async helper
        result = run_async_in_thread(
            auth_manager.get_group_messages(
                session_key, chat_id, limit, offset_id, media_only
            )
        )
        
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Failed to load more messages: {e}")
        return jsonify({'success': False, 'error': f'載入更多訊息失敗: {str(e)}'})


# =============================================================================
# Fast Download APIs
# =============================================================================

@_flask_app.route("/api/fast_download/add_tasks", methods=["POST"])
@require_fast_test_auth
def add_fast_download_tasks():
    """Add selected messages to download queue from fast test"""
    try:
        data = request.get_json()
        chat_id = data.get('chat_id')
        message_ids = data.get('message_ids', [])
        
        logger.info(f"Fast Test API called with chat_id: {chat_id}, message_ids: {message_ids}")
        
        if not chat_id or not message_ids:
            logger.error(f"Missing data - chat_id: {chat_id}, message_ids: {message_ids}")
            return jsonify({'success': False, 'error': '請提供群組 ID 和訊息 ID 列表'})
        
        # Add to existing custom download system
        from collections import OrderedDict
        
        # Update target_ids in config
        # Ensure _app.config is properly initialized
        if not hasattr(_app, 'config') or _app.config is None:
            logger.error("_app.config is not initialized")
            return jsonify({'success': False, 'error': '應用配置未初始化'})
            
        # Ensure custom_downloads section exists
        if 'custom_downloads' not in _app.config:
            _app.config['custom_downloads'] = {'enable': True, 'target_ids': {}, 'group_tags': {}}
        
        # Ensure target_ids exists
        custom_downloads = _app.config['custom_downloads']
        if 'target_ids' not in custom_downloads:
            custom_downloads['target_ids'] = OrderedDict()
        
        # Add message IDs to target chat
        target_ids = custom_downloads['target_ids']
        if chat_id not in target_ids:
            target_ids[chat_id] = []
        
        # Add new message IDs (avoid duplicates)
        existing_ids = set(target_ids[chat_id])
        new_ids = [msg_id for msg_id in message_ids if msg_id not in existing_ids]
        
        if new_ids:
            target_ids[chat_id].extend(new_ids)
            logger.info(f"Added {len(new_ids)} new message IDs: {new_ids}")
            
            # Mark as newly added for auto-select
            global newly_added_items
            for msg_id in new_ids:
                newly_added_items.add((chat_id, msg_id))
            
            # Update config file
            try:
                _app.update_config()
                logger.info("Configuration updated successfully")
            except Exception as update_error:
                logger.error(f"Failed to update config: {update_error}")
                # Don't fail the request if config update fails
                pass
            
            return jsonify({
                'success': True,
                'message': f'已新增 {len(new_ids)} 個下載任務',
                'added_count': len(new_ids)
            })
        else:
            logger.info(f"All message IDs already exist in queue: existing={existing_ids}, requested={message_ids}")
            return jsonify({
                'success': True,
                'message': '所選訊息已在下載佇列中',
                'added_count': 0
            })
        
    except Exception as e:
        import traceback
        logger.error(f"Failed to add fast download tasks: {e}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        logger.error(f"_app type: {type(_app)}")
        logger.error(f"_app.config type: {type(_app.config) if _app else 'N/A'}")
        return jsonify({'success': False, 'error': f'添加下載任務失敗: {str(e)}'})


@_flask_app.route("/api/fast_download/status", methods=["GET"])
@require_fast_test_auth
def get_fast_download_status():
    """Get download status for fast test interface"""
    try:
        # Use existing download progress system
        global download_progress, active_download_session
        
        return jsonify({
            'success': True,
            'progress': download_progress,
            'session': active_download_session,
            'download_state': get_download_state().name
        })
        
    except Exception as e:
        logger.error(f"Failed to get download status: {e}")
        return jsonify({'success': False, 'error': f'獲取下載狀態失敗: {str(e)}'})
