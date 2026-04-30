"""测试 compensate/compensate_utils.py 模块"""

import logging
from unittest.mock import MagicMock, patch


class TestCompensateError:
    """测试 CompensateError 枚举"""

    def test_all_error_types(self):
        from dochris.compensate.compensate_utils import CompensateError

        assert CompensateError.NO_TEXT.value == "no_text"
        assert CompensateError.LLM_FAILED.value == "llm_failed"
        assert CompensateError.FILE_NOT_FOUND.value == "file_not_found"
        assert CompensateError.OCR_FAILED.value == "ocr_failed"
        assert CompensateError.EBOOK_CONVERT_FAILED.value == "ebook_convert_failed"
        assert CompensateError.CONTENT_FILTER.value == "content_filter"
        assert CompensateError.UNKNOWN.value == "unknown"

    def test_error_count(self):
        from dochris.compensate.compensate_utils import CompensateError

        assert len(CompensateError) == 7


class TestSetupLogging:
    """测试 setup_logging"""

    @patch("dochris.compensate.compensate_utils.KB_PATH")
    def test_returns_logger(self, mock_kb_path, tmp_path):
        from dochris.compensate.compensate_utils import setup_logging

        mock_kb_path.__truediv__ = lambda self, other: tmp_path / other
        mock_kb_path.mkdir = MagicMock()

        # 直接测试返回值类型
        with patch("logging.basicConfig"):
            logger = setup_logging()
            assert isinstance(logger, logging.Logger)


class TestConstants:
    """测试常量配置"""

    def test_ebook_convert_cmd(self):
        from dochris.compensate.compensate_utils import EBOOK_CONVERT_CMD
        assert EBOOK_CONVERT_CMD == "ebook-convert"

    def test_tesseract_cmd(self):
        from dochris.compensate.compensate_utils import TESSERACT_CMD
        assert TESSERACT_CMD == "tesseract"

    def test_pdftoppm_cmd(self):
        from dochris.compensate.compensate_utils import PDFTOPPM_CMD
        assert PDFTOPPM_CMD == "pdftoppm"

    def test_max_concurrency(self):
        from dochris.compensate.compensate_utils import MAX_CONCURRENCY
        assert MAX_CONCURRENCY == 4

    def test_batch_size(self):
        from dochris.compensate.compensate_utils import BATCH_SIZE
        assert BATCH_SIZE == 30

    def test_batch_delay(self):
        from dochris.compensate.compensate_utils import BATCH_DELAY
        assert BATCH_DELAY == 3

    def test_ocr_max_pages(self):
        from dochris.compensate.compensate_utils import OCR_MAX_PAGES
        assert OCR_MAX_PAGES == 5

    def test_ocr_timeout(self):
        from dochris.compensate.compensate_utils import OCR_TIMEOUT
        assert OCR_TIMEOUT == 60

    def test_model_chain(self):
        from dochris.compensate.compensate_utils import MODEL_CHAIN
        assert isinstance(MODEL_CHAIN, list)
        assert len(MODEL_CHAIN) >= 2
