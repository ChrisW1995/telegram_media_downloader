"""Downloads media from telegram."""
import asyncio
import logging
import os
import shutil
import signal
import sys
import time
from typing import List, Optional, Tuple, Union

import pyrogram
from loguru import logger
from pyrogram.types import Audio, Document, Photo, Video, VideoNote, Voice
from rich.logging import RichHandler

from module.app_db import DatabaseApplication as Application
from module.app import ChatDownloadConfig, DownloadStatus, TaskNode
from module.bot import start_download_bot, stop_download_bot
from module.download_stat import update_download_status
from module.get_chat_history_v2 import get_chat_history_v2
from module.language import _t
from module.pyrogram_extension import (
    HookClient,
    fetch_message,
    get_extension,
    record_download_status,
    report_bot_download_status,
    set_max_concurrent_transmissions,
    set_meta_data,
    update_cloud_upload_stat,
    upload_telegram_chat,
)
from module.web import init_web
from utils.format import format_byte, truncate_filename, validate_title
from utils.log import LogFilter
from utils.meta import print_meta
from utils.meta_data import MetaData

logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
    datefmt="[%X]",
    handlers=[RichHandler()],
)

CONFIG_NAME = "config.yaml"
DATA_FILE_NAME = "data.yaml"
APPLICATION_NAME = "media_downloader"
app = Application(CONFIG_NAME, DATA_FILE_NAME, APPLICATION_NAME)

queue: asyncio.Queue = asyncio.Queue()
RETRY_TIME_OUT = 3

# Global flag for graceful shutdown
_shutdown_requested = False

def signal_handler(signum, frame):
    """Handle shutdown signals gracefully."""
    global _shutdown_requested
    if not _shutdown_requested:
        _shutdown_requested = True
        logger.info(f"Received signal {signum}, initiating graceful shutdown...")
        # Stop the event loop if it's running
        try:
            loop = asyncio.get_running_loop()
            loop.call_soon_threadsafe(lambda: asyncio.create_task(_graceful_shutdown()))
        except RuntimeError:
            # No running loop, exit directly
            logger.info("No running event loop, exiting immediately")
            sys.exit(0)
    else:
        logger.warning("Shutdown already in progress, forcing exit")
        sys.exit(1)

async def _graceful_shutdown():
    """Perform graceful shutdown operations."""
    global _shutdown_requested
    _shutdown_requested = True
    app.is_running = False
    logger.info("Graceful shutdown initiated")

logging.getLogger("pyrogram.session.session").addFilter(LogFilter())
logging.getLogger("pyrogram.client").addFilter(LogFilter())

logging.getLogger("pyrogram").setLevel(logging.WARNING)


def _check_download_finish(media_size: int, download_path: str, ui_file_name: str):
    """Check download task if finish

    Parameters
    ----------
    media_size: int
        The size of the downloaded resource
    download_path: str
        Resource download hold path
    ui_file_name: str
        Really show file name

    """
    download_size = os.path.getsize(download_path)
    if media_size == download_size:
        logger.success(f"{_t('Successfully downloaded')} - {ui_file_name}")
    else:
        logger.warning(
            f"{_t('Media downloaded with wrong size')}: "
            f"{download_size}, {_t('actual')}: "
            f"{media_size}, {_t('file name')}: {ui_file_name}"
        )
        os.remove(download_path)
        raise pyrogram.errors.exceptions.bad_request_400.BadRequest()


def _move_to_download_path(temp_download_path: str, download_path: str):
    """Move file to download path

    Parameters
    ----------
    temp_download_path: str
        Temporary download path

    download_path: str
        Download path

    """

    directory, _ = os.path.split(download_path)
    os.makedirs(directory, exist_ok=True)
    shutil.move(temp_download_path, download_path)


def _check_timeout(retry: int, _: int):
    """Check if message download timeout, then add message id into failed_ids

    Parameters
    ----------
    retry: int
        Retry download message times

    message_id: int
        Try to download message 's id

    """
    if retry == 2:
        return True
    return False


