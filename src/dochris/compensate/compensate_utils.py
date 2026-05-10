"""
补偿重试工具：错误枚举、日志配置
"""

import datetime
import logging
import sys
from enum import Enum

from dochris.settings import get_default_workspace

KB_PATH = get_default_workspace()

# ============================================================
# 配置
# ============================================================

EBOOK_CONVERT_CMD = "ebook-convert"
TESSERACT_CMD = "tesseract"
PDFTOPPM_CMD = "pdftoppm"

MAX_CONCURRENCY = 4
BATCH_SIZE = 30
BATCH_DELAY = 3
OCR_MAX_PAGES = 5  # OCR 最多处理前 5 页
OCR_TIMEOUT = 60  # 每页 OCR 超时

# 模型降级链
import os

MODEL_CHAIN = [
    os.environ.get("MODEL", "glm-4-flash"),
    "glm-4.7",
    "glm-5.1",
]


# ============================================================
# 错误分类枚举
# ============================================================


class CompensateError(Enum):
    NO_TEXT = "no_text"
    LLM_FAILED = "llm_failed"
    FILE_NOT_FOUND = "file_not_found"
    OCR_FAILED = "ocr_failed"
    EBOOK_CONVERT_FAILED = "ebook_convert_failed"
    CONTENT_FILTER = "content_filter"
    UNKNOWN = "unknown"


# ============================================================
# 日志
# ============================================================


def setup_logging() -> logging.Logger:
    log_dir = KB_PATH / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / f"compensate_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s.%(msecs)03d [%(levelname)-8s] %(message)s",
        handlers=[
            logging.FileHandler(log_file, encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
    )
    return logging.getLogger()
