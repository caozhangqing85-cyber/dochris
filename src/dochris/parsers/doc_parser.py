#!/usr/bin/env python3
"""
文档文件解析
支持 .md/.txt/.rst/.html 以及 .docx/.pptx/.xlsx
"""

import logging
import re
from pathlib import Path

logger = logging.getLogger(__name__)


def detect_document_file(file_path: Path) -> bool:
    """检测是否为文档文件"""
    doc_extensions = {
        ".md",
        ".txt",
        ".rst",
        ".html",
        ".docx",
        ".pptx",
        ".xlsx",  # Office 文档
    }
    return file_path.suffix.lower() in doc_extensions


def parse_document(file_path: Path) -> str | None:
    """
    解析文档文件

    - 纯文本文件（.md/.txt/.rst/.html）直接读取
    - Office 文档（.docx/.pptx/.xlsx）通过 markitdown 解析

    Returns:
        提取的文本
    """
    ext = file_path.suffix.lower()

    # 纯文本文件直接读取
    if ext in {".md", ".txt", ".rst", ".html", ".htm"}:
        try:
            return file_path.read_text(encoding="utf-8", errors="replace")
        except OSError as e:
            logger.warning(f"Failed to read document {file_path}: {e}")
            return None

    # Office 文档用 markitdown 解析
    if ext in {".docx", ".pptx", ".xlsx"}:
        return parse_office_document(file_path)

    # 其他格式尝试纯文本读取
    try:
        return file_path.read_text(encoding="utf-8", errors="replace")
    except (OSError, UnicodeDecodeError):
        return None


def parse_office_document(file_path: Path) -> str | None:
    """
    使用 markitdown 解析 Office 文档（.docx/.pptx/.xlsx）

    Args:
        file_path: Office 文件路径

    Returns:
        提取的文本，失败返回 None
    """
    try:
        from markitdown import MarkItDown

        md = MarkItDown()
        result = md.convert(str(file_path))
        text = result.text_content

        if text and len(text.strip()) > 50:
            # 清理 base64 内嵌图片数据（markitdown 会将 docx 中的图片转为 base64）
            text = re.sub(r"!\[\]\(data:image/[^)]+\)", "", text)
            text = re.sub(r"!\[.*?\]\(data:image/[^)]+\)", "", text)
            text = text.strip()
            if len(text) > 50:
                logger.info(f"markitdown 解析成功: {file_path.name} ({len(text)}字)")
                return text
            else:
                logger.warning(f"markitdown 清理后内容过短: {file_path.name}")
                return None
        else:
            logger.warning(f"markitdown 解析结果为空或过短: {file_path.name}")
            return None

    except ImportError:
        logger.warning("markitdown 未安装，无法解析 Office 文档。安装: pip install markitdown[all]")
        return None
    except Exception as e:
        logger.warning(f"markitdown 解析失败 {file_path.name}: {e}")
        return None