def _can_download(_type: str, file_formats: dict, file_format: Optional[str]) -> bool:
    """
    Check if the given file format can be downloaded.

    Parameters
    ----------
    _type: str
        Type of media object.
    file_formats: dict
        Dictionary containing the list of file_formats
        to be downloaded for `audio`, `document` & `video`
        media types
    file_format: str
        Format of the current file to be downloaded.

    Returns
    -------
    bool
        True if the file format can be downloaded else False.
    """
    if _type in ["audio", "document", "video"]:
        allowed_formats: list = file_formats[_type]
        if not file_format in allowed_formats and allowed_formats[0] != "all":
            return False
    return True


def _is_exist(file_path: str) -> bool:
    """
    Check if a file exists and it is not a directory.

    Parameters
    ----------
    file_path: str
        Absolute path of the file to be checked.

    Returns
    -------
    bool
        True if the file exists else False.
    """
    return not os.path.isdir(file_path) and os.path.exists(file_path)


# pylint: disable = R0912


async def _get_media_meta(
    chat_id: Union[int, str],
    message: pyrogram.types.Message,
    media_obj: Union[Audio, Document, Photo, Video, VideoNote, Voice],
    _type: str,
    node: TaskNode = None,
) -> Tuple[str, str, Optional[str]]:
    """Extract file name and file id from media object.

    Parameters
    ----------
    media_obj: Union[Audio, Document, Photo, Video, VideoNote, Voice]
        Media object to be extracted.
    _type: str
        Type of media object.

    Returns
    -------
    Tuple[str, str, Optional[str]]
        file_name, file_format
    """
    if _type in ["audio", "document", "video"]:
        # pylint: disable = C0301
        file_format: Optional[str] = media_obj.mime_type.split("/")[-1]  # type: ignore
    else:
        file_format = None

    file_name = None
    temp_file_name = None
    dirname = validate_title(f"{chat_id}")
    if message.chat and message.chat.title:
        dirname = validate_title(f"{message.chat.title}")

    if message.date:
        datetime_dir_name = message.date.strftime(app.date_format)
    else:
        datetime_dir_name = "0"

    if _type in ["voice", "video_note"]:
        # pylint: disable = C0209
        file_format = media_obj.mime_type.split("/")[-1]  # type: ignore
        is_bot = node and node.bot is not None
        file_save_path = app.get_file_save_path(_type, dirname, datetime_dir_name, is_bot)
        file_name = "{} - {}_{}.{}".format(
            message.id,
            _type,
            media_obj.date.isoformat(),  # type: ignore
            file_format,
        )
        file_name = validate_title(file_name)
        temp_file_name = os.path.join(app.temp_save_path, dirname, file_name)

        file_name = os.path.join(file_save_path, file_name)
    else:
        file_name = getattr(media_obj, "file_name", None)
        caption = getattr(message, "caption", None)

        file_name_suffix = ".unknown"
        if not file_name:
            file_name_suffix = get_extension(
                media_obj.file_id, getattr(media_obj, "mime_type", "")
            )
        else:
            # file_name = file_name.split(".")[0]
            _, file_name_without_suffix = os.path.split(os.path.normpath(file_name))
            file_name, file_name_suffix = os.path.splitext(file_name_without_suffix)
            if not file_name_suffix:
                file_name_suffix = get_extension(
                    media_obj.file_id, getattr(media_obj, "mime_type", "")
                )

        if caption:
            caption = validate_title(caption)
            app.set_caption_name(chat_id, message.media_group_id, caption)
            app.set_caption_entities(
                chat_id, message.media_group_id, message.caption_entities
            )
        else:
            caption = app.get_caption_name(chat_id, message.media_group_id)

        if not file_name and message.photo:
            file_name = f"{message.photo.file_unique_id}"

        gen_file_name = (
            app.get_file_name(message.id, file_name, caption) + file_name_suffix
        )

        is_bot = node and node.bot is not None
        file_save_path = app.get_file_save_path(_type, dirname, datetime_dir_name, is_bot)

        temp_file_name = os.path.join(app.temp_save_path, dirname, gen_file_name)

        file_name = os.path.join(file_save_path, gen_file_name)
    return truncate_filename(file_name), truncate_filename(temp_file_name), file_format


async def add_download_task(
    message: pyrogram.types.Message,
    node: TaskNode,
):
    """Add Download task"""
    if message.empty:
        return False
    node.download_status[message.id] = DownloadStatus.Downloading
    await queue.put((message, node))
    node.total_task += 1
    return True


