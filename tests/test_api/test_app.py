"""FastAPI 应用装配合同测试。"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from dochris.api.app import _get_cors_origins, _preload_embedding_model, create_app

pytestmark = pytest.mark.fast


def test_default_cors_matches_the_react_development_server(monkeypatch) -> None:
    """默认来源只开放给仓库内 Vite 的固定 3000 端口。"""
    monkeypatch.delenv("DOCHRIS_CORS_ORIGINS", raising=False)

    assert _get_cors_origins() == [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]


@pytest.mark.asyncio
async def test_embedding_preload_is_disabled_by_default(monkeypatch) -> None:
    """空白安装启动 API 时不应主动加载或下载嵌入模型。"""
    from unittest.mock import patch

    monkeypatch.delenv("DOCHRIS_PRELOAD_EMBEDDING", raising=False)
    with patch("threading.Thread") as mock_thread:
        await _preload_embedding_model()

    mock_thread.assert_not_called()


@pytest.mark.asyncio
async def test_embedding_preload_can_be_enabled_explicitly(monkeypatch) -> None:
    """需要消除首查冷启动时仍可显式开启后台预热。"""
    from unittest.mock import patch

    monkeypatch.setenv("DOCHRIS_PRELOAD_EMBEDDING", "true")
    with patch("threading.Thread") as mock_thread:
        await _preload_embedding_model()

    mock_thread.assert_called_once()
    mock_thread.return_value.start.assert_called_once_with()


def test_lifespan_closes_compile_job_manager() -> None:
    """API 关闭时必须等待编译作业管理器完成清理。"""
    application = create_app()
    manager = AsyncMock()
    application.state.compile_jobs = manager

    with TestClient(application):
        pass

    manager.close.assert_awaited_once_with()
