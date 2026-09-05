"""tests/test_compensate_utils.py

补偿工具模块测试
"""

import logging
from unittest.mock import patch

from dochris.compensate.compensate_utils import (
    BATCH_DELAY,
    BATCH_SIZE,
    EBOOK_CONVERT_CMD,
    MAX_CONCURRENCY,
    MODEL_CHAIN,
    OCR_MAX_PAGES,
    OCR_TIMEOUT,
    PDFTOPPM_CMD,
    TESSERACT_CMD,
    CompensateError,
    setup_logging,
)


class TestCompensateError:
    """CompensateError 枚举测试"""

    def test_error_types(self) -> None:
        """测试所有错误类型存在"""
        assert CompensateError.NO_TEXT.value == "no_text"
        assert CompensateError.LLM_FAILED.value == "llm_failed"
        assert CompensateError.FILE_NOT_FOUND.value == "file_not_found"
        assert CompensateError.OCR_FAILED.value == "ocr_failed"
        assert CompensateError.EBOOK_CONVERT_FAILED.value == "ebook_convert_failed"
        assert CompensateError.CONTENT_FILTER.value == "content_filter"
        assert CompensateError.UNKNOWN.value == "unknown"


class TestConfigurationConstants:
    """配置常量测试"""

    def test_command_constants(self) -> None:
        """测试命令常量"""
        assert EBOOK_CONVERT_CMD == "ebook-convert"
        assert TESSERACT_CMD == "tesseract"
        assert PDFTOPPM_CMD == "pdftoppm"

    def test_batch_constants(self) -> None:
        """测试批处理常量"""
        assert MAX_CONCURRENCY == 4
        assert BATCH_SIZE == 30
        assert BATCH_DELAY == 3

    def test_ocr_constants(self) -> None:
        """测试 OCR 常量"""
        assert OCR_MAX_PAGES == 5
        assert OCR_TIMEOUT == 60

    def test_model_chain(self) -> None:
        """测试模型降级链"""
        assert isinstance(MODEL_CHAIN, list)
        assert len(MODEL_CHAIN) == 3
        # 模型链应该包含有效的模型名
        for model in MODEL_CHAIN:
            assert isinstance(model, str)
            assert len(model) > 0


class TestSetupLogging:
    """日志设置测试"""

    def test_setup_logging_returns_logger(self, tmp_path) -> None:
        """测试 setup_logging 返回 logger"""
        workspace = tmp_path / "workspace"
        with patch("logging.basicConfig") as basic_config:
            logger = setup_logging(workspace)
            for handler in basic_config.call_args.kwargs["handlers"]:
                handler.close()

        assert isinstance(logger, logging.Logger)

    def test_setup_logging_creates_log_file(self, tmp_path) -> None:
        """测试 setup_logging 创建日志文件"""
        workspace = tmp_path / "workspace"

        with patch("logging.basicConfig") as basic_config:
            logger = setup_logging(workspace)
            for handler in basic_config.call_args.kwargs["handlers"]:
                handler.close()

        assert isinstance(logger, logging.Logger)
        assert len(list((workspace / "logs").glob("compensate_*.log"))) == 1

    def test_setup_logging_log_file_naming(self, tmp_path) -> None:
        """测试日志文件命名格式"""
        workspace = tmp_path / "workspace"

        with patch("logging.basicConfig") as basic_config:
            _ = setup_logging(workspace)
            for handler in basic_config.call_args.kwargs["handlers"]:
                handler.close()

        logs_dir = workspace / "logs"
        log_files = list(logs_dir.glob("compensate_*.log"))

        assert len(log_files) == 1
        timestamp = log_files[0].stem.removeprefix("compensate_")
        assert len(timestamp) == 15
        assert timestamp[:8].isdigit()
        assert timestamp[8] == "_"
        assert timestamp[9:].isdigit()
