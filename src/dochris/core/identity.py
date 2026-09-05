"""数据身份模型（DATA-01/DATA-02）。

提供跨工作区稳定的 canonical document ID：

- 路径身份：``canonical_source_path`` 把符号链接、相对路径、大小写
  （大小写不敏感文件系统）归一化成规范字符串；
- 内容身份：manifest 已有的 ``content_hash``（文件 SHA-256）是内容层身份；
- ``canonical_document_id`` = SHA-256(canonical_source_path)，写入 manifest
  的 ``canonical_id`` 字段，用于路径维度的去重与追踪。

SRC-NNNN 仍是主键（有序、人类可读）；canonical_id 是补充的稳定标识，
不改变任何现有存储布局。
"""

from __future__ import annotations

import hashlib
import os
import sys
from pathlib import Path

_CASE_INSENSITIVE = sys.platform in {"darwin", "win32"}


def canonical_source_path(path: str | Path) -> str:
    """把任意来源路径归一化为规范字符串。

    - 展开 ~ 与环境引用；
    - 解析符号链接（不存在时尽量解析父目录）；
    - 绝对化 + normpath；
    - 大小写不敏感文件系统上统一转小写。
    """
    raw = os.path.expandvars(os.path.expanduser(str(path)))
    p = Path(raw)
    try:
        resolved = p.resolve(strict=False)
    except OSError:
        resolved = p.absolute()
    normalized = os.path.normpath(str(resolved))
    if _CASE_INSENSITIVE:
        normalized = normalized.lower()
    return normalized


def canonical_document_id(path: str | Path) -> str:
    """返回来源路径的 canonical document ID（sha256 前 16 位十六进制）。"""
    return hashlib.sha256(canonical_source_path(path).encode("utf-8")).hexdigest()[:16]