async def save_msg_to_file(
    app, chat_id: Union[int, str], message: pyrogram.types.Message, node: TaskNode = None
):
    """Write message text into file"""
    dirname = validate_title(
        message.chat.title if message.chat and message.chat.title else str(chat_id)
    )
    datetime_dir_name = message.date.strftime(app.date_format) if message.date else "0"

    is_bot = node and node.bot is not None
    file_save_path = app.get_file_save_path("msg", dirname, datetime_dir_name, is_bot)
    file_name = os.path.join(
        app.temp_save_path,
        file_save_path,
        f"{app.get_file_name(message.id, None, None)}.txt",
    )

    os.makedirs(os.path.dirname(file_name), exist_ok=True)

    if _is_exist(file_name):
        return DownloadStatus.SkipDownload, file_name

    with open(file_name, "w", encoding="utf-8") as f:
        f.write(message.text or "")

    return DownloadStatus.SuccessDownload, file_name


async def download_task(
    client: pyrogram.Client, message: pyrogram.types.Message, node: TaskNode
):
    """Download and Forward media"""

    download_status, file_name = await download_media(
        client, message, app.media_types, app.file_formats, node
    )

    # Detailed message analysis for debugging
    logger.info(f"id={message.id} Message analysis:")
    logger.info(f"  - text: {repr(message.text)}")
    logger.info(f"  - caption: {repr(message.caption)}")
    logger.info(f"  - media: {message.media}")
    logger.info(f"  - media type: {type(message.media)}")
    if message.media:
        logger.info(f"  - media attributes: {dir(message.media)}")
    
    # 檢查是否是 custom download
    is_custom_download = hasattr(node, 'is_custom_download') and node.is_custom_download

    logger.info(f"id={message.id} Text download check - enable_txt: {app.enable_download_txt}, has_text: {bool(message.text)}, has_media: {bool(message.media)}, is_custom: {is_custom_download}")

    # 對於 custom download，強制下載用戶選擇的文字消息
    if (app.enable_download_txt or is_custom_download) and message.text and not message.media:
        logger.info(f"id={message.id} Attempting to download text content (custom: {is_custom_download})")
        download_status, file_name = await save_msg_to_file(app, node.chat_id, message, node)
        logger.info(f"id={message.id} Text download result: {download_status}, file: {file_name}")
    else:
        logger.info(f"id={message.id} Text download skipped - conditions not met")

    if not node.bot:
        app.set_download_id(node, message.id, download_status)

    node.download_status[message.id] = download_status

    file_size = os.path.getsize(file_name) if file_name else 0

    await upload_telegram_chat(
        client,
        node.upload_user if node.upload_user else client,
        app,
        node,
        message,
        download_status,
        file_name,
    )

    # rclone upload
    if (
        not node.upload_telegram_chat_id
        and download_status is DownloadStatus.SuccessDownload
    ):
        ui_file_name = file_name
        if app.hide_file_name:
            ui_file_name = f"****{os.path.splitext(file_name)[-1]}"
        if await app.upload_file(
            file_name, update_cloud_upload_stat, (node, message.id, ui_file_name)
        ):
            node.upload_success_count += 1

    # Send downloaded file via bot for successful downloads and skipped files
    if (node.bot and download_status in [DownloadStatus.SuccessDownload, DownloadStatus.SkipDownload] and 
        file_name and node.from_user_id and os.path.exists(file_name)):
        try:
            # Determine the media type and send accordingly
            file_ext = os.path.splitext(file_name)[1].lower()
            file_size_mb = file_size / (1024 * 1024)
            
            if download_status is DownloadStatus.SuccessDownload:
                success_msg = f"✅ **下載完成並傳送檔案** ({file_size_mb:.1f} MB)\n🆔 訊息ID: {message.id}"
            else:  # SkipDownload
                success_msg = f"📁 **檔案已存在，傳送現有檔案** ({file_size_mb:.1f} MB)\n🆔 訊息ID: {message.id}"
            
            if file_ext in ['.mp4', '.avi', '.mov', '.mkv', '.webm']:
                # Send as video
                await node.bot.send_video(
                    node.from_user_id,
                    file_name,
                    caption=success_msg,
                    parse_mode=pyrogram.enums.ParseMode.MARKDOWN
                )
            elif file_ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp']:
                # Send as photo
                await node.bot.send_photo(
                    node.from_user_id,
                    file_name,
                    caption=success_msg,
                    parse_mode=pyrogram.enums.ParseMode.MARKDOWN
                )
            elif file_ext in ['.mp3', '.wav', '.ogg', '.m4a', '.flac']:
                # Send as audio
                await node.bot.send_audio(
                    node.from_user_id,
                    file_name,
                    caption=success_msg,
                    parse_mode=pyrogram.enums.ParseMode.MARKDOWN
                )
            else:
                # Send as document for other file types
                await node.bot.send_document(
                    node.from_user_id,
                    file_name,
                    caption=success_msg,
                    parse_mode=pyrogram.enums.ParseMode.MARKDOWN
                )
            
            logger.info(f"Successfully sent file via bot: {os.path.basename(file_name)} ({file_size_mb:.1f} MB)")
                
        except Exception as e:
            logger.warning(f"Failed to send file via bot: {e}")
            # Fallback: send text message with file info
            try:
                file_size_mb = file_size / (1024 * 1024)
                fallback_msg = (
                    f"✅ **下載完成**\n\n"
                    f"❌ **檔案傳送失敗**: {str(e)}\n"
                    f"📁 **檔案名稱**: `{os.path.basename(file_name)}`\n"
                    f"📏 **檔案大小**: {file_size_mb:.1f} MB\n"
                    f"📍 **本地路徑**: `{os.path.abspath(file_name)}`\n"
                    f"🆔 **訊息ID**: {message.id}"
                )
                
                await node.bot.send_message(
                    node.from_user_id,
                    fallback_msg,
                    parse_mode=pyrogram.enums.ParseMode.MARKDOWN
                )
            except Exception as fallback_error:
                logger.error(f"Failed to send fallback message: {fallback_error}")

    await report_bot_download_status(
        node.bot,
        node,
        download_status,
        file_size,
    )

    return download_status, file_name


