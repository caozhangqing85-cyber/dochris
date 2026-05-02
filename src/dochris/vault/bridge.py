#!/usr/bin/env python3
"""
Vault Bridge — Obsidian 双向联动

功能：
  1. seed   — 从 Obsidian 主库拉取相关笔记到 raw/inbox/
  2. promote — 将认可的产物推送到 Obsidian 主库
  3. list   — 列出关联的 Obsidian 笔记

用法:
  python scripts/vault_bridge.py <workspace> seed "<topic>"
  python scripts/vault_bridge.py <workspace> promote <src-id>
  python scripts/vault_bridge.py <workspace> list <src-id>
"""

import hashlib
import logging
import re
import shutil
import sys
from pathlib import Path

# 确保 scripts 包可导入
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dochris.log import append_log
from dochris.manifest import (
    append_to_index,
    create_manifest,
    get_all_manifests,
    get_manifest,
    get_next_src_id,
)
from dochris.settings import get_settings as _get_settings

logger = logging.getLogger(__name__)

# ============================================================
# 常量（从配置获取）
# ============================================================

# OBSIDIAN_VAULT 从 settings 获取，可能为 None


def _get_obsidian_vault() -> Path | None:
    """获取 Obsidian 主库路径"""
    _s = _get_settings()
    return _s.obsidian_vaults[0] if _s.obsidian_vaults else None


# ============================================================
# 引用清洗
# ============================================================


def clean_internal_references(content: str) -> str:
    """清洗内部引用格式，适配 Obsidian 格式

    - 保留 `[[concept-name]]` 格式（Obsidian wikilink）
    - 转换 `(SRC-NNNN)` 为 `📚 来源: SRC-NNNN`
    - 移除内部 markdown 元数据（`---created: ...---`）
    """
    # 转换 SRC 引用为 Obsidian 友好格式
    content = re.sub(
        r"\(SRC-(\d{4})\)",
        r"📚 来源: SRC-\1",
        content,
    )

    # 移除内部 markdown 元数据块
    content = re.sub(
        r"---\n(?:created|status|quality|promoted|hash|path)[^:]*:[^\n]*\n---",
        "",
        content,
        flags=re.MULTILINE,
    )

    # 移除编译时间元数据行
    content = re.sub(
        r"^> 编译时间：.*$",
        "",
        content,
        flags=re.MULTILINE,
    )

    # 移除多余空行（连续 3+ 个空行变为 2 个）
    content = re.sub(r"\n{3,}", "\n\n", content)

    return content.strip()


def _compute_hash(content: str) -> str:
    """计算内容 SHA-256 哈希"""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


# ============================================================
# 搜索 Obsidian 笔记
# ============================================================


def _search_obsidian_notes(topic: str) -> list[dict]:
    """在 Obsidian 主库中搜索与 topic 相关的笔记

    搜索策略：
    1. 文件名包含关键词
    2. 文件内容包含关键词
    3. tags 包含关键词（frontmatter）

    Returns:
        [{"path": Path, "rel_path": str, "title": str, "match_type": str}, ...]
    """
    obsidian_vault = _get_obsidian_vault()
    if obsidian_vault is None or not obsidian_vault.exists():
        return []

    keywords = [kw.strip() for kw in topic.split() if len(kw.strip()) >= 2]
    if not keywords:
        keywords = [topic.strip()]

    results = []
    seen = set()

    for md_file in obsidian_vault.rglob("*.md"):
        # 跳过隐藏目录和配置文件
        if any(part.startswith(".") for part in md_file.parts):
            continue

        rel = md_file.relative_to(obsidian_vault)
        name_no_ext = md_file.stem

        # 策略1：文件名匹配
        for kw in keywords:
            if kw.lower() in name_no_ext.lower() and str(rel) not in seen:
                seen.add(str(rel))
                results.append(
                    {
                        "path": md_file,
                        "rel_path": str(rel),
                        "title": name_no_ext,
                        "match_type": "filename",
                    }
                )
                break

        # 策略2：内容匹配
        if str(rel) not in seen:
            try:
                content = md_file.read_text(encoding="utf-8", errors="replace")
                # 只检查前 2000 字符（标题区域）
                header = content[:2000]
                for kw in keywords:
                    if kw.lower() in header.lower():
                        seen.add(str(rel))
                        results.append(
                            {
                                "path": md_file,
                                "rel_path": str(rel),
                                "title": name_no_ext,
                                "match_type": "content",
                            }
                        )
                        break
            except OSError:
                continue

    # 去重并按匹配类型排序（filename 优先）
    filename_matches = [r for r in results if r["match_type"] == "filename"]
    content_matches = [r for r in results if r["match_type"] == "content"]
    return filename_matches + content_matches


