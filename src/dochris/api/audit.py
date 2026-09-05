"""写操作审计日志（SEC-04）。

所有非 GET API 请求记录一条 JSONL 审计事件到 ``<workspace>/logs/audit.log``：
- operation_id：本次操作的唯一 ID（同时通过 X-Operation-ID 响应头返回）
- idempotency_key：客户端可选的 Idempotency-Key 请求头，用于重放去重
- method/path/client/trace_id 与 sanitized query 参数

设计约束：审计写入失败绝不能阻断主请求（local-only 模式下 logs 目录
可能不可写），只记录 warning。
"""

from __future__ import annotations

import json
import logging
import os
import uuid
from datetime import UTC, datetime
from pathlib import Path

logger = logging.getLogger(__name__)

AUDIT_LOG_NAME = "audit.log"


def new_operation_id() -> str:
    """生成操作 ID。"""
    return uuid.uuid4().hex


def _audit_log_path() -> Path | None:
    """解析审计日志路径；无法定位工作区时返回 None。"""
    try:
        from dochris.settings import get_settings

        workspace = Path(get_settings().workspace).expanduser()
        return workspace / "logs" / AUDIT_LOG_NAME
    except Exception:
        return None


def record_operation(
    operation_id: str,
    method: str,
    path: str,
    client: str = "",
    trace_id: str = "",
    idempotency_key: str = "",
    status_code: int | None = None,
) -> None:
    """追加一条审计事件。失败不影响主流程。"""
    log_path = _audit_log_path()
    if log_path is None:
        return
    event = {
        "operation_id": operation_id,
        "timestamp": datetime.now(UTC).isoformat(),
        "method": method,
        "path": path,
        "client": client,
        "trace_id": trace_id,
        "idempotency_key": idempotency_key,
        "status_code": status_code,
    }
    try:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with open(log_path, "a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, ensure_ascii=False) + "\n")
    except OSError:
        logger.warning("无法写入审计日志", exc_info=True)


def workspace_rewrite_allowed() -> bool:
    """SEC-03：workspace 修改授权检查。

    规则：
    - 显式设置 ``DOCHRIS_ALLOW_WORKSPACE_REWRITE=true`` → 允许；
    - 否则仅 local-only 模式（未配置 DOCHRIS_API_KEY）允许；
    - 已配置 API key 的受保护部署默认禁止，防止运行时改写数据根目录。
    """
    flag = os.environ.get("DOCHRIS_ALLOW_WORKSPACE_REWRITE", "").strip().lower()
    if flag in {"1", "true", "yes", "on"}:
        return True
    if flag in {"0", "false", "no", "off"}:
        return False
    # 未显式配置：local-only（无 API key）允许，受保护部署禁止
    return not os.environ.get("DOCHRIS_API_KEY")
