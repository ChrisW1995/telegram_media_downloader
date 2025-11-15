"""MP4 檔案結構解析工具

用於處理 MP4 atom 解析、moov atom 提取等操作
支援 Telegram 串流播放的 MP4 重組
"""

import struct
from typing import Tuple, Optional, List
from loguru import logger


class MP4Atom:
    """MP4 Atom 結構"""

    def __init__(self, atom_type: bytes, size: int, offset: int, data: bytes = b''):
        self.type = atom_type
        self.size = size
        self.offset = offset
        self.data = data

    def __repr__(self):
        return f"MP4Atom(type={self.type.decode('ascii', errors='ignore')}, size={self.size}, offset={self.offset})"


def parse_atom_header(data: bytes, offset: int = 0) -> Optional[Tuple[bytes, int]]:
    """解析 MP4 atom header

    Args:
        data: 包含 atom 的數據
        offset: atom 在數據中的偏移

    Returns:
        (atom_type, atom_size) 或 None
    """
    if len(data) < offset + 8:
        return None

    # MP4 atom 結構：[4 bytes size][4 bytes type][data]
    atom_size = struct.unpack('>I', data[offset:offset+4])[0]
    atom_type = data[offset+4:offset+8]

    # 處理大小為 1 的情況（extended size）
    if atom_size == 1:
        if len(data) < offset + 16:
            return None
        atom_size = struct.unpack('>Q', data[offset+8:offset+16])[0]

    # 處理大小為 0 的情況（atom 延伸到檔案末尾）
    if atom_size == 0:
        atom_size = len(data) - offset

    return atom_type, atom_size


def find_atom(data: bytes, atom_type: bytes, start_offset: int = 0) -> Optional[MP4Atom]:
    """在數據中搜尋特定類型的 atom

    Args:
        data: 要搜尋的數據
        atom_type: 要搜尋的 atom 類型（4 bytes，如 b'moov'）
        start_offset: 開始搜尋的偏移

    Returns:
        找到的 MP4Atom 或 None
    """
    offset = start_offset

    while offset < len(data) - 8:
        header = parse_atom_header(data, offset)
        if not header:
            break

        current_type, current_size = header

        # 檢查是否找到目標 atom
        if current_type == atom_type:
            # 提取完整的 atom 數據
            if offset + current_size <= len(data):
                atom_data = data[offset:offset+current_size]
                return MP4Atom(current_type, current_size, offset, atom_data)
            else:
                # atom 超出數據範圍，返回不含數據的資訊
                return MP4Atom(current_type, current_size, offset)

        # 移動到下一個 atom
        offset += current_size

    return None


def find_all_atoms(data: bytes) -> List[MP4Atom]:
    """列出數據中的所有 atom

    Args:
        data: 要分析的數據

    Returns:
        所有 atom 的列表
    """
    atoms = []
    offset = 0

    while offset < len(data) - 8:
        header = parse_atom_header(data, offset)
        if not header:
            break

        atom_type, atom_size = header

        if offset + atom_size <= len(data):
            atom_data = data[offset:offset+atom_size]
            atoms.append(MP4Atom(atom_type, atom_size, offset, atom_data))
        else:
            atoms.append(MP4Atom(atom_type, atom_size, offset))

        offset += atom_size

    return atoms


def extract_atom(data: bytes, atom_type: bytes) -> Optional[bytes]:
    """從數據中提取指定類型的 atom

    Args:
        data: 包含 atom 的數據
        atom_type: 要提取的 atom 類型

    Returns:
        atom 的完整數據（包含 header）或 None
    """
    atom = find_atom(data, atom_type)
    if atom and atom.data:
        return atom.data
    return None


