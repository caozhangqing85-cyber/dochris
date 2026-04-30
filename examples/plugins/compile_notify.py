"""编译完成通知插件示例

编译完成后打印通知信息。
可扩展为飞书/钉钉/邮件通知。

使用方法：
1. 将此文件复制到 ~/.knowledge-base/plugins/
2. 或在 .env 中设置: PLUGIN_DIRS=/path/to/examples/plugins
"""

from __future__ import annotations

import logging
from typing import Any

# 导入 dochris 插件装饰器
from dochris.plugin import hookimpl

logger = logging.getLogger(__name__)


@hookimpl
def post_compile(src_id: str, result: dict[str, Any]) -> None:
    """编译完成后发送通知

    Args:
        src_id: 文件 ID（如 SRC-0001）
        result: 编译结果字典，包含 status、title 等信息
    """
    status = result.get("status", "unknown")
    title = result.get("title") or result.get("result", {}).get("one_line", src_id)

    if status == "compiled":
        quality = result.get("result", {}).get("quality_score", 0)
        print(f"📢 编译完成: {title} ({src_id}) [质量: {quality}/100]")
    else:
        print(f"⚠️ 编译异常: {title} ({src_id}) - {status}")

    # TODO: 扩展为实际通知
    # - 飞书机器人: send_feishu_notification(message)
    # - 钉钉机器人: send_dingtalk_notification(message)
    # - 邮件: send_email(subject, body)