# pylint: disable = R0915,R0914


@record_download_status
async def download_media(
    client: pyrogram.client.Client,
    message: pyrogram.types.Message,
    media_types: List[str],
    file_formats: dict,
    node: TaskNode,
):
    """
    Download media from Telegram.

    Each of the files to download are retried 3 times with a
    delay of 5 seconds each.

    Parameters
    ----------
    client: pyrogram.client.Client
        Client to interact with Telegram APIs.
    message: pyrogram.types.Message
        Message object retrieved from telegram.
    media_types: list
        List of strings of media types to be downloaded.
        Ex : `["audio", "photo"]`
        Supported formats:
            * audio
            * document
            * photo
            * video
            * voice
    file_formats: dict
        Dictionary containing the list of file_formats
        to be downloaded for `audio`, `document` & `video`
        media types.

    Returns
    -------
    int
        Current message id.
    """

    # pylint: disable = R0912

    file_name: str = ""
    ui_file_name: str = ""
    task_start_time: float = time.time()
    media_size = 0
    _media = None
    message = await fetch_message(client, message)
    try:
        for _type in media_types:
            _media = getattr(message, _type, None)
            if _media is None:
                continue
            file_name, temp_file_name, file_format = await _get_media_meta(
                node.chat_id, message, _media, _type, node
            )
            media_size = getattr(_media, "file_size", 0)

            ui_file_name = file_name
            if app.hide_file_name:
                ui_file_name = f"****{os.path.splitext(file_name)[-1]}"

            if _can_download(_type, file_formats, file_format):
                # 檢查是否是 ZIP 下載，如果是則強制重新下載
                is_zip_download = hasattr(node, 'zip_download_manager') and node.zip_download_manager

                if _is_exist(file_name) and not is_zip_download:
                    file_size = os.path.getsize(file_name)
                    if file_size or file_size == media_size:
                        logger.info(
                            f"id={message.id} {ui_file_name} "
                            f"File path: {file_name} "
                            f"{_t('already download,download skipped')}.\n"
                        )

                        return DownloadStatus.SkipDownload, file_name
                elif is_zip_download and _is_exist(file_name):
                    logger.info(f"id={message.id} ZIP 下載模式 - 強制重新下載已存在檔案: {ui_file_name}")
                    # 為 ZIP 下載產生臨時檔案名，避免覆蓋原檔案
                    import tempfile
                    temp_dir = tempfile.mkdtemp(prefix='zip_download_')
                    file_name = os.path.join(temp_dir, os.path.basename(file_name))
            else:
                return DownloadStatus.SkipDownload, None

            break
    except Exception as e:
        logger.error(
            f"Message[{message.id}]: "
            f"{_t('could not be downloaded due to following exception')}:\n[{e}].",
            exc_info=True,
        )
        return DownloadStatus.FailedDownload, None
    
    # Debug message analysis
    logger.info(f"id={message.id} Media analysis:")
    logger.info(f"  - _media: {_media}")
    logger.info(f"  - message.media: {message.media}")
    logger.info(f"  - message.text: {repr(message.text)}")
    logger.info(f"  - message.caption: {repr(message.caption)}")
    logger.info(f"  - checked media_types: {media_types}")
    for _type in media_types:
        _type_value = getattr(message, _type, None)
        logger.info(f"  - message.{_type}: {_type_value}")
    
    if _media is None:
        # 檢查是否是 custom download，如果是且有文字內容，嘗試下載文字
        is_custom_download = hasattr(node, 'is_custom_download') and node.is_custom_download

        if is_custom_download and message.text:
            logger.info(f"id={message.id} Custom download: No media but has text content - attempting text download")
            # 對於 custom download，如果沒有媒體但有文字，不直接跳過
            # 讓後續的 text download 邏輯處理
            return DownloadStatus.SkipDownload, None
        else:
            logger.info(f"id={message.id} No media content found - skipping download (text-only message)")
            return DownloadStatus.SkipDownload, None

    message_id = message.id

    for retry in range(3):
        try:
            temp_download_path = await client.download_media(
                message,
                file_name=temp_file_name,
                progress=update_download_status,
                progress_args=(
                    message_id,
                    ui_file_name,
                    task_start_time,
                    node,
                    client,
                ),
            )

            if temp_download_path and isinstance(temp_download_path, str):
                _check_download_finish(media_size, temp_download_path, ui_file_name)
                await asyncio.sleep(0.5)
                _move_to_download_path(temp_download_path, file_name)
                # TODO: if not exist file size or media
                return DownloadStatus.SuccessDownload, file_name
            else:
                # 檢查是否是 custom download
                is_custom_download = hasattr(node, 'is_custom_download') and node.is_custom_download
                logger.error(
                    f"id={message.id} Download failed: temp_download_path is {temp_download_path}, "
                    f"is_custom_download: {is_custom_download}"
                )
                if temp_download_path is None:
                    logger.error(f"id={message.id} Pyrogram download_media returned None - possible authentication or permission issue")
                break
        except pyrogram.errors.exceptions.bad_request_400.BadRequest:
            logger.warning(
                f"Message[{message.id}]: {_t('file reference expired, refetching')}..."
            )
            await asyncio.sleep(RETRY_TIME_OUT)
            message = await fetch_message(client, message)
            if _check_timeout(retry, message.id):
                # pylint: disable = C0301
                logger.error(
                    f"Message[{message.id}]: "
                    f"{_t('file reference expired for 3 retries, download skipped.')}"
                )
        except pyrogram.errors.exceptions.flood_420.FloodWait as wait_err:
            await asyncio.sleep(wait_err.value)
            logger.warning("Message[{}]: FlowWait {}", message.id, wait_err.value)
            _check_timeout(retry, message.id)
        except TypeError:
            # pylint: disable = C0301
            logger.warning(
                f"{_t('Timeout Error occurred when downloading Message')}[{message.id}], "
                f"{_t('retrying after')} {RETRY_TIME_OUT} {_t('seconds')}"
            )
            await asyncio.sleep(RETRY_TIME_OUT)
            if _check_timeout(retry, message.id):
                logger.error(
                    f"Message[{message.id}]: {_t('Timing out after 3 reties, download skipped.')}"
                )
        except Exception as e:
            # pylint: disable = C0301
            logger.error(
                f"Message[{message.id}]: "
                f"{_t('could not be downloaded due to following exception')}:\n[{e}].",
                exc_info=True,
            )
            break

    return DownloadStatus.FailedDownload, None


