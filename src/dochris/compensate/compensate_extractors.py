"""
补偿重试工具：增强文本提取（ebook/PDF OCR/通用补偿）
"""

import os
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dochris.compensate.compensate_utils import (
    EBOOK_CONVERT_CMD,
    OCR_MAX_PAGES,
    OCR_TIMEOUT,
    PDFTOPPM_CMD,
    TESSERACT_CMD,
)
from dochris.exceptions import TextExtractionError
from dochris.settings import get_settings

_s = get_settings()
MAX_CONTENT_CHARS = _s.max_content_chars
MIN_AUDIO_TEXT_LENGTH = _s.min_text_length

# ============================================================
# 本地文本提取函数（替代不存在的 extract_text_v4）
# ============================================================


def extract_text_from_file(file_path: Path, logger) -> str | None:
    """从文件提取文本，根据扩展名选择解析器

    Args:
        file_path: 文件路径
        logger: 日志记录器

    Returns:
        提取的文本，失败返回 None
    """
    ext = file_path.suffix.lower()

    # PDF 使用 markitdown
    if ext == ".pdf":
        from dochris.parsers.pdf_parser import parse_pdf

        try:
            text = parse_pdf(file_path)
            if text:
                logger.debug(f"PDF 提取成功: {file_path.name}")
                return text[:MAX_CONTENT_CHARS]
        except TextExtractionError as e:
            logger.warning(f"PDF 提取失败 {file_path.name}: {e}")
        except Exception as e:
            # 顶层兜底：捕获未预期的错误
            logger.warning(f"PDF 未预期错误 {file_path.name}: {e}")

    # 文档文件
    elif ext in (".md", ".txt", ".rst", ".html", ".htm", ".docx", ".doc", ".pptx", ".ppt", ".xlsx"):
        from dochris.parsers.doc_parser import parse_document

        try:
            text: str | None = parse_document(file_path)
            if text:
                logger.debug(f"文档提取成功: {file_path.name}")
                return text[:MAX_CONTENT_CHARS]
        except TextExtractionError as e:
            logger.warning(f"文档提取失败 {file_path.name}: {e}")
        except Exception as e:
            # 顶层兜底：捕获未预期的错误
            logger.warning(f"文档未预期错误 {file_path.name}: {e}")

    # 代码文件（直接读取）
    elif ext in (".py", ".js", ".ts", ".java", ".go", ".rs", ".c", ".cpp", ".h", ".css", ".json", ".xml"):
        try:
            text = file_path.read_text(encoding="utf-8", errors="replace")
            return text[:MAX_CONTENT_CHARS]
        except (OSError, UnicodeDecodeError, TextExtractionError) as e:
            logger.warning(f"代码文件读取失败 {file_path.name}: {e}")
        except Exception as e:
            # 顶层兜底：捕获未预期的错误
            logger.warning(f"代码文件未预期错误 {file_path.name}: {e}")

    # 默认尝试直接读取
    else:
        try:
            text = file_path.read_text(encoding="utf-8", errors="replace")
            if len(text) > 100:
                return text[:MAX_CONTENT_CHARS]
        except (OSError, UnicodeDecodeError, TextExtractionError):
            pass
        except Exception:
            # 顶层兜底：静默忽略其他异常
            pass

    return None


def extract_ebook_text(filepath: Path, logger) -> str | None:
    """用 Calibre ebook-convert 提取 ebook 文本

    支持: .mobi, .azw3, .epub 等格式
    """
    if not filepath.exists():
        logger.warning(f"ebook 文件不存在: {filepath}")
        return None

    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as tmp:
            tmp_path = tmp.name

        result = subprocess.run(
            [EBOOK_CONVERT_CMD, str(filepath), tmp_path],
            capture_output=True,
            text=True,
            timeout=120,
        )

        if result.returncode != 0:
            logger.warning(f"ebook-convert 失败 {filepath.name}: {result.stderr[:200]}")
            return None

        text = Path(tmp_path).read_text(encoding="utf-8", errors="replace")

        if text.strip():
            text = text.strip()[:MAX_CONTENT_CHARS]
            logger.info(f"ebook-convert 成功: {filepath.name}, 文本长度: {len(text)}")
            return text
        else:
            logger.warning(f"ebook-convert 结果为空: {filepath.name}")
            return None

    except subprocess.TimeoutExpired:
        logger.warning(f"ebook-convert 超时: {filepath.name}")
        return None
    except (OSError, FileNotFoundError) as e:
        logger.warning(f"ebook-convert 异常 {filepath.name}: {e}")
        return None
    finally:
        if tmp_path:
            Path(tmp_path).unlink(missing_ok=True)