# ============================================================
# seed_from_obsidian
# ============================================================


def seed_from_obsidian(workspace_path: Path, topic: str) -> list[dict]:
    """从 Obsidian 主库拉取相关笔记到 raw/inbox/

    流程：
    1. 搜索 Obsidian 主库中匹配 topic 的笔记
    2. 复制到 raw/inbox/
    3. 创建 manifest（status: ingested）
    4. 追加日志

    Args:
        workspace_path: 工作区路径
        topic: 搜索关键词

    Returns:
        操作结果列表
    """
    workspace_path = Path(workspace_path)
    inbox_dir = workspace_path / "raw" / "inbox"
    inbox_dir.mkdir(parents=True, exist_ok=True)

    notes = _search_obsidian_notes(topic)
    if not notes:
        logger.info(f"未找到与 '{topic}' 相关的 Obsidian 笔记")
        return []

    logger.info(f"找到 {len(notes)} 个相关笔记:")
    for n in notes:
        logger.info(f"  [{n['match_type']}] {n['rel_path']}")

    seeded = []
    for note in notes:
        src_path = note["path"]
        title = note["title"]

        # 读取内容计算哈希
        try:
            content = src_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue

        content_hash = _compute_hash(content)
        size_bytes = len(content.encode("utf-8"))

        # 检查是否已经存在（通过内容哈希）
        existing = get_all_manifests(workspace_path)
        already_exists = any(m.get("content_hash") == content_hash for m in existing)
        if already_exists:
            logger.info(f"  跳过（已存在）: {title}")
            continue

        # 复制到 inbox
        dst = inbox_dir / src_path.name
        counter = 1
        while dst.exists():
            stem = src_path.stem
            dst = inbox_dir / f"{stem}_{counter}.md"
            counter += 1

        shutil.copy2(src_path, dst)
        file_path = str(dst.relative_to(workspace_path))

        # 创建 manifest
        src_id = get_next_src_id(workspace_path)
        manifest = create_manifest(
            workspace_path=workspace_path,
            src_id=src_id,
            title=title,
            file_type="article",
            source_path=src_path,
            file_path=file_path,
            content_hash=content_hash,
            size_bytes=size_bytes,
            tags=["obsidian", "seed", topic],
        )
        append_to_index(workspace_path, manifest)

        seeded.append(
            {
                "src_id": src_id,
                "title": title,
                "file_path": file_path,
            }
        )

        logger.info(f"  入库: {src_id} → {title}")
    if seeded:
        append_log(
            workspace_path,
            "SEED_FROM_OBSIDIAN",
            f"topic={topic} | 导入={len(seeded)} 个笔记",
        )

    return seeded


# ============================================================
# promote_to_obsidian
# ============================================================