def _load_config():
    """Load config"""
    app.load_config()


def _check_config() -> bool:
    """Check config"""
    print_meta(logger)
    try:
        _load_config()
        logger.add(
            os.path.join(app.log_file_path, "tdl.log"),
            rotation="10 MB",
            retention="10 days",
            level=app.log_level,
        )
    except Exception as e:
        logger.exception(f"load config error: {e}")
        return False

    return True


async def worker(client: pyrogram.client.Client):
    """Work for download task"""
    while app.is_running:
        download_status = None
        file_path = None
        message = None
        node = None

        try:
            item = await queue.get()
            message = item[0]
            node: TaskNode = item[1]

            # Check for cancelled state
            from module.download_stat import get_download_state, DownloadState
            if get_download_state() == DownloadState.Cancelled:
                node.is_stop_transmission = True
                continue

            if node.is_stop_transmission:
                continue

            # 執行下載任務
            if node.client:
                download_status, file_path = await download_task(node.client, message, node)
            else:
                download_status, file_path = await download_task(client, message, node)

            # 通知 ZIP 下載管理器（如果是 ZIP 下載的一部分）
            if hasattr(node, 'zip_download_manager') and node.zip_download_manager:
                from module.app import DownloadStatus
                message_id = getattr(node, 'zip_message_id', message.id)

                if download_status in [DownloadStatus.SuccessDownload, DownloadStatus.SkipDownload] and file_path:
                    try:
                        import os
                        file_size = os.path.getsize(file_path) if file_path else 0
                        node.zip_download_manager.on_file_downloaded(message_id, file_path, file_size)
                    except Exception as zip_error:
                        logger.error(f"ZIP 管理器通知下載完成失敗: {zip_error}")
                        node.zip_download_manager.on_file_failed(message_id, str(zip_error))
                else:
                    # 真正的下載失敗
                    error_msg = f"下載狀態: {download_status}"
                    node.zip_download_manager.on_file_failed(message_id, error_msg)

        except Exception as e:
            logger.exception(f"{e}")

            # 如果有 ZIP 管理器，也要通知失敗
            try:
                if node and hasattr(node, 'zip_download_manager') and node.zip_download_manager:
                    message_id = getattr(node, 'zip_message_id', getattr(message, 'id', 'unknown') if message else 'unknown')
                    node.zip_download_manager.on_file_failed(message_id, str(e))
            except Exception as zip_error:
                logger.error(f"ZIP 管理器通知異常失敗: {zip_error}")


