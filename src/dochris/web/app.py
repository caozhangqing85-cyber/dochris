"""Gradio Web UI 主文件 — 组装各 Tab 子模块"""

from __future__ import annotations

import logging

import gradio as gr  # type: ignore[import-untyped]

from dochris import __version__

# Tab 子模块
# 向后兼容重导出 — 保持 from dochris.web.app import xxx 仍然可用
from .compile_tab import (
    create_compile_tab,
    get_compile_info,
    handle_compile,  # noqa: F401
)
from .file_tab import (  # noqa: F401
    _get_file_table,
    create_file_tab,
    handle_refresh_files,
    handle_upload,
)
from .graph_tab import (
    _handle_graph_refresh,  # noqa: F401
    create_graph_tab,
)
from .quality_tab import (  # noqa: F401
    _get_quality_dashboard,
    create_quality_tab,
    handle_refresh_quality,
)
from .query_tab import (  # noqa: F401
    _format_query_results,
    create_query_tab,
    handle_query,
)
from .status_tab import (  # noqa: F401
    _get_status_distribution_df,
    _get_type_distribution_df,
    create_status_tab,
    get_system_status,
    handle_refresh_status,
)

# 向后兼容别名
_get_system_status = get_system_status  # noqa: F401

logger = logging.getLogger(__name__)


def create_web_app() -> gr.Blocks:
    """创建 Gradio Web UI

    Returns:
        gr.Blocks 实例
    """
    with gr.Blocks(title="dochris - 个人知识库") as app:
        gr.Markdown(
            f"# 📚 dochris 个人知识库 v{__version__}\n四阶段流水线: 摄入 → 编译 → 审核 → 分发"
        )

        with gr.Tabs():
            create_query_tab()
            create_file_tab()
            compile_info = create_compile_tab()
            create_status_tab()
            create_quality_tab()
            create_graph_tab()

        # 页面加载时刷新编译信息
        app.load(fn=get_compile_info, outputs=compile_info)

    return app  # type: ignore[no-any-return]


def launch_web(server_name: str = "0.0.0.0", server_port: int = 7860) -> None:
    """启动 Gradio Web UI 服务器

    Args:
        server_name: 监听地址
        server_port: 监听端口
    """
    app = create_web_app()
    logger.info(f"启动 dochris Web UI: http://{server_name}:{server_port}")
    app.launch(
        server_name=server_name,
        server_port=server_port,
        theme=gr.themes.Soft(),
    )
