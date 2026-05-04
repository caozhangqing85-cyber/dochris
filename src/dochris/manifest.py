#!/usr/bin/env python3
"""
Manifest 管理系统
管理 source manifest 的创建、读取、更新和索引操作。

Manifest 格式：
{
  "id": "SRC-NNNN",
  "title": "来源标题",
  "type": "pdf|audio|video|ebook|article|other",
  "source_path": "/path/to/sources/filename.pdf",
  "file_path": "raw/pdfs/filename.pdf",
  "content_hash": "SHA-256",
  "date_ingested": "YYYY-MM-DD",
  "date_published": "YYYY-MM-DD 或 null",
  "size_bytes": 12345,
  "summary": null,
  "compiled_summary": null,
  "status": "ingested|compiled|failed|promoted",
  "quality_score": 0,
  "error_message": null,
  "promoted_to": null,
  "tags": []
}
"""

import csv
import json
import logging
from datetime import datetime
from pathlib import Path

from dochris.log_utils import append_log_to_file

logger = logging.getLogger(__name__)

# 保留向后兼容的别名
append_log = append_log_to_file


def get_default_workspace() -> Path:
    """获取默认工作区路径"""
    return Path.home() / ".openclaw/knowledge-base"


def _ensure_dirs(workspace_path: Path) -> None:
    """确保 manifests 目录存在"""
    (workspace_path / "manifests" / "sources").mkdir(parents=True, exist_ok=True)


def get_next_src_id(workspace_path: Path) -> str:
    """获取下一个 SRC-ID

    扫描 manifests/sources/ 中最大的 SRC-NNNN 编号，返回 SRC-NNNN+1。
    如果没有任何 manifest，返回 SRC-0001。
    """
    sources_dir = workspace_path / "manifests" / "sources"
    if not sources_dir.exists():
        return "SRC-0001"

    max_num = 0
    for f in sources_dir.glob("SRC-*.json"):
        try:
            num = int(f.stem.split("-")[1])
            if num > max_num:
                max_num = num
        except (ValueError, IndexError):
            continue

    return f"SRC-{max_num + 1:04d}"


def create_manifest(
    workspace_path: Path,
    src_id: str,
    title: str,
    file_type: str,
    source_path: Path,
    file_path: str,
    content_hash: str,
    size_bytes: int = 0,
    date_published: str | None = None,
    tags: list[str] | None = None,
) -> dict:
    """创建新的 source manifest

    Args:
        workspace_path: 工作区路径
        src_id: 来源 ID（如 SRC-0001）
        title: 来源标题
        file_type: 文件类型（pdf, audio, video, ebook, article, other）
        source_path: 原始文件绝对路径
        file_path: 相对于工作区的文件路径（如 raw/pdfs/filename.pdf）
        content_hash: 文件 SHA-256 哈希
        size_bytes: 文件大小
        date_published: 发布日期（可选）
        tags: 标签列表（可选）

    Returns:
        创建的 manifest 字典
    """
    _ensure_dirs(workspace_path)

    manifest = {
        "id": src_id,
        "title": title,
        "type": file_type,
        "source_path": str(source_path),
        "file_path": file_path,
        "content_hash": content_hash,
        "date_ingested": datetime.now().strftime("%Y-%m-%d"),
        "date_published": date_published,
        "size_bytes": size_bytes,
        "summary": None,
        "compiled_summary": None,
        "status": "ingested",
        "quality_score": 0,
        "error_message": None,
        "promoted_to": None,
        "tags": tags or [],
    }

    # 写入 manifest 文件
    manifest_path = workspace_path / "manifests" / "sources" / f"{src_id}.json"
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)

    # 同步到索引
    append_to_index(workspace_path, manifest)

    return manifest


def get_manifest(workspace_path: Path, src_id: str) -> dict | None:
    """读取 manifest

    Args:
        workspace_path: 工作区路径
        src_id: 来源 ID

    Returns:
        manifest 字典，不存在或读取失败则返回 None

    Raises:
        JSONDecodeError: 当 JSON 解析失败时抛出（不返回损坏数据）
    """
    manifest_path = workspace_path / "manifests" / "sources" / f"{src_id}.json"
    if not manifest_path.exists():
        return None

    # 首先尝试严格模式读取，捕获编码错误
    try:
        with open(manifest_path, encoding="utf-8") as f:
            data = json.load(f)
    except UnicodeDecodeError as e:
        # 记录详细的编码错误信息
        logger.warning(
            f"编码错误 in {manifest_path}: {e.__class__.__name__}, "
            f"使用 replacement characters 读取。"
        )
        try:
            with open(manifest_path, encoding="utf-8", errors="replace") as f:
                data = json.load(f)
        except json.JSONDecodeError as json_e:
            # JSON 解析也失败时抛出异常，不返回损坏数据
            logger.error(f"JSON 解析失败（编码错误后）in {manifest_path}: {json_e}")
            raise

    # 验证返回的 JSON 数据完整性
    if not isinstance(data, dict):
        logger.error(f"manifest 数据格式错误（非字典类型）: {manifest_path}")
        return None
    if "id" not in data:
        logger.warning(f"manifest 缺少 id 字段: {manifest_path}")

    return data


