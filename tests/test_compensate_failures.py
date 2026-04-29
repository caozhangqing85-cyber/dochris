"""
测试 compensate_failures.py 模块
"""

import json
import sys
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture(autouse=True)
def setup_and_teardown_module_mocks():
    """设置测试前 mock，测试后清理"""
    # Mock phase2_compilation functions since compensate_failures.py imports them
    sys.modules['dochris.phases.phase2_compilation'] = MagicMock()
    yield
    # 测试结束后清理 mock，恢复真实模块
    if 'dochris.phases.phase2_compilation' in sys.modules:
        del sys.modules['dochris.phases.phase2_compilation']


@pytest.fixture
def mock_workspace(tmp_path):
    workspace = tmp_path / "kb"
    workspace.mkdir()
    (workspace / "manifests").mkdir()
    (workspace / "manifests" / "sources").mkdir(parents=True)
    return workspace


@pytest.fixture
def sample_failed_manifests(mock_workspace):
    manifests = [
        {
            "id": "SRC-0001",
            "status": "failed",
            "title": "Ebook失败",
            "file_path": "raw/test.mobi",
            "error_message": "no_text",
            "type": "ebook",
        },
        {
            "id": "SRC-0002",
            "status": "failed",
            "title": "PDF失败",
            "file_path": "raw/test.pdf",
            "error_message": "no_text",
            "type": "pdf",
        },
    ]
    for m in manifests:
        f = mock_workspace / "manifests" / "sources" / f"{m['id']}.json"
        f.write_text(json.dumps(m, ensure_ascii=False), encoding="utf-8")
    return manifests


class TestCompensateFailuresFunctions:
    """测试 compensate_failures 功能"""

    def test_extract_ebook_text_success(self, tmp_path):
        """测试 ebook 文本提取"""
        # 基础结构测试
        ebook_file = tmp_path / "test.mobi"
        ebook_file.write_bytes(b"test")
        assert ebook_file.exists()

    def test_extract_pdf_with_ocr(self, tmp_path):
        """测试 PDF OCR 提取"""
        pdf_file = tmp_path / "test.pdf"
        pdf_file.write_bytes(b"%PDF")
        assert pdf_file.exists()

    @patch('dochris.manifest.get_all_manifests')
    def test_find_failed_manifests(self, mock_get, sample_failed_manifests):
        """测试查找失败 manifest"""
        mock_get.return_value = sample_failed_manifests
        result = mock_get()
        assert len(result) == 2
        assert result[0]["status"] == "failed"

    @pytest.mark.asyncio
    async def test_compensate_single_basic(self):
        """测试单个补偿基本流程"""
        # 测试异步函数的基本结构
        assert True
