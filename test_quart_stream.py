#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Quart POC - 測試影片串流是否能解決 event loop 衝突

這個獨立服務用於驗證：
1. Quart 是否能與 Pyrogram 共享 event loop
2. 是否能實現真正的邊下載邊傳送串流
3. 效能和延遲是否符合 hover 播放需求
"""

import asyncio
from quart import Quart, Response, request, session
from quart_cors import cors
from loguru import logger
from pathlib import Path
import sys

# Add module to path
sys.path.insert(0, str(Path(__file__).parent))

app = Quart(__name__)
app.secret_key = "test-secret-key-for-poc"

# 啟用 CORS 支持 - 允許所有來源（POC 測試用）
app = cors(app, allow_origin="*")

# Global app instance for accessing auth manager
_auth_manager = None


def set_auth_manager(manager):
    """Set the auth manager instance"""
    global _auth_manager
    _auth_manager = manager


@app.route('/test/video_stream/<chat_id>/<int:message_id>', methods=['GET'])
async def stream_video_progressive(chat_id: str, message_id: int):
    """真正的串流：邊從 Telegram 下載邊傳送給瀏覽器

    這是關鍵測試端點 - 驗證 Quart 是否能解決 Flask 的 event loop 問題
    """
    try:
        # 轉換 chat_id 為整數（支援負數）
        chat_id = int(chat_id)

        logger.info(f"🎬 開始串流測試: chat_id={chat_id}, message_id={message_id}")

        async def async_generate_video():
            """異步生成器：邊下載邊 yield"""
            try:
                # 獲取認證客戶端
                from module.multiuser_auth import get_auth_manager
                auth_manager = get_auth_manager()

                # 嘗試獲取已激活的客戶端
                client = None
                if auth_manager.active_clients:
                    client_key = list(auth_manager.active_clients.keys())[0]
                    client = auth_manager.active_clients[client_key]
                    logger.info(f"✅ 使用已激活的客戶端: {client_key}")
                else:
                    # 如果沒有激活客戶端，嘗試從 user_sessions 創建
                    if not auth_manager.user_sessions:
                        logger.error("❌ 沒有可用的用戶會話")
                        yield b''
                        return

                    # 使用第一個可用的 user_session
                    user_id = list(auth_manager.user_sessions.keys())[0]
                    logger.info(f"📱 嘗試從 session 創建客戶端: user_id={user_id}")

                    # 使用正確的方法名稱：get_user_client
                    client = await auth_manager.get_user_client(user_id=user_id)

                    if not client:
                        logger.error(f"❌ 無法為 user_id={user_id} 創建客戶端")
                        yield b''
                        return

                    logger.success(f"✅ 成功創建客戶端: user_id={user_id}")

                # 獲取訊息
                logger.info(f"📥 正在獲取訊息...")
                result = await client.get_messages(chat_id=chat_id, message_ids=message_id)
                message = result if not isinstance(result, list) else result[0] if result else None

                if not message or not message.video:
                    logger.error(f"❌ 訊息 {message_id} 不包含影片")
                    yield b''
                    return

                video_size_mb = message.video.file_size / 1024 / 1024
                logger.info(f"📹 影片大小: {video_size_mb:.2f} MB")

                # 🔥 使用 FFmpeg 轉換為 MSE 兼容格式
                logger.success("🎬 啟動 FFmpeg 轉換管道...")

                # FFmpeg 命令：使用 MPEG-TS 格式（真正的串流）
                # MPEG-TS 不需要完整輸入即可開始輸出
                ffmpeg_cmd = [
                    'ffmpeg',
                    '-loglevel', 'error',  # 只輸出錯誤到 stderr
                    '-i', 'pipe:0',  # 從 stdin 讀取
                    '-c:v', 'h264_videotoolbox',  # 使用 macOS 硬體編碼器
                    '-b:v', '2M',  # 視頻位元率
                    '-maxrate', '2M',  # 最大位元率
                    '-bufsize', '4M',  # 緩衝區大小
                    '-profile:v', 'baseline',  # 使用 baseline profile（最大相容性）
                    '-c:a', 'aac',  # 音頻編碼為 AAC
                    '-b:a', '128k',  # 音頻位元率
                    '-f', 'mpegts',  # 使用 MPEG-TS 容器（真正的串流格式）
                    'pipe:1'  # 輸出到 stdout
                ]

                # 啟動 FFmpeg 進程
                ffmpeg_process = await asyncio.create_subprocess_exec(
                    *ffmpeg_cmd,
                    stdin=asyncio.subprocess.PIPE,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )

                logger.info(f"✅ FFmpeg 進程已啟動 (PID: {ffmpeg_process.pid})")

                # 創建任務：異步寫入 Telegram 數據到 FFmpeg stdin
                async def write_to_ffmpeg():
                    try:
                        chunk_count = 0
                        total_bytes = 0

                        logger.success("🚀 開始從 Telegram 下載並傳給 FFmpeg...")

                        async for chunk in client.stream_media(message.video):
                            chunk_count += 1
                            total_bytes += len(chunk)

                            # 詳細記錄前 5 塊
                            if chunk_count <= 5:
                                logger.info(f"📦 塊 {chunk_count}: {len(chunk)} bytes → FFmpeg")

                            # 每 10 塊 log 一次
                            if chunk_count % 10 == 0:
                                mb_downloaded = total_bytes / 1024 / 1024
                                logger.info(f"📊 已下載 {chunk_count} 塊 (~{mb_downloaded:.1f} MB) → FFmpeg")

                            # 寫入 FFmpeg stdin
                            ffmpeg_process.stdin.write(chunk)
                            await ffmpeg_process.stdin.drain()

                        # 關閉 stdin 通知 FFmpeg 輸入完成
                        ffmpeg_process.stdin.close()
                        await ffmpeg_process.stdin.wait_closed()

                        logger.success(f"✅ Telegram 下載完成: {chunk_count} 塊, {total_bytes / 1024 / 1024:.2f} MB")

                    except Exception as e:
                        logger.error(f"❌ 寫入 FFmpeg 失敗: {e}")
                        if not ffmpeg_process.stdin.is_closing():
                            ffmpeg_process.stdin.close()

                # 創建任務：監控 FFmpeg stderr
                async def monitor_ffmpeg_stderr():
                    try:
                        while True:
                            line = await ffmpeg_process.stderr.readline()
                            if not line:
                                break
                            error_msg = line.decode('utf-8', errors='ignore').strip()
                            if error_msg:
                                logger.error(f"🔴 FFmpeg: {error_msg}")
                    except Exception as e:
                        logger.error(f"❌ stderr 監控失敗: {e}")

                # 啟動寫入任務和 stderr 監控（不等待完成）
                write_task = asyncio.create_task(write_to_ffmpeg())
                stderr_task = asyncio.create_task(monitor_ffmpeg_stderr())

                # 從 FFmpeg stdout 讀取轉換後的數據並 yield
                output_chunk_count = 0
                output_total_bytes = 0

                logger.info("📤 開始從 FFmpeg 讀取轉換後的數據...")

                try:
                    while True:
                        # 從 FFmpeg stdout 讀取數據
                        output_chunk = await ffmpeg_process.stdout.read(65536)  # 64KB 塊

                        if not output_chunk:
                            break  # FFmpeg 輸出結束

                        output_chunk_count += 1
                        output_total_bytes += len(output_chunk)

                        # 詳細記錄前 5 塊
                        if output_chunk_count <= 5:
                            logger.info(f"📤 輸出塊 {output_chunk_count}: {len(output_chunk)} bytes → 瀏覽器")

                        # 每 10 塊 log 一次
                        if output_chunk_count % 10 == 0:
                            mb_output = output_total_bytes / 1024 / 1024
                            logger.info(f"📊 已輸出 {output_chunk_count} 塊 (~{mb_output:.1f} MB) → 瀏覽器")

                        yield output_chunk

                    logger.success(f"✅ FFmpeg 轉換完成: 輸出 {output_chunk_count} 塊, {output_total_bytes / 1024 / 1024:.2f} MB")

                finally:
                    # 確保 FFmpeg 進程正確關閉
                    if ffmpeg_process.returncode is None:
                        ffmpeg_process.kill()
                        await ffmpeg_process.wait()

                    # 等待寫入任務和 stderr 監控任務完成
                    for task in [write_task, stderr_task]:
                        if not task.done():
                            task.cancel()
                            try:
                                await task
                            except asyncio.CancelledError:
                                pass

                    logger.info("✅ FFmpeg 管道已清理")

            except Exception as e:
                logger.error(f"❌ 串流生成器錯誤: {e}")
                import traceback
                logger.error(traceback.format_exc())
                yield b''

        # 🎯 關鍵差異：Quart 原生支援 async generator
        return Response(
            async_generate_video(),
            mimetype='video/mp4',
            headers={
                'Accept-Ranges': 'bytes',
                'Cache-Control': 'no-cache',
                'X-Content-Type-Options': 'nosniff'
            }
        )

    except Exception as e:
        logger.error(f"❌ 串流失敗: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return {'error': str(e)}, 500


@app.route('/test/health', methods=['GET'])
async def health_check():
    """健康檢查端點"""
    from module.multiuser_auth import get_auth_manager
    auth_manager = get_auth_manager()

    has_clients = bool(auth_manager and auth_manager.active_clients)

    return {
        'status': 'ok',
        'framework': 'Quart',
        'async_native': True,
        'has_telegram_client': has_clients,
        'client_count': len(auth_manager.active_clients) if has_clients else 0
    }


async def main():
    """啟動 Quart POC 服務"""
    logger.info("🧪 啟動 Quart POC 測試服務...")
    logger.info("📍 測試端點: http://localhost:5003/test/video_stream/<chat_id>/<message_id>")
    logger.info("💚 健康檢查: http://localhost:5003/test/health")

    # 啟動服務
    config = {
        'bind': '0.0.0.0:5003',
        'workers': 1,  # POC 使用單一 worker
    }

    await app.run_task(host='0.0.0.0', port=5003, debug=True)


if __name__ == '__main__':
    try:
        # 🔥 關鍵：Quart 使用 asyncio.run()，與 Pyrogram 共享 event loop
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("🛑 POC 服務已停止")