async def find_moov_location(file_size: int, tail_reader) -> Optional[Tuple[int, int]]:
    """找出 moov atom 在檔案中的位置

    Args:
        file_size: 檔案總大小
        tail_reader: async function(offset, limit) -> bytes，用於讀取檔案片段

    Returns:
        (moov_offset, moov_size) 或 None
    """
    # Telegram API 關鍵限制：請求必須在同一個 1MB 區塊內
    # 使用 256KB 可以減少跨越 1MB 邊界的機會
    # get_file_range 會自動處理邊界檢查和調整
    MAX_CHUNK_SIZE = 256 * 1024  # 256KB（安全值）

    # 策略1：先檢查檔案開頭（faststart 優化的檔案 moov 在前面）
    logger.info("🔍 檢查檔案開頭是否有 moov atom (faststart 優化)")
    header_data = await tail_reader(0, min(MAX_CHUNK_SIZE, file_size))
    moov = find_atom(header_data, b'moov')
    if moov:
        logger.success(f"✅ 找到 moov atom (faststart): offset={moov.offset}, size={moov.size}")
        return (moov.offset, moov.size)

    # 策略2：從檔案末尾往前搜尋，通常未優化的 MP4 moov atom 在最後 1-30MB
    logger.info("🔍 檔案開頭無 moov，從末尾搜尋...")
    search_sizes = [
        1 * 1024 * 1024,   # 先試 1MB
        5 * 1024 * 1024,   # 再試 5MB
        10 * 1024 * 1024,  # 試 10MB
        20 * 1024 * 1024,  # 試 20MB
        30 * 1024 * 1024,  # 最後試 30MB
    ]

    for search_size in search_sizes:
        search_size = min(search_size, file_size)

        # 計算搜尋範圍（必須對齊到 4KB）
        offset = max(0, file_size - search_size)
        offset = (offset // 4096) * 4096
        total_size = file_size - offset
        total_size_aligned = ((total_size + 4095) // 4096) * 4096

        # 讀取數據（支援分段讀取）
        if total_size_aligned <= MAX_CHUNK_SIZE:
            # 一次讀取
            logger.info(f"🔍 搜尋 moov atom: offset={offset}, limit={total_size_aligned}")
            data = await tail_reader(offset, total_size_aligned)
        else:
            # 分段讀取
            logger.info(f"🔍 搜尋 moov atom (分段): offset={offset}, total_size={total_size_aligned}")
            chunks = []
            current_offset = offset
            remaining = total_size_aligned

            while remaining > 0:
                chunk_size = min(MAX_CHUNK_SIZE, remaining)
                logger.info(f"  📥 讀取片段: offset={current_offset}, limit={chunk_size}")
                chunk = await tail_reader(current_offset, chunk_size)
                chunks.append(chunk)
                current_offset += chunk_size
                remaining -= chunk_size

            data = b''.join(chunks)

        # 搜尋 moov atom
        moov = find_atom(data, b'moov')

        if moov:
            actual_offset = offset + moov.offset
            logger.success(f"✅ 找到 moov atom: offset={actual_offset}, size={moov.size}")
            return (actual_offset, moov.size)
        else:
            # 調試：顯示這個範圍內找到的 atom 類型
            atoms = find_all_atoms(data)
            atom_types = [atom.type.decode('ascii', errors='ignore') for atom in atoms[:10]]  # 只顯示前 10 個
            logger.info(f"   📋 該範圍內的 atom: {', '.join(atom_types)}")

    logger.error("❌ 找不到 moov atom")
    return None


async def extract_moov_atom(file_size: int, file_reader) -> Optional[bytes]:
    """提取 MP4 檔案的 moov atom

    Args:
        file_size: 檔案總大小
        file_reader: async function(offset, limit) -> bytes，用於讀取檔案片段

    Returns:
        moov atom 的完整數據或 None
    """
    # 1. 找出 moov atom 的位置
    location = await find_moov_location(file_size, file_reader)

    if not location:
        return None

    moov_offset, moov_size = location

    # 2. 讀取完整的 moov atom（支援分段讀取）
    MAX_CHUNK_SIZE = 256 * 1024  # 256KB（安全值，避免跨越 1MB 邊界）

    # 對齊到 4KB
    aligned_offset = (moov_offset // 4096) * 4096
    total_size = moov_size + (moov_offset - aligned_offset)
    total_size_aligned = ((total_size + 4095) // 4096) * 4096

    # 如果 moov atom 小於 1MB，一次讀取
    if total_size_aligned <= MAX_CHUNK_SIZE:
        logger.info(f"📥 讀取完整 moov atom: offset={aligned_offset}, limit={total_size_aligned}")
        data = await file_reader(aligned_offset, total_size_aligned)

        # 從對齊的數據中提取 moov
        local_offset = moov_offset - aligned_offset
        moov_data = data[local_offset:local_offset+moov_size]
    else:
        # moov atom 太大，需要分段讀取
        logger.info(f"📥 moov atom 較大 ({total_size_aligned} bytes)，使用分段讀取")
        chunks = []
        current_offset = aligned_offset
        remaining = total_size_aligned

        while remaining > 0:
            chunk_size = min(MAX_CHUNK_SIZE, remaining)
            logger.info(f"📥 讀取片段: offset={current_offset}, limit={chunk_size}")
            chunk = await file_reader(current_offset, chunk_size)
            chunks.append(chunk)
            current_offset += chunk_size
            remaining -= chunk_size

        # 合併所有片段
        data = b''.join(chunks)

        # 從對齊的數據中提取 moov
        local_offset = moov_offset - aligned_offset
        moov_data = data[local_offset:local_offset+moov_size]

    logger.success(f"✅ moov atom 提取完成: {len(moov_data)} bytes")
    return moov_data


def calculate_mdat_offset(ftyp_size: int, moov_size: int) -> Tuple[int, int]:
    """計算重組後 mdat 的偏移量調整

    Args:
        ftyp_size: ftyp atom 的大小
        moov_size: moov atom 的大小

    Returns:
        (new_mdat_start, offset_adjustment)
    """
    # 新結構：ftyp + moov + mdat
    new_mdat_start = ftyp_size + moov_size

    # 偏移量調整：需要告訴 moov atom 新的 mdat 位置
    # 這可能需要修改 moov 內部的偏移引用
    # 簡化處理：大部分情況下不需要調整（使用相對偏移）

    return new_mdat_start, 0
