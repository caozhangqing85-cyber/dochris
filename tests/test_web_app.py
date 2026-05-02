"""Web UI 模块测试 — Gradio 应用创建与基本功能"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import gradio as gr  # type: ignore[import-untyped]
import pytest

from dochris.web.app import (
    _format_query_results,
    _get_file_table,
    _get_quality_dashboard,
    _get_system_status,
    create_web_app,
    handle_query,
    handle_refresh_files,
    handle_refresh_quality,
    handle_refresh_status,
    handle_upload,
)

# ============================================================
# Fixtures
# ============================================================


@pytest.fixture
def mock_settings(tmp_path: Path) -> MagicMock:
    """模拟 settings"""
    settings = MagicMock()
    settings.workspace = tmp_path
    settings.raw_dir = tmp_path / "raw"
    settings.data_dir = tmp_path / "data"
    settings.model = "test-model"
    settings.query_model = "test-query-model"
    settings.api_base = "http://localhost:1234"
    settings.api_key = "test-key"
    settings.min_quality_score = 85
    return settings


@pytest.fixture
def sample_manifests(tmp_path: Path) -> list[dict[str, Any]]:
    """创建示例 manifest 文件"""
    manifests_dir = tmp_path / "manifests" / "sources"
    manifests_dir.mkdir(parents=True)

    manifests = [
        {
            "id": "SRC-0001",
            "original_filename": "test1.pdf",
            "type": "pdf",
            "status": "compiled",
            "quality_score": 90,
            "source_file": "test1.pdf",
        },
        {
            "id": "SRC-0002",
            "original_filename": "test2.md",
            "type": "markdown",
            "status": "ingested",
            "source_file": "test2.md",
        },
        {
            "id": "SRC-0003",
            "original_filename": "test3.pdf",
            "type": "pdf",
            "status": "compiled",
            "quality_score": 60,
            "source_file": "test3.pdf",
        },
        {
            "id": "SRC-0004",
            "original_filename": "test4.txt",
            "type": "text",
            "status": "failed",
            "source_file": "test4.txt",
        },
    ]

    for m in manifests:
        manifest_path = manifests_dir / f"{m['id']}.json"
        manifest_path.write_text(json.dumps(m, ensure_ascii=False), encoding="utf-8")

    return manifests


# ============================================================
# 测试: create_web_app
# ============================================================


class TestCreateWebApp:
    """测试 Gradio 应用工厂"""

    @patch("dochris.web.app.get_settings")
    def test_create_web_app_returns_blocks(self, mock_get_settings: MagicMock) -> None:
        """create_web_app 返回 gr.Blocks 实例"""
        mock_get_settings.return_value = MagicMock()
        app = create_web_app()
        assert isinstance(app, gr.Blocks)

    @patch("dochris.web.app.get_settings")
    def test_create_web_app_has_title(self, mock_get_settings: MagicMock) -> None:
        """应用标题设置正确"""
        mock_get_settings.return_value = MagicMock()
        app = create_web_app()
        assert app.title == "dochris - 个人知识库"


# ============================================================
# 测试: 数据格式化
# ============================================================


class TestFormatQueryResults:
    """测试查询结果格式化"""

    def test_format_empty_results(self) -> None:
        """空结果格式化"""
        result: dict[str, Any] = {"time_seconds": 0.5}
        output = _format_query_results(result)
        assert "未找到相关结果" in output
        assert "0.50s" in output

    def test_format_with_answer(self) -> None:
        """带 AI 回答的格式化"""
        result = {
            "time_seconds": 1.2,
            "answer": "这是一个测试回答",
            "vector_results": [],
            "concepts": [],
        }
        output = _format_query_results(result)
        assert "AI 回答" in output
        assert "测试回答" in output

    def test_format_with_vector_results(self) -> None:
        """带向量结果的格式化"""
        result = {
            "time_seconds": 0.3,
            "vector_results": [
                {
                    "title": "测试文档",
                    "content": "内容摘要",
                    "source": "/path/to/file.pdf",
                    "score": 0.95,
                }
            ],
        }
        output = _format_query_results(result)
        assert "向量搜索结果" in output
        assert "测试文档" in output
        assert "0.950" in output
        assert "/path/to/file.pdf" in output

    def test_format_long_content_truncated(self) -> None:
        """过长内容被截断"""
        long_content = "x" * 600
        result = {
            "time_seconds": 0.1,
            "vector_results": [
                {"title": "T", "content": long_content, "source": "", "score": 0.8},
            ],
        }
        output = _format_query_results(result)
        assert "..." in output
        assert len(output) < len(long_content)


# ============================================================
# 测试: 系统状态
# ============================================================


class TestSystemStatus:
    """测试系统状态获取"""

    @patch("dochris.web.app.get_settings")
    @patch("dochris.web.app.get_all_manifests")
    def test_system_status_basic(
        self,
        mock_manifests: MagicMock,
        mock_get_settings: MagicMock,
        mock_settings: MagicMock,
    ) -> None:
        """基本状态信息"""
        mock_get_settings.return_value = mock_settings
        mock_manifests.return_value = [
            {"status": "compiled", "type": "pdf"},
            {"status": "ingested", "type": "markdown"},
        ]

        output = _get_system_status()
        assert "系统信息" in output
        assert "test-model" in output
        assert "已配置" in output
        assert "文件统计" in output

    @patch("dochris.web.app.get_settings")
    @patch("dochris.web.app.get_all_manifests")
    def test_system_status_with_chromadb(
        self,
        mock_manifests: MagicMock,
        mock_get_settings: MagicMock,
        tmp_path: Path,
    ) -> None:
        """包含 ChromaDB 状态"""
        settings = MagicMock()
        settings.workspace = tmp_path
        settings.data_dir = tmp_path / "data"
        settings.model = "m"
        settings.query_model = "qm"
        settings.api_base = "http://a"
        settings.api_key = "k"
        settings.min_quality_score = 85
        mock_get_settings.return_value = settings
        mock_manifests.return_value = []

        # 创建 chroma 数据库文件
        data_dir = tmp_path / "data"
        data_dir.mkdir(parents=True)
        (data_dir / "chroma.sqlite3").write_bytes(b"x" * 1024)

        output = _get_system_status()
        assert "向量数据库" in output
        assert "MB" in output


# ============================================================
# 测试: 质量仪表盘
# ============================================================


class TestQualityDashboard:
    """测试质量仪表盘"""

    @patch("dochris.web.app.get_settings")
    @patch("dochris.web.app.get_all_manifests")
    def test_quality_no_scores(
        self,
        mock_manifests: MagicMock,
        mock_get_settings: MagicMock,
    ) -> None:
        """无评分数据"""
        mock_get_settings.return_value = MagicMock(min_quality_score=85)
        mock_manifests.return_value = [{"status": "ingested"}]
        output = _get_quality_dashboard()
        assert "暂无质量评分数据" in output

    @patch("dochris.web.app.get_settings")
    @patch("dochris.web.app.get_all_manifests")
    def test_quality_with_scores(
        self,
        mock_manifests: MagicMock,
        mock_get_settings: MagicMock,
    ) -> None:
        """有评分数据"""
        mock_get_settings.return_value = MagicMock(min_quality_score=85)
        mock_manifests.return_value = [
            {"original_filename": "good.pdf", "quality_score": 95},
            {"original_filename": "bad.pdf", "quality_score": 60},
            {"original_filename": "ok.pdf", "quality_score": 88},
        ]
        output = _get_quality_dashboard()
        assert "质量概览" in output
        assert "平均分" in output
        assert "未达标" in output
        assert "bad.pdf" in output

    @patch("dochris.web.app.get_settings")
    @patch("dochris.web.app.get_all_manifests")
    def test_quality_distribution(
        self,
        mock_manifests: MagicMock,
        mock_get_settings: MagicMock,
    ) -> None:
        """质量分布统计"""
        mock_get_settings.return_value = MagicMock(min_quality_score=85)
        mock_manifests.return_value = [
            {"quality_score": 10},
            {"quality_score": 30},
            {"quality_score": 50},
            {"quality_score": 70},
            {"quality_score": 90},
        ]
        output = _get_quality_dashboard()
        assert "质量分布" in output
        assert "81-100" in output


# ============================================================
# 测试: 文件列表
# ============================================================


class TestFileTable:
    """测试文件列表获取"""

    @patch("dochris.web.app.get_settings")
    @patch("dochris.web.app.get_all_manifests")
    def test_file_table_data(
        self,
        mock_manifests: MagicMock,
        mock_get_settings: MagicMock,
        mock_settings: MagicMock,
        sample_manifests: list[dict[str, Any]],
    ) -> None:
        """文件列表数据正确"""
        mock_get_settings.return_value = mock_settings
        mock_manifests.return_value = sample_manifests

        rows = _get_file_table()
        assert len(rows) == 4
        assert rows[0][0] == "SRC-0001"
        assert rows[0][2] == "pdf"
        assert rows[0][3] == "compiled"

    @patch("dochris.web.app.get_settings")
    @patch("dochris.web.app.get_all_manifests")
    def test_file_table_limit(
        self,
        mock_manifests: MagicMock,
        mock_get_settings: MagicMock,
        mock_settings: MagicMock,
    ) -> None:
        """文件列表限制 200 条"""
        mock_get_settings.return_value = mock_settings
        # 生成 250 条 manifest
        many_manifests = [
            {"id": f"SRC-{i:04d}", "type": "pdf", "status": "compiled"}
            for i in range(250)
        ]
        mock_manifests.return_value = many_manifests

        rows = _get_file_table()
        assert len(rows) == 200


# ============================================================
# 测试: 事件处理
# ============================================================


class TestEventHandlers:
    """测试 Gradio 事件处理函数"""

    def test_handle_query_empty(self) -> None:
        """空查询返回提示"""
        result = handle_query("", 5)
        assert "请输入查询内容" in result

    def test_handle_query_whitespace(self) -> None:
        """纯空格查询返回提示"""
        result = handle_query("   ", 5)
        assert "请输入查询内容" in result

    @patch("dochris.web.app._do_query")
    def test_handle_query_success(self, mock_query: MagicMock) -> None:
        """查询成功"""
        mock_query.return_value = {
            "time_seconds": 0.5,
            "answer": "测试回答",
            "vector_results": [],
            "concepts": [],
        }
        result = handle_query("测试", 5)
        assert "测试回答" in result

    @patch("dochris.web.app._do_query")
    def test_handle_query_error(self, mock_query: MagicMock) -> None:
        """查询失败"""
        mock_query.side_effect = RuntimeError("API 错误")
        result = handle_query("测试", 5)
        assert "查询出错" in result

    @patch("dochris.web.app.get_settings")
    @patch("dochris.web.app.get_all_manifests")
    def test_handle_refresh_files(
        self,
        mock_manifests: MagicMock,
        mock_get_settings: MagicMock,
        mock_settings: MagicMock,
    ) -> None:
        """刷新文件列表"""
        mock_get_settings.return_value = mock_settings
        mock_manifests.return_value = [
            {"id": "SRC-0001", "original_filename": "test.pdf", "type": "pdf", "status": "compiled"},
        ]
        rows, status = handle_refresh_files()
        assert len(rows) == 1
        assert "1 条记录" in status

    @patch("dochris.web.app.get_settings")
    @patch("dochris.web.app.get_all_manifests")
    def test_handle_refresh_status(
        self,
        mock_manifests: MagicMock,
        mock_get_settings: MagicMock,
        mock_settings: MagicMock,
    ) -> None:
        """刷新系统状态"""
        mock_get_settings.return_value = mock_settings
        mock_manifests.return_value = []
        result = handle_refresh_status()
        assert "系统信息" in result

    @patch("dochris.web.app.get_settings")
    @patch("dochris.web.app.get_all_manifests")
    def test_handle_refresh_quality(
        self,
        mock_manifests: MagicMock,
        mock_get_settings: MagicMock,
    ) -> None:
        """刷新质量数据"""
        mock_get_settings.return_value = MagicMock(min_quality_score=85)
        mock_manifests.return_value = []
        result = handle_refresh_quality()
        assert "暂无" in result or "质量概览" in result

    def test_handle_upload_no_files(self) -> None:
        """无文件上传"""
        result = handle_upload([])
        assert "未选择文件" in result


# ============================================================
# 测试: CLI 集成
# ============================================================


class TestCLIServe:
    """测试 CLI serve 命令"""

    @patch("dochris.cli.cli_serve._launch_web")
    def test_serve_web_flag(self, mock_launch_web: MagicMock) -> None:
        """--web 参数启动 Web UI"""
        from dochris.cli.cli_serve import cmd_serve

        args = MagicMock()
        args.web = True
        args.host = "0.0.0.0"
        args.web_port = 7860
        mock_launch_web.return_value = 0

        result = cmd_serve(args)
        assert result == 0
        mock_launch_web.assert_called_once_with(args)

    @patch("dochris.cli.cli_serve._launch_api")
    def test_serve_api_default(self, mock_launch_api: MagicMock) -> None:
        """默认启动 API"""
        from dochris.cli.cli_serve import cmd_serve

        args = MagicMock()
        args.web = False
        mock_launch_api.return_value = 0

        result = cmd_serve(args)
        assert result == 0
        mock_launch_api.assert_called_once_with(args)
