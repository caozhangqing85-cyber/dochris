#!/usr/bin/env python3
"""
Phase 1: 数据摄入（v2 - manifest 集成版）
扫描资料文件夹，按文件类型分类到 raw/，提取元数据，使用符号链接
支持增量处理和文件去重
新增：为每个来源创建 manifest 并追加到 source_index.csv
"""

import hashlib
import json
import logging
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

# 导入统一配置
sys.path.insert(0, str(Path(__file__).parent))
from dochris.log import append_log
from dochris.manifest import (
    append_to_index,
    create_manifest,
    get_next_src_id,
)
from dochris.settings import (
    LOG_DATE_FORMAT,
    LOG_FORMAT_SIMPLE,
    MAX_FILE_SIZE,
    OBSIDIAN_PATHS,
    SOURCE_PATH,
    get_default_workspace,
    get_file_category,
    get_logs_dir,
    get_progress_file,
    get_raw_dir,
)

# 路径配置（从 config 导入）
KB_PATH = get_default_workspace()
RAW_PATH = get_raw_dir()
LOGS_PATH = get_logs_dir()
PROGRESS_FILE = get_progress_file()


def setup_logging() -> logging.Logger:
    """设置日志系统

    Returns:
        配置好的 logger 实例
    """
    LOGS_PATH.mkdir(parents=True, exist_ok=True)
    log_file = LOGS_PATH / f"phase1_{datetime.now().strftime(LOG_DATE_FORMAT)}.log"
    logger = logging.getLogger("phase1")
    logger.setLevel(logging.DEBUG)

    fh = logging.FileHandler(log_file, encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)

    fmt = logging.Formatter(LOG_FORMAT_SIMPLE)
    fh.setFormatter(fmt)
    ch.setFormatter(fmt)

    logger.addHandler(fh)
    logger.addHandler(ch)
    return logger


def load_progress() -> dict:
    """加载 Phase 1 进度

    Returns:
        包含 phase1/phase2/phase3 进度的字典
    """
    default = {
        "phase1": {
            "ingested_files": {},
            "hash_index": {},
            "stats": {"total": 0, "linked": 0, "skipped": 0, "failed": 0},
            "last_update": None,
        },
        "phase2": {},
        "phase3": {},
    }
    if PROGRESS_FILE.exists():
        try:
            data = json.loads(PROGRESS_FILE.read_text(encoding="utf-8"))
            # Merge with defaults to ensure phase1 key exists
            for key, val in default.items():
                if key not in data:
                    data[key] = val
            if "ingested_files" not in data["phase1"]:
                data["phase1"]["ingested_files"] = {}
            if "hash_index" not in data["phase1"]:
                data["phase1"]["hash_index"] = {}
            if "stats" not in data["phase1"]:
                data["phase1"]["stats"] = {"total": 0, "linked": 0, "skipped": 0, "failed": 0}
            return data
        except (json.JSONDecodeError, OSError, UnicodeDecodeError):
            pass
    return default