async def download_chat_task(
    client: pyrogram.Client,
    chat_download_config: ChatDownloadConfig,
    node: TaskNode,
):
    """Download all task"""
    messages_iter = get_chat_history_v2(
        client,
        node.chat_id,
        limit=node.limit,
        max_id=node.end_offset_id,
        offset_id=chat_download_config.last_read_message_id,
        reverse=True,
    )

    chat_download_config.node = node

    if chat_download_config.ids_to_retry:
        logger.info(f"{_t('Downloading files failed during last run')}...")
        skipped_messages: list = await client.get_messages(  # type: ignore
            chat_id=node.chat_id, message_ids=chat_download_config.ids_to_retry
        )

        for message in skipped_messages:
            await add_download_task(message, node)

    async for message in messages_iter:  # type: ignore
        # Check for cancelled state during message processing
        from module.download_stat import get_download_state, DownloadState
        if get_download_state() == DownloadState.Cancelled:
            logger.info("Download cancelled by user, stopping message processing")
            break
            
        meta_data = MetaData()

        caption = message.caption
        if caption:
            caption = validate_title(caption)
            app.set_caption_name(node.chat_id, message.media_group_id, caption)
            app.set_caption_entities(
                node.chat_id, message.media_group_id, message.caption_entities
            )
        else:
            caption = app.get_caption_name(node.chat_id, message.media_group_id)
        set_meta_data(meta_data, message, caption)

        if app.need_skip_message(chat_download_config, message.id):
            continue

        if app.exec_filter(chat_download_config, meta_data):
            await add_download_task(message, node)
        else:
            node.download_status[message.id] = DownloadStatus.SkipDownload
            if message.media_group_id:
                await upload_telegram_chat(
                    client,
                    node.upload_user,
                    app,
                    node,
                    message,
                    DownloadStatus.SkipDownload,
                )

    chat_download_config.need_check = True
    chat_download_config.total_task = node.total_task
    node.is_running = True


