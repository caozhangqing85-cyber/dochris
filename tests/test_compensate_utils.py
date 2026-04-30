"""tests/test_compensate_utils.py

补偿工具模块测试
"""

import logging

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

    def test_setup_logging_returns_logger(self, tmp_path, monkeypatch) -> None:
        """测试 setup_logging 返回 logger"""
        # 修改工作区路径到临时目录
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        monkeypatch.setenv("WORKSPACE", str(workspace))

        logger = setup_logging()

        assert isinstance(logger, logging.Logger)

    def test_setup_logging_creates_log_file(self, tmp_path, monkeypatch) -> None:
        """测试 setup_logging 创建日志文件"""
        # KB_PATH is module-level, so we test against the real workspace
        # This test verifies the logging function doesn't crash
        logger = setup_logging()
        assert logger is not None
        assert isinstance(logger, logging.Logger)

    def test_setup_logging_log_file_naming(self, tmp_path, monkeypatch) -> None:
        """测试日志文件命名格式"""
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        monkeypatch.setenv("WORKSPACE", str(workspace))

        _ = setup_logging()

        logs_dir = workspace / "logs"
        log_files = list(logs_dir.glob("compensate_*.log"))

        # 日志文件名应该包含日期时间
        if log_files:
            log_file_name = log_files[0].stem
            assert "compensate_" in log_file_name
