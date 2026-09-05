"""错误摘要与脱敏 — 供 API 任务存储与编译流水线共用。

统一规则：
- 保留异常类型名，截断到固定长度；
- 抹去 API key / Bearer token / 密码等秘密字段；
- 抹去本机绝对路径，避免泄露用户目录结构。
"""

from __future__ import annotations

import re

_SECRET_FIELD_RE = re.compile(
    r"(?i)\b(?:authorization|(?:[a-z0-9]+_)?api[_-]?key|access[_-]?token|token|secret|password)"
    r"\b\s*[:=]\s*(?:bearer\s+)?[^\s,;]+"
)
_BEARER_TOKEN_RE = re.compile(r"(?i)\bbearer\s+[^\s,;]+")
_PROVIDER_KEY_RE = re.compile(r"\bsk-[a-zA-Z0-9_-]{8,}\b")
_POSIX_PRIVATE_PATH_RE = re.compile(
    r"(?<![:\w])/(?:Users|home|private|tmp|var|etc|opt|srv|mnt|Volumes)(?:/[^\s,;]+)+"
)
_WINDOWS_PRIVATE_PATH_RE = re.compile(r"\b[a-zA-Z]:\\(?:[^\\\s,;]+\\)+[^\\\s,;]+")

MAX_ERROR_SUMMARY_LENGTH = 1000


def sanitize_error_text(detail: str) -> str:
    """抹去秘密字段与本机路径。"""
    detail = _SECRET_FIELD_RE.sub("[REDACTED]", detail)
    detail = _BEARER_TOKEN_RE.sub("[REDACTED]", detail)
    detail = _PROVIDER_KEY_RE.sub("[REDACTED]", detail)
    detail = _POSIX_PRIVATE_PATH_RE.sub("<path>", detail)
    detail = _WINDOWS_PRIVATE_PATH_RE.sub("<path>", detail)
    return detail


def error_summary(exc: BaseException) -> str:
    """生成单行脱敏错误摘要：`类型名: 详情`。"""
    detail = str(exc).strip() or "未提供错误详情"
    return f"{type(exc).__name__}: {sanitize_error_text(detail)}"[:MAX_ERROR_SUMMARY_LENGTH]