def save_progress(data: dict) -> None:
    """保存进度到文件

    Args:
        data: 进度数据字典
    """
    data["phase1"]["last_update"] = datetime.now().isoformat()
    PROGRESS_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def file_hash(filepath: Path) -> str | None:
    """计算文件 SHA256 哈希

    Args:
        filepath: 文件路径

    Returns:
        十六进制哈希字符串，文件不存在或读取失败时返回 None
    """
    try:
        h = hashlib.sha256()
        with open(filepath, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                h.update(chunk)
        return h.hexdigest()
    except (FileNotFoundError, OSError):
        return None


def get_audio_duration(filepath: Path) -> float | None:
    """获取音频/视频时长（秒）

    Args:
        filepath: 音视频文件路径

    Returns:
        时长（秒），失败时返回 None
    """
    import logging
    _logger = logging.getLogger(__name__)
    # 安全验证：确保文件路径存在
    try:
        if not filepath.exists():
            return None
        # 符号链接指向外部路径时仍然允许（源文件可能通过符号链接组织）
    except (OSError, RuntimeError) as e:
        _logger.warning(f"Path validation failed for {filepath}: {e}")
        return None

    try:
        result = subprocess.run(
            ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", str(filepath)],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            info = json.loads(result.stdout)
            return float(info.get("format", {}).get("duration", 0))
    except (
        subprocess.TimeoutExpired,
        json.JSONDecodeError,
        FileNotFoundError,
        ValueError,
        KeyError,
    ):
        pass
    return None


def scan_obsidian_vault(vault_path: Path, logger: logging.Logger) -> list[dict]:
    """扫描 Obsidian vault 中的 markdown 文件

    Args:
        vault_path: Obsidian vault 目录路径
        logger: 日志记录器

    Returns:
        文件信息字典列表
    """
    files: list[dict] = []
    if not vault_path.exists():
        return files

    for md_file in vault_path.rglob("*.md"):
        try:
            stat = md_file.stat()
            files.append(
                {
                    "path": str(md_file),
                    "name": md_file.name,
                    "size": stat.st_size,
                    "ext": ".md",
                    "category": "articles",
                    "mtime": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                    "type": "obsidian",
                    "source_vault": str(vault_path),
                }
            )
        except OSError as e:
            logger.warning(f"Cannot stat {md_file}: {e}")
    return files


def scan_source_dir(source_path: Path, logger: logging.Logger) -> list[dict]:
    """扫描源目录中的所有文件

    Args:
        source_path: 源目录路径
        logger: 日志记录器

    Returns:
        文件信息字典列表
    """
    files: list[dict] = []
    if not source_path.exists():
        logger.warning(f"Source path does not exist: {source_path}")
        return files

    for filepath in source_path.rglob("*"):
        if not filepath.is_file():
            continue

        ext = filepath.suffix.lower()
        category = get_file_category(ext)

        if category is None:
            continue

        try:
            stat = filepath.stat()
            if stat.st_size > MAX_FILE_SIZE:
                logger.debug(f"Skipping large file: {filepath} ({stat.st_size} bytes)")
                continue
            if stat.st_size == 0:
                continue

            entry: dict = {
                "path": str(filepath),
                "name": filepath.name,
                "size": stat.st_size,
                "ext": ext,
                "category": category,
                "mtime": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                "type": "file",
            }

            # 音视频获取时长
            if category in ("audio", "videos"):
                duration = get_audio_duration(filepath)
                if duration:
                    entry["duration_seconds"] = duration
                    mins = int(duration // 60)
                    entry["duration_display"] = f"{mins // 60}h{mins % 60}m"

            files.append(entry)
        except OSError as e:
            logger.warning(f"Cannot stat {filepath}: {e}")

    return files


def ingest_file(entry: dict, progress: dict, logger: logging.Logger) -> bool:
    """使用符号链接将文件摄入到 raw/

    Args:
        entry: 文件信息字典
        progress: 进度数据字典
        logger: 日志记录器

    Returns:
        成功返回 True，失败返回 False
    """
    src = Path(entry["path"])
    if not src.exists():
        logger.warning(f"源文件不存在: {src}")
        progress["phase1"]["stats"]["failed"] += 1
        return False

    category = entry["category"]
    hash_val = file_hash(src)

    phase1 = progress["phase1"]

    # 去重检查
    if hash_val in phase1["hash_index"]:
        existing = phase1["hash_index"][hash_val]
        logger.debug(f"Duplicate: {entry['name']} == {existing}")
        phase1["stats"]["skipped"] += 1
        return True

    # 创建目标路径
    cat_dir = RAW_PATH / category
    cat_dir.mkdir(parents=True, exist_ok=True)

    # 避免文件名冲突
    dst_name = entry["name"]
    dst_path = cat_dir / dst_name
    counter = 1
    max_attempts = 1000
    while dst_path.exists() and counter < max_attempts:
        stem = Path(dst_name).stem
        suffix = Path(dst_name).suffix
        dst_name = f"{stem}_{counter}{suffix}"
        dst_path = cat_dir / dst_name
        counter += 1

    if counter >= max_attempts:
        logger.error(f"无法解决文件名冲突: {dst_name}")
        phase1["stats"]["failed"] += 1
        return False

    # 创建符号链接
    try:
        os.symlink(str(src.resolve()), str(dst_path))
    except OSError as e:
        logger.warning(f"Symlink failed for {src}: {e}, trying copy")
        try:
            import shutil

            shutil.copy2(str(src), str(dst_path))
        except (OSError, shutil.Error) as e2:
            logger.error(f"Copy also failed for {src}: {e2}")
            phase1["stats"]["failed"] += 1
            return False

    # 记录进度
    rel_dst = str(dst_path.relative_to(KB_PATH))
    phase1["ingested_files"][rel_dst] = {
        "source": str(src),
        "hash": hash_val,
        "category": category,
        "name": entry["name"],
        "size": entry["size"],
        "ingested_at": datetime.now().isoformat(),
    }
    if "duration_seconds" in entry:
        phase1["ingested_files"][rel_dst]["duration_seconds"] = entry["duration_seconds"]
        phase1["ingested_files"][rel_dst]["duration_display"] = entry.get("duration_display", "")

    phase1["hash_index"][hash_val] = entry["name"]
    phase1["stats"]["linked"] += 1

    # 创建 manifest 并追加到 source_index.csv
    try:
        src_id = get_next_src_id(KB_PATH)
        manifest = create_manifest(
            workspace_path=KB_PATH,
            src_id=src_id,
            title=entry["name"],
            file_type=category,
            source_path=src.resolve(),
            file_path=rel_dst,
            content_hash=hash_val,
            size_bytes=entry.get("size", 0),
        )
        append_to_index(KB_PATH, manifest)
        logger.info(f"  [{category}] {entry['name']} -> {rel_dst} [{src_id}]")
    except (OSError, ValueError, KeyError) as e:
        logger.warning(f"  manifest 创建失败: {entry['name']}: {e}")

    return True


def run_phase1(logger: logging.Logger) -> dict:
    """执行 Phase 1 数据摄入

    Args:
        logger: 日志记录器

    Returns:
        统计信息字典
    """
    logger.info("=" * 60)
    logger.info("Phase 1: 数据摄入开始")
    logger.info("=" * 60)

    progress = load_progress()

    # 扫描所有源
    all_files: list[dict] = []

    # 扫描主源目录（如果配置了）
    if SOURCE_PATH:
        logger.info(f"扫描源目录: {SOURCE_PATH}")
        files = scan_source_dir(SOURCE_PATH, logger)
        logger.info(f"  发现 {len(files)} 个文件")
        all_files.extend(files)
    else:
        logger.info("未配置源目录 (SOURCE_PATH)，跳过扫描")

    # 扫描 Obsidian vaults（如果配置了）
    if OBSIDIAN_PATHS:
        for vault in OBSIDIAN_PATHS:
            logger.info(f"扫描 Obsidian vault: {vault}")
            files = scan_obsidian_vault(vault, logger)
            logger.info(f"  发现 {len(files)} 个 markdown 文件")
            all_files.extend(files)
    else:
        logger.info("未配置 Obsidian vault (OBSIDIAN_PATHS)，跳过扫描")

    # 去重（基于文件名）
    seen_names = {v["name"] for v in progress["phase1"]["ingested_files"].values()}
    new_files = []
    for f in all_files:
        if f["name"] not in seen_names:
            new_files.append(f)

    logger.info(f"已存在 {len(seen_names)} 个文件, 新发现 {len(new_files)} 个文件")

    # 按类别统计
    from collections import Counter

    cat_counts = Counter(f["category"] for f in new_files)
    for cat, count in cat_counts.most_common():
        logger.info(f"  {cat}: {count} 个文件")

    # 摄入文件
    success = 0
    failed = 0
    for i, entry in enumerate(new_files):
        logger.info(f"[{i + 1}/{len(new_files)}] 处理: {entry['name']}")
        if ingest_file(entry, progress, logger):
            success += 1
        else:
            failed += 1

        # 每100个文件保存一次进度
        if (i + 1) % 100 == 0:
            save_progress(progress)

    # 最终保存
    progress["phase1"]["stats"]["total"] = len(progress["phase1"]["ingested_files"])
    save_progress(progress)

    # 输出统计
    stats = progress["phase1"]["stats"]
    logger.info("=" * 60)
    logger.info("Phase 1 完成!")
    logger.info(f"  总计: {stats['total']} 文件")
    logger.info(f"  本次新增: {stats['linked']} 文件")
    logger.info(f"  跳过(重复): {stats['skipped']} 文件")
    logger.info(f"  失败: {stats['failed']} 文件")
    logger.info("=" * 60)

    append_log(
        KB_PATH,
        "ingest",
        f"Phase 1 完成: 新增 {stats['linked']} 文件, 跳过 {stats['skipped']} 文件, 失败 {stats['failed']} 文件, 总计 {stats['total']} 文件",
    )

    return stats


if __name__ == "__main__":
    logger = setup_logging()
    try:
        run_phase1(logger)
    except KeyboardInterrupt:
        logger.info("用户中断执行")
        sys.exit(130)
    except OSError as e:
        logger.exception(f"Phase 1 failed (系统错误): {e}")
        sys.exit(1)
    except RuntimeError as e:
        logger.exception(f"Phase 1 failed (runtime error): {e}")
        sys.exit(1)
