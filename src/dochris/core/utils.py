#!/usr/bin/env python3
"""
通用工具函数
"""

import hashlib
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


# ============================================================
# 文件哈希计算
# ============================================================


def compute_file_hash(file_path: Path, algorithm: str = "sha256") -> str | None:
    """
    计算文件哈希值

    Args:
        file_path: 文件路径
        algorithm: 哈希算法（sha256, md5, sha1）

    Returns:
        哈希值的十六进制字符串，失败返回 None
    """
    try:
        hash_obj = hashlib.new(algorithm)
        with open(file_path, "rb") as f:
            # 分块读取大文件
            for chunk in iter(lambda: f.read(8192), b""):
                hash_obj.update(chunk)
        return hash_obj.hexdigest()
    except OSError as e:
        logger.warning(f"Failed to compute hash for {file_path}: {e}")
        return None


# ============================================================
# 文本验证
# ============================================================


def is_meaningful_text(text: str, min_length: int = 100) -> bool:
    """
    判断文本是否有意义

    Args:
        text: 待检查的文本
        min_length: 最小长度

    Returns:
        是否有意义
    """
    if not text or not isinstance(text, str):
        return False
    # 去除空白后检查长度
    stripped = text.strip()
    return len(stripped) >= min_length


def truncate_text(text: str, max_length: int, suffix: str = "...") -> str:
    """
    截断文本到指定长度

    Args:
        text: 原文本
        max_length: 最大长度
        suffix: 截断后缀

    Returns:
        截断后的文本
    """
    if len(text) <= max_length:
        return text
    return text[: max_length - len(suffix)] + suffix


# ============================================================
# 路径工具
# ============================================================


def sanitize_filename(filename: str, replacement: str = "_", max_length: int = 255) -> str:
    """
    清理文件名，移除路径遍历字符和控制字符

    Args:
        filename: 原始文件名
        replacement: 替换字符（默认 "_"）
        max_length: 最大长度限制（默认 255）

    Returns:
        清理后的安全文件名

    Examples:
        >>> sanitize_filename("test.pdf")
        'test.pdf'
        >>> sanitize_filename("../etc/passwd")
        '___etc_passwd'
        >>> sanitize_filename("file\\x00name")
        'file_name'
        >>> sanitize_filename("a" * 300, max_length=80)[:85]
        'aaaaaaaa...'
    """
    import string
    import unicodedata

    if not filename:
        return replacement

    # 移除控制字符
    cleaned = "".join(c for c in filename if unicodedata.category(c)[0] != "C")

    # 移除路径遍历字符
    cleaned = cleaned.replace("..", replacement)
    cleaned = cleaned.replace("/", replacement)
    cleaned = cleaned.replace("\\", replacement)

    # 移除其他不安全字符，保留字母、数字、常见符号
    safe_chars = string.ascii_letters + string.digits + "._- "
    cleaned = "".join(c if c in safe_chars else replacement for c in cleaned)

    # 移除连续的替换字符和首尾空格/点
    while replacement + replacement in cleaned:
        cleaned = cleaned.replace(replacement + replacement, replacement)
    cleaned = cleaned.strip(". ")

    # 应用长度限制（如果设置了）
    if max_length > 0 and len(cleaned) > max_length:
        cleaned = cleaned[:max_length]

    # 确保非空
    return cleaned or "unnamed"


def ensure_dir(path: Path) -> Path:
    """
    确保目录存在

    Args:
        path: 目录路径

    Returns:
        目录路径
    """
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_file_extension(file_path: Path) -> str:
    """
    获取文件扩展名（小写，带点）

    Args:
        file_path: 文件路径

    Returns:
        扩展名，如 '.pdf'
    """
    return file_path.suffix.lower()


# ============================================================
# 安全读取
# ============================================================


def safe_read_text(file_path: Path, encoding: str = "utf-8", errors: str = "replace") -> str | None:
    """
    安全读取文本文件

    Args:
        file_path: 文件路径
        encoding: 编码
        errors: 错误处理策略

    Returns:
        文件内容，失败返回 None
    """
    try:
        return file_path.read_text(encoding=encoding, errors=errors)
    except OSError as e:
        logger.warning(f"Failed to read {file_path}: {e}")
        return None


# ============================================================
# 时间工具
# ============================================================


def format_timestamp(timestamp: float, fmt: str = "%Y-%m-%d %H:%M:%S") -> str:
    """
    格式化时间戳

    Args:
        timestamp: Unix 时间戳
        fmt: 格式字符串

    Returns:
        格式化的时间字符串
    """
    import datetime

    return datetime.datetime.fromtimestamp(timestamp).strftime(fmt)


def get_iso_timestamp() -> str:
    """
    获取当前 ISO 格式时间戳

    Returns:
        ISO 格式时间字符串
    """
    import datetime

    return datetime.datetime.now().isoformat()


# ============================================================
# 路径安全验证
# ============================================================


def validate_path_within_base(
    file_path: Path, base_dir: Path, allow_symlinks: bool = False
) -> bool:
    """
    验证文件路径是否在基础目录内（防止路径遍历攻击）

    Args:
        file_path: 要验证的文件路径
        base_dir: 基础目录（允许的根目录）
        allow_symlinks: 是否允许符号链接（默认 False）

    Returns:
        True 如果路径安全，False 否则

    Examples:
        >>> base = Path("/safe/dir")
        >>> validate_path_within_base(Path("/safe/dir/file.txt"), base)
        True
        >>> validate_path_within_base(Path("/etc/passwd"), base)
        False
        >>> validate_path_within_base(Path("/safe/dir/../etc/passwd"), base)
        False
    """
    try:
        # 解析为绝对路径，解析所有符号链接（如果不允许）
        resolved = file_path.resolve() if not allow_symlinks else file_path.absolute()
        base_resolved = base_dir.resolve()

        # 检查解析后的路径是否以基础目录开头
        try:
            resolved.relative_to(base_resolved)
            return True
        except ValueError:
            # 路径不在基础目录内
            return False
    except (OSError, RuntimeError):
        return False
