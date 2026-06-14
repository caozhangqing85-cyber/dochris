#!/usr/bin/env python3
"""
SHA256 缓存管理

用于缓存文件提取结果，避免重复处理相同内容。
"""

import hashlib
import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any, cast

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
    d = root / "cache"
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
            return cast(dict[str, Any], cached_data.get("result"))
        return None
    except (json.JSONDecodeError, OSError):
        return None


def save_cached(cache_dir: Path, file_hash: str, result: dict[str, Any]) -> bool | None:
    """
    保存提取结果到缓存

    Args:
        cache_dir: 缓存目录
        file_hash: 文件哈希值
        result: 要缓存的结果

    Returns:
        成功返回 True，失败返回 False，file_hash 为空返回 None
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

        # 原子写入：os.replace 跨平台原子（Path.rename 在跨设备时会失败）
        os.replace(tmp, entry)
        return True
    except (OSError, TypeError) as e:
        logger.warning(f"Failed to save cache: {e}")
        return False


def query_cache_key(query: str, context: str) -> str:
    """生成查询缓存的键（基于查询文本 + 上下文指纹）

    Args:
        query: 用户查询文本
        context: 拼接后的上下文（concepts + summaries + vector results）

    Returns:
        SHA256 十六进制哈希字符串
    """
    combined = f"{query}\n---\n{context}"
    return hashlib.sha256(combined.encode("utf-8")).hexdigest()


def load_query_cache(workspace_cache_dir: Path, key: str) -> str | None:
    """从缓存中加载查询回答

    Args:
        workspace_cache_dir: 工作区缓存目录 (workspace/cache/)
        key: query_cache_key() 生成的哈希

    Returns:
        缓存的回答文本，未命中返回 None
    """
    query_cache = workspace_cache_dir / "query_answers"
    entry = query_cache / f"{key}.json"
    if not entry.exists():
        return None
    try:
        with open(entry, encoding="utf-8") as f:
            data = json.load(f)
        return cast(str | None, data.get("answer"))
    except (json.JSONDecodeError, OSError):
        return None


def save_query_cache(workspace_cache_dir: Path, key: str, answer: str) -> bool | None:
    """保存查询回答到缓存

    Args:
        workspace_cache_dir: 工作区缓存目录
        key: query_cache_key() 生成的哈希
        answer: LLM 生成的回答

    Returns:
        成功返回 True
    """
    query_cache = workspace_cache_dir / "query_answers"
    query_cache.mkdir(parents=True, exist_ok=True)
    entry = query_cache / f"{key}.json"
    tmp = entry.with_suffix(".tmp")
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(
                {"key": key, "answer": answer, "timestamp": str(datetime.now())},
                f,
                ensure_ascii=False,
                indent=2,
            )
        os.replace(tmp, entry)
        return True
    except (OSError, TypeError) as e:
        logger.warning(f"Failed to save query cache: {e}")
        return False


def clear_cache(cache_dir: Path, older_than_days: int = 30) -> int:
    """
    清理旧缓存文件

    Args:
        cache_dir: 缓存目录（应仅含缓存 .json；调用方需确保路径正确）
        older_than_days: 清理多少天前的文件

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
