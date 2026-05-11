#!/usr/bin/env python3
"""
kb export 命令：导出知识库内容为 ZIP 归档
"""

import csv
import io
import logging
import zipfile
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# 支持的导出类型
EXPORT_TYPES = {"summaries", "concepts", "all"}


def cmd_export(args: Any) -> int:
    """导出知识库内容

    Args:
        args: 命令行参数
            - output: 输出 ZIP 文件路径
            - type: 导出类型 (summaries/concepts/all)

    Returns:
        退出码（0 表示成功，非 0 表示错误）
    """
    from dochris.settings import get_settings

    settings = get_settings()
    workspace = settings.workspace

    export_type = getattr(args, "type", "all") or "all"
    output_path = Path(getattr(args, "output", "knowledge-export.zip"))

    if export_type not in EXPORT_TYPES:
        print(f"❌ 不支持的导出类型: {export_type}，可选: {', '.join(sorted(EXPORT_TYPES))}")
        return 1

    # 确定要打包的目录
    dirs_to_export: list[tuple[str, Path]] = []
    if export_type in ("summaries", "all"):
        dirs_to_export.append(("wiki/summaries", workspace / "wiki" / "summaries"))
        dirs_to_export.append(("outputs/summaries", workspace / "outputs" / "summaries"))
    if export_type in ("concepts", "all"):
        dirs_to_export.append(("wiki/concepts", workspace / "wiki" / "concepts"))
        dirs_to_export.append(("outputs/concepts", workspace / "outputs" / "concepts"))

    # 收集所有要打包的文件
    file_entries: list[tuple[str, Path]] = []
    for label, dir_path in dirs_to_export:
        if not dir_path.exists():
            logger.warning(f"目录不存在，跳过: {dir_path}")
            continue
        for f in sorted(dir_path.rglob("*")):
            if f.is_file():
                arcname = f"{label}/{f.relative_to(dir_path)}"
                file_entries.append((arcname, f))

    if not file_entries:
        print("⚠️  没有找到可导出的文件")
        return 0

    # 生成 manifest
    manifest_rows = _build_manifest(file_entries, workspace)

    print(f"📦 导出类型: {export_type}")
    print(f"   文件数量: {len(file_entries)}")

    # 写入 ZIP
    try:
        with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
            # 写入文件
            for arcname, file_path in file_entries:
                zf.write(file_path, arcname)

            # 写入 manifest.csv
            manifest_bytes = _manifest_to_csv(manifest_rows)
            zf.writestr("manifest.csv", manifest_bytes)

        size_kb = output_path.stat().st_size / 1024
        print(f"✅ 导出完成: {output_path} ({size_kb:.1f} KB)")
        return 0

    except OSError as e:
        print(f"❌ 导出失败: {e}")
        return 1


def _build_manifest(file_entries: list[tuple[str, Path]], workspace: Path) -> list[dict[str, str]]:
    """构建 manifest 数据

    尝试从 manifests/ 目录读取对应文件的状态和质量分。
    """
    rows = []
    manifests = _load_manifest_lookup(workspace)

    for arcname, file_path in file_entries:
        status = "unknown"
        quality = ""
        data = _match_manifest(file_path, manifests)
        if data:
            status = data.get("status", "unknown")
            quality = str(data.get("quality_score", ""))

        rows.append(
            {
                "path": arcname,
                "filename": file_path.name,
                "status": status,
                "quality_score": quality,
            }
        )

    return rows


def _load_manifest_lookup(workspace: Path) -> list[dict]:
    """读取所有 manifest，供导出时匹配产物状态"""
    manifests_dir = workspace / "manifests" / "sources"
    if not manifests_dir.exists():
        return []

    manifests = []
    for mf in manifests_dir.glob("*.json"):
        data = _read_json_simple(mf)
        if data:
            manifests.append(data)
    return manifests


def _match_manifest(file_path: Path, manifests: list[dict]) -> dict | None:
    """按 src_id、file_path 和 title 兼容匹配导出文件对应的 manifest"""
    stem = file_path.stem
    parts = set(file_path.parts)

    for data in manifests:
        src_id = data.get("id", "")
        if src_id and (stem == src_id or src_id in parts):
            return data

        manifest_file = Path(str(data.get("file_path", ""))).name
        if manifest_file and manifest_file == file_path.name:
            return data

        title = str(data.get("title", ""))
        if title and Path(title).stem == stem:
            return data

    return None


def _read_json_simple(path: Path) -> dict | None:
    """简单 JSON 读取，不依赖额外库"""
    import json

    try:
        return dict(json.loads(path.read_text(encoding="utf-8")))  # type: ignore[arg-type]
    except (OSError, json.JSONDecodeError):
        return None


def _manifest_to_csv(rows: list[dict[str, str]]) -> bytes:
    """将 manifest 数据转为 CSV 字节"""
    buf = io.StringIO()
    if rows:
        writer = csv.DictWriter(buf, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    return buf.getvalue().encode("utf-8")