def update_manifest_status(
    workspace_path: Path,
    src_id: str,
    status: str,
    quality_score: int = 0,
    error_message: str | None = None,
    summary: dict | None = None,
    compiled_summary: dict | None = None,
    promoted_to: str | None = None,
) -> dict | None:
    """更新 manifest 状态

    Args:
        workspace_path: 工作区路径
        src_id: 来源 ID
        status: 新状态（ingested, compiled, failed, promoted）
        quality_score: 质量评分
        error_message: 错误消息（失败时使用）
        summary: 编译后的摘要数据
        compiled_summary: 编译后的概念数据
        promoted_to: 晋升目标

    Returns:
        更新后的 manifest 字典，不存在则返回 None
    """
    manifest = get_manifest(workspace_path, src_id)
    if manifest is None:
        return None

    manifest["status"] = status

    if quality_score > 0:
        manifest["quality_score"] = quality_score

    if error_message is not None:
        manifest["error_message"] = error_message

    if summary is not None:
        manifest["summary"] = summary

    if compiled_summary is not None:
        manifest["compiled_summary"] = compiled_summary

    if promoted_to is not None:
        manifest["promoted_to"] = promoted_to

    # 设置时间戳
    if status == "compiled":
        manifest["date_compiled"] = datetime.now().isoformat()
    elif status == "failed":
        manifest["date_failed"] = datetime.now().isoformat()

    # 写回文件
    manifest_path = workspace_path / "manifests" / "sources" / f"{src_id}.json"
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)

    # 同步更新 source_index.csv
    update_index_entry(workspace_path, src_id, status, quality_score)

    return manifest


def append_to_index(workspace_path: Path, manifest: dict) -> None:
    """追加 manifest 到 source_index.csv

    Args:
        workspace_path: 工作区路径
        manifest: manifest 字典
    """
    _ensure_dirs(workspace_path)
    index_path = workspace_path / "manifests" / "source_index.csv"

    # 如果文件不存在，写入表头
    if not index_path.exists():
        with open(index_path, "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(
                [
                    "id",
                    "title",
                    "type",
                    "date_ingested",
                    "file_path",
                    "content_hash",
                    "status",
                    "quality_score",
                ]
            )

    # 追加一行
    with open(index_path, "a", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                manifest["id"],
                manifest["title"],
                manifest["type"],
                manifest["date_ingested"],
                manifest["file_path"],
                manifest["content_hash"],
                manifest["status"],
                manifest["quality_score"],
            ]
        )


def update_index_entry(
    workspace_path: Path,
    src_id: str,
    status: str,
    quality_score: int = 0,
) -> None:
    """更新 source_index.csv 中某条记录的状态

    使用临时文件 + os.replace() 实现原子操作。

    Args:
        workspace_path: 工作区路径
        src_id: 来源 ID
        status: 新状态
        quality_score: 质量评分
    """
    import os

    index_path = workspace_path / "manifests" / "source_index.csv"
    if not index_path.exists():
        return

    rows = []
    with open(index_path, encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames or [
            "id",
            "title",
            "type",
            "date_ingested",
            "file_path",
            "content_hash",
            "status",
            "quality_score",
        ]
        for row in reader:
            # 统一使用 'id' 字段名匹配
            if row.get("id") == src_id:
                row["status"] = status
                if quality_score > 0:
                    row["quality_score"] = str(quality_score)
            rows.append(row)

    # 使用临时文件 + 原子替换
    tmp_path = index_path.with_suffix(".tmp")
    with open(tmp_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    os.replace(tmp_path, index_path)


def get_all_manifests(workspace_path: Path, status: str | None = None) -> list[dict]:
    """获取所有 manifest（可按状态过滤）

    Args:
        workspace_path: 工作区路径
        status: 过滤状态（可选，如 "ingested", "compiled"）

    Returns:
        manifest 列表
    """
    sources_dir = workspace_path / "manifests" / "sources"
    if not sources_dir.exists():
        return []

    manifests = []
    for f in sorted(sources_dir.glob("SRC-*.json")):
        try:
            with open(f, encoding="utf-8") as fh:
                m = json.load(fh)
            if status is None or m.get("status") == status:
                manifests.append(m)
        except (json.JSONDecodeError, OSError):
            continue

    return manifests


def rebuild_index(workspace_path: Path) -> None:
    """从所有 manifest 文件重建 source_index.csv"""
    _ensure_dirs(workspace_path)
    index_path = workspace_path / "manifests" / "source_index.csv"

    manifests = get_all_manifests(workspace_path)

    with open(index_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "id",
                "title",
                "type",
                "date_ingested",
                "file_path",
                "content_hash",
                "status",
                "quality_score",
            ]
        )
        for m in manifests:
            writer.writerow(
                [
                    m["id"],
                    m["title"],
                    m["type"],
                    m["date_ingested"],
                    m["file_path"],
                    m["content_hash"],
                    m["status"],
                    m["quality_score"],
                ]
            )
