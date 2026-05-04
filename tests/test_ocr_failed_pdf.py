"""
测试 ocr_failed_pdf.py 模块
"""

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest

# 添加 scripts 目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))


@pytest.fixture
def mock_workspace(tmp_path):
    workspace = tmp_path / "kb"
    workspace.mkdir()
    (workspace / "manifests").mkdir()
    (workspace / "manifests" / "sources").mkdir(parents=True)
    return workspace


@pytest.fixture
def sample_pdf_manifests(mock_workspace):
    manifests = [
        {
            "id": "SRC-0001",
            "status": "failed",
            "title": "PDF文件",
            "source_path": "raw/test.pdf",
            "file_path": "raw/test.pdf",
            "type": "pdf",
        },
    ]
    for m in manifests:
        f = mock_workspace / "manifests" / "sources" / f"{m['id']}.json"
        f.write_text(json.dumps(m, ensure_ascii=False), encoding="utf-8")
    return manifests


class TestGetFailedPDFManifests:
    @patch("dochris.admin.ocr_failed_pdf.get_all_manifests")
    @patch("dochris.admin.ocr_failed_pdf.get_default_workspace")
    def test_get_failed_pdf_manifests(self, mock_ws, mock_get, sample_pdf_manifests):
        from dochris.admin.ocr_failed_pdf import get_failed_pdf_manifests

        mock_ws.return_value = mock_workspace
        mock_get.return_value = sample_pdf_manifests
        result = get_failed_pdf_manifests()
        assert len(result) > 0


class TestPDFToImages:
    @patch("dochris.admin.ocr_failed_pdf.subprocess.run")
    def test_pdf_to_images(self, mock_run, tmp_path):
        from dochris.admin.ocr_failed_pdf import pdf_to_images

        mock_run.return_value = MagicMock(returncode=0)
        pdf_file = tmp_path / "test.pdf"
        output_dir = tmp_path / "output"
        result = pdf_to_images(pdf_file, output_dir)
        assert isinstance(result, list)


class TestOCRImage:
    @patch("dochris.admin.ocr_failed_pdf.subprocess.run")
    def test_ocr_image(self, mock_run, tmp_path):
        from dochris.admin.ocr_failed_pdf import ocr_image

        mock_run.return_value = MagicMock(stdout="OCR 文本", returncode=0)
        img_file = tmp_path / "page.png"
        result = ocr_image(img_file)
        assert result == "OCR 文本"


class TestFindExistingTranscript:
    @patch("dochris.admin.ocr_failed_pdf.TRANSCRIPTS_DIR", create=True)
    @patch("dochris.admin.ocr_failed_pdf.RAW_DIR", create=True)
    def test_find_existing_transcript(self, mock_raw, mock_transcripts, tmp_path):
        from dochris.admin.ocr_failed_pdf import find_existing_transcript

        # 设置 mock，确保 exists() 和 stat().st_size 返回合适的值
        mock_transcripts.__truediv__ = Mock(return_value=Mock(exists=Mock(return_value=False)))
        mock_raw.__truediv__ = Mock(return_value=Mock(exists=Mock(return_value=False)))
        manifest = {"source_id": "SRC-0001", "source_path": "test.pdf"}
        result = find_existing_transcript(manifest)
        assert result is None or isinstance(result, Path)
