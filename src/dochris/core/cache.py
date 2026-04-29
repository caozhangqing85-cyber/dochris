#!/usr/bin/env python3
"""
SHA256 缓存管理 (参考 graphify/cache.py)
"""

import hashlib
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def file_hash(path: Path) -> str | None:
    """
    计算文件的 SHA256 哈希（仅基于文件内容）

    Args:
        path: 文件路径

    Returns:
        SHA256 十六进制哈希字符串，失败时返回 None
    """
    try:
        h = hashlib.sha256()
        h.update(path.read_bytes())
        return h.hexdigest()
    except OSError:
        return None


def cache_dir(root: Path = Path(".")) -> Path:
    """返回缓存目录路径"""
    d = root / "graphify-out" / "cache"
    d.mkdir(parents=True, exist_ok=True)
    return d


def load_cached(cache_dir: Path, file_hash: str) -> dict[str, Any] | None:
    """
    如果哈希匹配，返回缓存的提取结果
    否则返回 None
    """
    if not file_hash:
        return None

    entry = cache_dir / f"{file_hash}.json"
    if not entry.exists():
        return None

    try:
        with open(entry, encoding="utf-8") as f:
            cached_data = json.load(f)

        if cached_data.get("hash") == file_hash:
            return cached_data.get("result")
        return None
    except (json.JSONDecodeError, OSError):
        return None


def save_cached(cache_dir: Path, file_hash: str, result: dict[str, Any]) -> None:
    """
    保存提取结果到缓存
    """
    if not file_hash:
        return None

    entry = cache_dir / f"{file_hash}.json"
    tmp = entry.with_suffix(".tmp")

    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(
                {"hash": file_hash, "result": result, "timestamp": str(datetime.now())},
                f,
                ensure_ascii=False,
                indent=2,
            )

        # 原子写入
        tmp.rename(entry)
        return True
    except (OSError, TypeError) as e:
        logger.warning(f"Failed to save cache: {e}")
        return False


def clear_cache(cache_dir: Path, older_than_days: int = 30) -> int:
    """
    清理旧缓存文件

    Returns:
        清理的文件数量
    """
    from datetime import timedelta

    cutoff = datetime.now() - timedelta(days=older_than_days)
    cleaned = 0

    for cache_file in cache_dir.glob("*.json"):
        if not cache_file.is_file():
            continue

        try:
            stat = cache_file.stat()
            mtime = datetime.fromtimestamp(stat.st_mtime)

            if mtime < cutoff:
                cache_file.unlink()
                cleaned += 1
                logger.info(f"Cleaned old cache: {cache_file.name}")
        except OSError:
            pass

    return cleaned