def promote_to_obsidian(workspace_path: Path, src_id: str) -> bool:
    """将认可的产物推送到 Obsidian 主库

    前置条件：manifest status == "promoted"
    流程：
    1. 验证 manifest 状态
    2. 读取 curated/promoted/ 中的内容
    3. 清洗内部引用
    4. 写入 Obsidian 主库
    5. 更新 manifest promoted_to 字段

    Args:
        workspace_path: 工作区路径
        src_id: 来源 ID

    Returns:
        是否成功
    """
    workspace_path = Path(workspace_path)
    manifest = get_manifest(workspace_path, src_id)

    if manifest is None:
        logger.error(f"未找到 manifest {src_id}")
        return False

    if manifest["status"] not in ("promoted", "promoted_to_wiki"):
        logger.error(
            f"{src_id} 当前状态为 '{manifest['status']}'，需要 'promoted' 或 'promoted_to_wiki'"
        )
        return False

    title = manifest.get("title", "")
    if not title:
        logger.error(f"{src_id} 缺少 title 字段")
        return False

    # 查找源文件（优先 curated/promoted/，其次 wiki/summaries/）
    safe_title = re.sub(r'[<>:"/\\|?*]', "", title)[:80]

    source_file = None
    for candidate_dir in [
        workspace_path / "curated" / "promoted",
        workspace_path / "wiki" / "summaries",
    ]:
        if candidate_dir.exists():
            for candidate_name in [f"{safe_title}.md"]:
                f = candidate_dir / candidate_name
                if f.exists():
                    source_file = f
                    break
            if source_file:
                break

    if source_file is None:
        logger.error(f"未找到 {src_id} 的产物文件")
        return False

    # 读取并清洗内容
    try:
        content = source_file.read_text(encoding="utf-8")
    except OSError as e:
        logger.error(f"读取文件失败: {e}")
        return False

    content = clean_internal_references(content)

    # 写入 Obsidian 主库
    obsidian_vault = _get_obsidian_vault()
    if obsidian_vault is None or not obsidian_vault.exists():
        logger.error(f"Obsidian 主库不存在或未配置: {obsidian_vault}")
        return False

    obsidian_target = obsidian_vault / "06-知识库" / source_file.name
    obsidian_target.parent.mkdir(parents=True, exist_ok=True)

    # 处理重名
    counter = 1
    while obsidian_target.exists():
        stem = source_file.stem
        obsidian_target = obsidian_vault / "06-知识库" / f"{stem}_{counter}.md"
        counter += 1

    obsidian_target.write_text(content, encoding="utf-8")

    # 更新 manifest
    from dochris.manifest import update_manifest_status

    update_manifest_status(
        workspace_path,
        src_id,
        status="promoted",
        promoted_to=f"obsidian:{obsidian_target.relative_to(obsidian_vault)}",
    )

    # 追加日志
    append_log(
        workspace_path,
        "PROMOTE_TO_OBSIDIAN",
        f"{src_id} | {title} → {obsidian_target.relative_to(obsidian_vault)}",
    )

    logger.info(f"推送成功：{src_id} → Obsidian")
    logger.info(f"  目标: {obsidian_target.relative_to(obsidian_vault)}")
    return True


# ============================================================
# list associated notes
# ============================================================


def list_associated_notes(workspace_path: Path, src_id: str) -> list[dict]:
    """列出与指定来源关联的 Obsidian 笔记

    通过标题关键词在 Obsidian 主库中搜索相关笔记。

    Args:
        workspace_path: 工作区路径
        src_id: 来源 ID

    Returns:
        关联笔记列表
    """
    workspace_path = Path(workspace_path)
    manifest = get_manifest(workspace_path, src_id)

    if manifest is None:
        logger.warning(f"未找到 manifest: {src_id}")
        return []

    title = manifest.get("title", "")
    if not title:
        logger.warning(f"{src_id} 缺少标题，无法搜索")
        return []

    # 用标题的关键词搜索
    keywords = re.sub(r'[<>:"/\\|?*]', " ", title).split()
    search_term = " ".join(k for k in keywords if len(k) >= 2)[:50]

    notes = _search_obsidian_notes(search_term)
    if not notes:
        logger.info(f"未找到与 '{title}' 关联的 Obsidian 笔记")
        return []

    logger.info(f"关联笔记（{len(notes)} 个）:")
    for n in notes:
        logger.info(f"  [{n['match_type']}] {n['rel_path']}")

    return notes


# ============================================================
# CLI
# ============================================================


def main() -> None:
    if len(sys.argv) < 4:
        print(__doc__)
        print("用法:")
        print(f'  python {sys.argv[0]} <workspace> seed "<topic>"')
        print(f"  python {sys.argv[0]} <workspace> promote <src-id>")
        print(f"  python {sys.argv[0]} <workspace> list <src-id>")
        sys.exit(1)

    workspace = Path(sys.argv[1])
    action = sys.argv[2].lower()
    arg = sys.argv[3]

    if action == "seed":
        results = seed_from_obsidian(workspace, arg)
        if results:
            print(f"\n共导入 {len(results)} 个笔记")
        sys.exit(0 if results else 1)

    elif action == "promote":
        ok = promote_to_obsidian(workspace, arg)
        sys.exit(0 if ok else 1)

    elif action == "list":
        notes = list_associated_notes(workspace, arg)
        sys.exit(0 if notes else 1)

    else:
        print(f"未知操作: {action}，支持: seed / promote / list")
        sys.exit(1)


if __name__ == "__main__":
    main()