async def download_all_chat(client: pyrogram.Client):
    """Download All chat"""
    # Check if custom download is enabled and exclusive
    custom_config = app.config.get('custom_downloads', {})
    if custom_config.get('enable', False):
        logger.info("Custom download is enabled, skipping regular chat download")
        return
    
    for key, value in app.chat_download_config.items():
        value.node = TaskNode(chat_id=key)
        try:
            await download_chat_task(client, value, value.node)
        except Exception as e:
            logger.warning(f"Download {key} error: {e}")
        finally:
            value.need_check = True


async def run_until_all_task_finish():
    """Normal download"""
    while True:
        finish: bool = True
        for _, value in app.chat_download_config.items():
            if not value.need_check or value.total_task != value.finish_task:
                finish = False

        if (not app.bot_token and finish) or app.restart_program:
            break

        await asyncio.sleep(1)


def _exec_loop():
    """Exec loop"""

    app.loop.run_until_complete(run_until_all_task_finish())


async def start_server(client: pyrogram.Client):
    """
    Start the server using the provided client.
    """
    await client.start()


async def stop_server(client: pyrogram.Client):
    """
    Stop the server using the provided client.
    """
    try:
        await client.stop()
    except ConnectionError:
        # Client is already terminated, ignore
        pass


def main():
    """Main function of the downloader."""
    global _shutdown_requested
    tasks = []
    
    # Register signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    
    # 使用用戶主目錄下的 session 存儲，避免權限問題
    session_dir = os.path.join(os.path.expanduser("~"), ".telegram_sessions")
    if not os.path.exists(session_dir):
        os.makedirs(session_dir, exist_ok=True)
    
    # 設置完全權限
    os.chmod(session_dir, 0o755)
    print(f"Using session directory: {session_dir}")
    
    client = HookClient(
        "media_downloader",
        api_id=app.api_id,
        api_hash=app.api_hash,
        proxy=app.proxy,
        workdir=session_dir,  # 使用用戶主目錄下的路徑
        start_timeout=app.start_timeout,
    )
    try:
        app.pre_run()
        init_web(app, client, queue)

        set_max_concurrent_transmissions(client, app.max_concurrent_transmissions)

        app.loop.run_until_complete(start_server(client))
        logger.success(_t("Successfully started (Press Ctrl+C to stop)"))

        # Start worker tasks first
        for _ in range(app.max_download_task):
            task = app.loop.create_task(worker(client))
            tasks.append(task)
        
        app.loop.create_task(download_all_chat(client))
        
        # Custom download functionality - removed auto-start, now controlled via web interface

        if app.bot_token:
            app.loop.run_until_complete(
                start_download_bot(app, client, add_download_task, download_chat_task)
            )
        _exec_loop()
    except KeyboardInterrupt:
        logger.info(_t("KeyboardInterrupt"))
        _shutdown_requested = True
    except Exception as e:
        logger.exception("{}", e)
        _shutdown_requested = True
    finally:
        # Ensure graceful cleanup
        logger.info("Starting cleanup process...")
        app.is_running = False
        
        # Cancel all tasks first
        for task in tasks:
            if not task.done():
                task.cancel()
                logger.debug(f"Cancelled task: {task}")
        
        # Wait for cancelled tasks to complete
        if tasks:
            try:
                app.loop.run_until_complete(asyncio.gather(*tasks, return_exceptions=True))
            except Exception as e:
                logger.warning(f"Error waiting for tasks to complete: {e}")
        
        # Stop services in order
        if app.bot_token:
            try:
                app.loop.run_until_complete(stop_download_bot())
            except Exception as e:
                logger.warning(f"Error stopping bot: {e}")
        
        # Stop client
        try:
            app.loop.run_until_complete(stop_server(client))
        except Exception as e:
            logger.warning(f"Error stopping server: {e}")
        
        logger.info(_t("Stopped!"))
        
        # Update configuration
        try:
            logger.info(f"{_t('update config')}......")
            app.update_config()
            logger.success(
                f"{_t('Updated last read message_id to config file')},"
                f"{_t('total download')} {app.total_download_task}, "
                f"{_t('total upload file')} "
                f"{app.cloud_drive_config.total_upload_success_file_count}"
            )
        except Exception as e:
            logger.warning(f"Error updating config: {e}")
        
        # Clean up database connections
        try:
            from database.database_manager import close_database
            close_database()
            logger.debug("Database connections closed")
        except Exception as e:
            logger.warning(f"Error closing database: {e}")


if __name__ == "__main__":
    if _check_config():
        main()
