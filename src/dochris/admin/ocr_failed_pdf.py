#!/usr/bin/env python3
"""
OCR处理失败状态的PDF文件（图片PDF/扫描件）
"""

import json
import logging
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path

from dochris.manifest import get_all_manifests, get_default_workspace, update_manifest_status

# 延迟初始化的路径常量（由 _init_paths() 在 __main__ 或 main() 中设置）
WORKSPACE: Path
TRANSCRIPTS_DIR: Path
RAW_DIR: Path
LOGS_PATH: Path

# logger — 延迟初始化由 setup_logging() 在 main() 中设置，但提供模块级默认值避免 NameError
logger = logging.getLogger(__name__)


def _init_paths() -> None:
    """延迟初始化路径常量"""
    global WORKSPACE, TRANSCRIPTS_DIR, RAW_DIR, LOGS_PATH
    WORKSPACE = Path.home() / ".openclaw/knowledge-base"
    TRANSCRIPTS_DIR = WORKSPACE / "transcripts"
    RAW_DIR = WORKSPACE / "raw"
    LOGS_PATH = WORKSPACE / "logs"


def setup_logging() -> logging.Logger:
    LOGS_PATH.mkdir(parents=True, exist_ok=True)
    log_file = LOGS_PATH / f"ocr_failed_pdf_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s.%(msecs)03d [%(levelname)-8s] %(message)s",
        handlers=[
            logging.FileHandler(log_file, encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
    )
    return logging.getLogger()


def get_failed_pdf_manifests() -> list[dict]:
    workspace = get_default_workspace()
    all_failed = get_all_manifests(workspace, status="failed")
    failed_pdfs = [m for m in all_failed if m.get("source_path", "").lower().endswith(".pdf")]
    logger.info(f"📊 找到失败状态的PDF文件: {len(failed_pdfs)} 个")
    return failed_pdfs


def pdf_to_images(pdf_path: Path, output_dir: Path, dpi: int = 200) -> list[Path]:
    """Convert PDF pages to images using pdftoppm"""
    output_dir.mkdir(parents=True, exist_ok=True)
    prefix = output_dir / "page"
    cmd = ["pdftoppm", "-png", "-r", str(dpi), str(pdf_path), str(prefix)]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if result.returncode != 0:
        logger.error(f"pdftoppm failed: {result.stderr}")
        return []
    images = sorted(output_dir.glob("page-*.png"))
    logger.info(f"📄 PDF转图片: {len(images)} 页")
    return images


def ocr_image(image_path: Path, lang: str = "chi_sim+eng") -> str:
    """OCR a single image"""
    try:
        result = subprocess.run(
            ["tesseract", str(image_path), "stdout", "-l", lang, "--psm", "6"],
            capture_output=True,
            text=True,
            timeout=60,
        )
        return result.stdout.strip()
    except (subprocess.TimeoutExpired, OSError, FileNotFoundError) as e:
        logger.error(f"OCR失败 {image_path.name}: {e}")
        return ""


def process_pdf(manifest: dict) -> bool:
    src_id = manifest.get("source_id", "")
    src_path = Path(manifest.get("source_path", ""))
    title = manifest.get("title", src_path.stem)

    if not src_path.exists():
        logger.error(f"❌ 文件不存在: {src_path}")
        return False

    logger.info(f"\n📖 处理: {title}")

    with tempfile.TemporaryDirectory() as tmpdir_str:
        tmpdir = Path(tmpdir_str)
        images = pdf_to_images(src_path, tmpdir)
        if not images:
            return False

        # Limit to first 50 pages for very large PDFs
        if len(images) > 50:
            logger.warning(f"⚠️ PDF超过50页({len(images)}页)，只处理前50页")
            images = images[:50]

        all_text = []
        for i, img in enumerate(images):
            logger.info(f"  OCR第{i + 1}/{len(images)}页...")
            text = ocr_image(img)
            if text:
                all_text.append(f"--- 第{i + 1}页 ---\n{text}")

    if not all_text:
        logger.error("❌ OCR结果为空")
        return False

    full_text = "\n\n".join(all_text)
    logger.info(f"✅ OCR完成: {len(full_text)} 字符")

    # Save transcript
    TRANSCRIPTS_DIR.mkdir(parents=True, exist_ok=True)
    transcript_file = TRANSCRIPTS_DIR / f"{src_id}.txt"
    transcript_file.write_text(full_text, encoding="utf-8")

    # Update manifest
    try:
        update_manifest_status(
            get_default_workspace(),
            src_id,
            "transcribed",
            error_message=str({"text_length": len(full_text)}),
        )
        logger.info(f"✓ Manifest已更新: {src_id}")
    except (OSError, json.JSONDecodeError, ValueError) as e:
        logger.warning(f"Manifest更新失败: {e}")

    return True


def find_existing_transcript(manifest: dict) -> Path | None:
    """查找已有的转录文件，先查 transcripts/，再查 raw/"""
    src_id = manifest.get("source_id", "")
    src_path = manifest.get("source_path", "")
    file_path = manifest.get("file_path", "")

    # 1. 检查 transcripts 目录
    transcript_file = TRANSCRIPTS_DIR / f"{src_id}.txt"
    if transcript_file.exists():
        return transcript_file

    # 2. 在 raw/ 下查找同名 .txt 文件
    stem = Path(src_path).stem if src_path else Path(file_path).stem
    if not stem:
        return None

    for subdir in ["pdfs", "audio", "videos", "articles"]:
        raw_sub = RAW_DIR / subdir
        if raw_sub.exists():
            # 精确匹配
            txt = raw_sub / f"{stem}.txt"
            if txt.exists() and txt.stat().st_size > 200:
                return txt
            # 模糊匹配（去掉特殊字符）
            import re

            clean_stem = re.sub(r"[\s\-_|/\\:：？?！!（）()【】\[\]]", "", stem)
            for txt in raw_sub.glob("*.txt"):
                clean_name = re.sub(r"[\s\-_|/\\:：？?！!（）()【】\[\]]", "", txt.stem)
                if (
                    clean_name
                    and clean_stem
                    and (clean_stem in clean_name or clean_name in clean_stem)
                ) and txt.stat().st_size > 200:
                    return txt

    return None


def main() -> None:
    global logger
    _init_paths()
    logger = setup_logging()

    manifests = get_failed_pdf_manifests()
    if not manifests:
        logger.info("没有需要处理的PDF文件")
        return

    success = 0
    skip = 0
    fail = 0

    for i, m in enumerate(manifests, 1):
        src_id = m.get("source_id", "")
        title = m.get("title", "")
        logger.info(f"\n{'=' * 60}")
        logger.info(f"[{i}/{len(manifests)}] {src_id}: {title}")

        # 检查已有转录文件（transcripts/ 或 raw/）
        existing = find_existing_transcript(m)
        if existing:
            logger.info(f"⏭️ 已有转录文件 ({existing})，跳过OCR")
            skip += 1
            continue

        try:
            if process_pdf(m):
                success += 1
            else:
                fail += 1
        except (OSError, subprocess.TimeoutExpired, RuntimeError) as e:
            logger.error(f"处理异常: {e}")
            fail += 1

    logger.info(f"\n{'=' * 60}")
    logger.info(f"📊 完成! 成功: {success}, 跳过: {skip}, 失败: {fail}, 总计: {len(manifests)}")


if __name__ == "__main__":
    main()
