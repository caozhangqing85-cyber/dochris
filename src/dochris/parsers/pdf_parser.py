#!/usr/bin/env python3
"""
PDF 文件解析 (多个解析器降级)
"""

import logging
import subprocess
from collections.abc import Callable
from pathlib import Path

logger = logging.getLogger(__name__)


def parse_with_markitdown(file_path: Path) -> str | None:
    """使用 markitdown 解析"""
    try:
        # 安全验证：确保文件路径有效
        if not file_path.exists():
            logger.warning(f"File not found: {file_path}")
            return None

        # 检查文件扩展名
        if file_path.suffix.lower() != ".pdf":
            logger.warning(f"Not a PDF file: {file_path}")
            return None

        result = subprocess.run(
            ["markitdown", str(file_path)], capture_output=True, text=True, timeout=10
        )

        if result.returncode == 0:
            return result.stdout
        return None
    except FileNotFoundError:
        return None


def parse_with_pypdf2(file_path: Path) -> str | None:
    """使用 PyPDF2 解析"""
    try:
        from PyPDF2 import PdfReader

        with open(file_path, "rb") as f:
            reader = PdfReader(f)
            text = ""
            for page in reader.pages:
                text += page.extract_text()

            return text if len(text) > 100 else None
    except ImportError:
        return None
    except (OSError, ValueError, RuntimeError, KeyError) as e:
        logger.warning(f"PyPDF2 error: {e}")
        return None
    except Exception as e:
        logger.warning(f"PyPDF2 unexpected error: {type(e).__name__}: {e}")
        return None


def parse_with_pdfplumber(file_path: Path) -> str | None:
    """使用 pdfplumber 解析"""
    try:
        import pdfplumber

        with pdfplumber.open(file_path) as pdf:
            text = ""
            for page in pdf.pages:
                text += page.extract_text() or ""

            return text if len(text) > 100 else None
    except ImportError:
        return None
    except (OSError, ValueError, RuntimeError, KeyError) as e:
        logger.warning(f"pdfplumber error: {e}")
        return None
    except Exception as e:
        logger.warning(f"pdfplumber unexpected error: {type(e).__name__}: {e}")
        return None


def parse_with_pymupdf(file_path: Path) -> str | None:
    """使用 PyMuPDF (fitz) 解析，对加密 PDF 兼容性最好"""
    try:
        import fitz  # PyMuPDF

        doc = fitz.open(str(file_path))
        text = ""
        for page in doc:
            text += page.get_text()
        doc.close()

        return text if len(text) > 100 else None
    except ImportError:
        return None
    except Exception as e:
        logger.warning(f"pymupdf error: {type(e).__name__}: {e}")
        return None


def parse_with_tesseract_ocr(file_path: Path) -> str | None:
    """使用 Tesseract OCR 解析"""
    try:
        import tempfile

        # 转换 PDF 为图片（简化实现）
        # 实际应该使用 pdftoppm 或类似工具
        # 需要 pytesseract 和 PIL.Image
        with tempfile.TemporaryDirectory():
            # 这里简化实现，实际需要完整的 OCR 流程
            return None
    except ImportError:
        return None


def parse_pdf(file_path: Path) -> str | None:
    """
    解析 PDF 文件 (降级策略)

    Returns:
        提取的文本，或 None
    """
    # 解析器列表（按优先级排序）
    # pdfplumber 对普通 PDF 最快，pymupdf 对加密 PDF 兼容性最好
    # markitdown 放最后（慢且容易超时）
    parsers: list[tuple[str, Callable[[Path], str | None]]] = [
        ("pdfplumber", parse_with_pdfplumber),
        ("pymupdf", parse_with_pymupdf),
        ("pypdf2", parse_with_pypdf2),
        ("markitdown", parse_with_markitdown),
        ("tesseract_ocr", parse_with_tesseract_ocr),
    ]

    for parser_name, parser_func in parsers:
        try:
            text = parser_func(file_path)

            if text and len(text) > 100:
                logger.info(f"✓ PDF parsed with {parser_name}")
                return text
        except Exception as e:
            logger.warning(f"⚠ {parser_name} failed: {e}")
            continue

    logger.error(
        f"✗ All parsers failed for {Path(file_path).name if isinstance(file_path, str) else file_path.name}"
    )
    return None