def extract_pdf_with_ocr(filepath: Path, logger) -> str | None:
    """对扫描 PDF 使用 OCR 提取文本

    流程: pdftoppm 转 PNG → tesseract OCR → 拼接文本
    """
    if not filepath.exists():
        return None

    try:
        import fitz
    except ImportError:
        logger.warning("PyMuPDF (fitz) 未安装，无法进行 OCR")
        return None

    # 先用 PyMuPDF 检查是否有文字层
    try:
        with fitz.open(str(filepath)) as doc:
            has_text = False
            for i in range(min(3, doc.page_count)):
                if doc[i].get_text().strip():
                    has_text = True
                    break

        if has_text:
            logger.debug(f"PDF 有文字层，跳过 OCR: {filepath.name}")
            return None  # 交给主提取流程
    except (OSError, RuntimeError, ImportError) as e:
        logger.warning(f"PyMuPDF 检查失败: {e}")

    # 检查 tesseract 和 pdftoppm 是否可用
    try:
        subprocess.run([TESSERACT_CMD, "--version"], capture_output=True, timeout=5)
        subprocess.run([PDFTOPPM_CMD, "-v"], capture_output=True, timeout=5)
    except (FileNotFoundError, subprocess.TimeoutExpired):
        logger.warning("tesseract 或 pdftoppm 不可用，无法 OCR")
        return None

    # 转图片 + OCR
    text_parts = []
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_prefix = os.path.join(tmp_dir, "page")

        try:
            # PDF 转图片（限制页数）
            result = subprocess.run(
                [
                    PDFTOPPM_CMD,
                    "-png",
                    "-l",
                    str(OCR_MAX_PAGES),
                    "-r",
                    "200",
                    str(filepath),
                    tmp_prefix,
                ],
                capture_output=True,
                text=True,
                timeout=120,
            )
            if result.returncode != 0:
                logger.warning(f"pdftoppm 失败: {result.stderr[:200]}")
                return None

            # 找到生成的图片
            page_images = sorted(Path(tmp_dir).glob("page-*.png"))
            if not page_images:
                logger.warning(f"pdftoppm 未生成图片: {filepath.name}")
                return None

            # 逐页 OCR
            for img_path in page_images:
                try:
                    ocr_result = subprocess.run(
                        [TESSERACT_CMD, str(img_path), "stdout", "-l", "chi_sim+eng", "--psm", "6"],
                        capture_output=True,
                        text=True,
                        timeout=OCR_TIMEOUT,
                    )
                    if ocr_result.returncode == 0 and ocr_result.stdout.strip():
                        text_parts.append(ocr_result.stdout.strip())
                except subprocess.TimeoutExpired:
                    logger.warning(f"OCR 超时: {img_path.name}")
                    continue
                except (OSError, FileNotFoundError) as e:
                    logger.warning(f"OCR 异常: {e}")
                    continue

        except subprocess.TimeoutExpired:
            logger.warning(f"pdftoppm 超时: {filepath.name}")
            return None

    if text_parts:
        full_text = "\n\n".join(text_parts)[:MAX_CONTENT_CHARS]
        logger.info(
            f"OCR 成功: {filepath.name}, 文本长度: {len(full_text)}, 页数: {len(text_parts)}"
        )
        return full_text
    else:
        logger.warning(f"OCR 未提取到文本: {filepath.name}")
        return None


def extract_text_compensated(filepath: Path, manifest: dict, logger) -> tuple[str | None, str]:
    """补偿文本提取

    Returns:
        (text, extraction_method) 元组
        extraction_method: "original" / "ebook_convert" / "ocr" / "failed"
    """
    file_type = manifest.get("type", "")
    ext = filepath.suffix.lower()

    # 1. 先尝试原始提取
    original_text = extract_text_from_file(filepath, logger)
    if original_text and len(original_text.strip()) >= MIN_AUDIO_TEXT_LENGTH:
        return original_text, "original"

    # 2. ebook 补偿：.mobi 用 Calibre
    if file_type == "ebook" and ext in (".mobi", ".azw3"):
        logger.info(f"尝试 Calibre 转换: {filepath.name}")
        ebook_text = extract_ebook_text(filepath, logger)
        if ebook_text and len(ebook_text.strip()) >= MIN_AUDIO_TEXT_LENGTH:
            return ebook_text, "ebook_convert"

    # 3. PDF 补偿：OCR
    if file_type == "pdf" and ext == ".pdf":
        logger.info(f"尝试 OCR: {filepath.name}")
        ocr_text = extract_pdf_with_ocr(filepath, logger)
        if ocr_text and len(ocr_text.strip()) >= MIN_AUDIO_TEXT_LENGTH:
            return ocr_text, "ocr"

    # 4. other 类型：尝试 markitdown
    if file_type == "other" and ext in (".mhtml", ".pptx", ".ppt", ".xmind"):
        logger.info(f"尝试 markitdown: {filepath.name}")
        try:
            result = subprocess.run(
                ["markitdown", str(filepath)],
                capture_output=True,
                text=True,
                timeout=120,
            )
            if result.returncode == 0 and result.stdout.strip():
                text = result.stdout.strip()[:MAX_CONTENT_CHARS]
                if len(text) >= MIN_AUDIO_TEXT_LENGTH:
                    return text, "markitdown"
        except (subprocess.TimeoutExpired, OSError, FileNotFoundError) as e:
            logger.warning(f"markitdown 补偿失败: {e}")

    return None, "failed"
