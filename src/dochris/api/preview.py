"""破坏性操作预览（SEC-05）。

为 reset / promote / discard 等\"不可直接撤销\"的写操作提供 preview/diff：
调用方在真正执行前先拿到\"会发生什么\"的结构化清单（含文件级
create/overwrite/identical 差异与阻塞项），确认后再发起实际写入。

统一信封：
    {"preview": true, "operation": str, "summary": str,
     "changes": [...], "blockers": [...]}
"""

from __future__ import annotations

from pathlib import Path
from typing import Any


def preview_envelope(
    operation: str,
    summary: str,
    changes: list[dict[str, Any]],
    blockers: list[str] | None = None,
) -> dict[str, Any]:
    """构造统一的 preview 响应信封。"""
    return {
        "preview": True,
        "operation": operation,
        "summary": summary,
        "changes": changes,
        "blockers": blockers or [],
    }


def file_change(
    target_dir: Path,
    planned_src: Path,
    *,
    workspace: Path | None = None,
) -> dict[str, Any]:
    """计算单个计划复制文件的 diff 条目。

    action 语义：
    - "create"：目标不存在，晋升将新增该文件；
    - "overwrite"：目标已存在且内容不同（列出现大小与计划大小）；
    - "identical"：目标已存在且字节相同（晋升为幂等重放）。
    """
    target = target_dir / planned_src.name
    exists = target.exists()
    identical = False
    target_bytes: int | None = None
    if exists and planned_src.exists():
        target_bytes = target.stat().st_size
        try:
            identical = target.read_bytes() == planned_src.read_bytes()
        except OSError:
            identical = False

    try:
        display = str(target.relative_to(workspace)) if workspace else str(target)
    except ValueError:
        display = str(target)

    if not exists:
        action = "create"
    elif identical:
        action = "identical"
    else:
        action = "overwrite"

    entry: dict[str, Any] = {
        "path": display,
        "action": action,
        "size_bytes": planned_src.stat().st_size if planned_src.exists() else None,
    }
    if target_bytes is not None:
        entry["existing_size_bytes"] = target_bytes
    return entry
