#!/usr/bin/env python3
"""
Promote 脚本 — 将编译产物从 outputs/ 晋升到 wiki/ 或 curated/

两级晋升流程：
  1. outputs/ → wiki/      (status: compiled → promoted_to_wiki)
  2. wiki/   → curated/   (status: promoted_to_wiki → promoted)

用法:
  python scripts/promote_artifact.py <workspace> wiki <src-id>
  python scripts/promote_artifact.py <workspace> curated <src-id>
  python scripts/promote_artifact.py <workspace> status <src-id>
"""

import os
import shutil
import sys
import tempfile
from pathlib import Path

# 确保 scripts 包可导入
from dochris.core.utils import sanitize_filename
from dochris.log import append_log
from dochris.manifest import get_manifest, update_manifest_status

# 文件复制重名冲突最大重试次数
MAX_COPY_RETRIES = 999


def _ensure_dirs(*paths: Path) -> None:
    """确保目录存在"""
    for p in paths:
        p.mkdir(parents=True, exist_ok=True)


def _copy_file(src: Path, dst_dir: Path) -> Path:
    """原子复制文件到目标目录，处理重名冲突

    使用临时文件 + rename 实现原子操作，避免中断导致文件损坏。

    Args:
        src: 源文件路径
        dst_dir: 目标目录

    Returns:
        复制后的文件路径

    Raises:
        ValueError: 当重名冲突超过 MAX_COPY_RETRIES 时
    """
    dst = dst_dir / src.name
    counter = 1
    while dst.exists():
        if counter > MAX_COPY_RETRIES:
            raise ValueError(f"文件复制重名冲突超过上限 ({MAX_COPY_RETRIES}): {src.name}")
        stem = src.stem
        suffix = src.suffix
        dst = dst_dir / f"{stem}_{counter}{suffix}"
        counter += 1
    # 原子操作：先写临时文件，再 rename
    fd, tmp_path = tempfile.mkstemp(suffix=src.suffix, dir=dst_dir)
    try:
        os.close(fd)
        shutil.copy2(src, tmp_path)
        os.rename(tmp_path, dst)
    except Exception:
        # 清理临时文件
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise
    return dst


def _find_output_file(base_dir: Path, src_id: str, ext: str) -> Path | None:
    """在目录中查找与 src_id 相关的输出文件

    查找策略：
    1. 直接匹配 SRC-NNNN.ext
    2. 遍历目录查找文件内容中包含 src_id 引用的文件
    """
    # 策略1：直接文件名匹配
    direct = base_dir / f"{src_id}{ext}"
    if direct.exists():
        return direct

    return None


def _find_concept_file(base_dir: Path, src_id: str, concept_name: str) -> Path | None:
    """查找指定 src_id 下的概念文件，兼容新旧输出结构"""
    compiler_safe = concept_name.strip().replace("/", "_").replace("\\", "_")
    sanitized = sanitize_filename(concept_name, max_length=50)
    candidate_names = [name for name in [compiler_safe, sanitized] if name]
    candidates = []
    for name in candidate_names:
        candidates.append(base_dir / src_id / f"{name}.md")
        candidates.append(base_dir / f"{name}.md")
    for path in candidates:
        if path.exists():
            return path

    # 模糊匹配：在 base_dir 和 src 子目录中搜索包含 concept_name 的文件
    src_dir = base_dir / src_id
    for search_dir in [src_dir, base_dir]:
        if not search_dir.exists():
            continue
        for name in candidate_names:
            # 尝试 glob 模式匹配（如 01_AI.md）
            for path in sorted(search_dir.glob(f"*_{name}.md")):
                if path.is_file():
                    return path
            # 尝试在所有 .md 文件中搜索标题包含概念名的
            for path in sorted(search_dir.glob("*.md")):
                if path.is_file():
                    try:
                        first_line = path.read_text(encoding="utf-8", errors="ignore").split("\n", 1)[0]
                        if concept_name.strip() in first_line:
                            return path
                    except OSError:
                        continue

    return None


def promote_to_wiki(workspace_path: Path, src_id: str) -> bool:
    """将来源从 outputs/ 晋升到 wiki/

    前置条件：manifest status == "compiled"
    操作：复制 outputs/summaries/ 和 outputs/concepts/ 到 wiki/
    """
    workspace_path = Path(workspace_path)
    manifest = get_manifest(workspace_path, src_id)

    if manifest is None:
        print(f"错误：未找到 manifest {src_id}")
        return False

    if manifest["status"] != "compiled":
        print(f"错误：{src_id} 当前状态为 '{manifest['status']}'，需要 'compiled' 才能晋升")
        return False

    title = manifest.get("title", "")
    if not title:
        print(f"错误：{src_id} 缺少 title 字段")
        return False

    wiki_summaries = workspace_path / "wiki" / "summaries"
    wiki_concepts = workspace_path / "wiki" / "concepts"
    outputs_summaries = workspace_path / "outputs" / "summaries"
    outputs_concepts = workspace_path / "outputs" / "concepts"

    _ensure_dirs(wiki_summaries, wiki_concepts)

    promoted_files = []

    # 晋升摘要文件
    safe_title = sanitize_filename(title, max_length=80)
    summary_src = _find_output_file(outputs_summaries, src_id, ".md")
    if summary_src is None:
        summary_src = outputs_summaries / f"{safe_title}.md"

    if not summary_src.exists():
        # 尝试使用更宽松的匹配（允许更多特殊字符）
        import re

        pattern = re.sub(r'[<>:"/\\|?*]', "", title)[:80]
        summary_src = outputs_summaries / f"{pattern}.md"

    if summary_src.exists():
        dst = _copy_file(summary_src, wiki_summaries)
        promoted_files.append(f"  wiki/summaries/{dst.name}")
    else:
        print(f"警告：未找到摘要文件 outputs/summaries/{safe_title}.md")

    # 晋升相关概念文件
    compiled_summary = manifest.get("compiled_summary")
    if compiled_summary and isinstance(compiled_summary, dict):
        concepts = compiled_summary.get("concepts", [])
        if isinstance(concepts, list):
            for c in concepts:
                if isinstance(c, dict):
                    concept_name = c.get("name", "")
                elif isinstance(c, str):
                    concept_name = c
                else:
                    continue
                if not concept_name:
                    continue
                concept_src = _find_concept_file(outputs_concepts, src_id, concept_name)
                if concept_src is not None:
                    dst = _copy_file(concept_src, wiki_concepts)
                    promoted_files.append(f"  wiki/concepts/{dst.name}")

    if not promoted_files:
        print(f"错误：{src_id} 没有找到可晋升的输出文件")
        return False

    # 更新 manifest 状态
    update_manifest_status(
        workspace_path,
        src_id,
        status="promoted_to_wiki",
        promoted_to="wiki",
    )

    # 记录日志
    append_log(
        workspace_path,
        "PROMOTE_TO_WIKI",
        f"{src_id} | {title} | 文件数: {len(promoted_files)}",
    )

    print(f"晋升成功：{src_id} → wiki/")
    for f in promoted_files:
        print(f"  {f}")
    return True


def promote_to_curated(workspace_path: Path, src_id: str) -> bool:
    """将来源从 wiki/ 晋升到 curated/

    前置条件：manifest status == "promoted_to_wiki"
    操作：复制 wiki/ 中认可的文件到 curated/promoted/
    """
    workspace_path = Path(workspace_path)
    manifest = get_manifest(workspace_path, src_id)

    if manifest is None:
        print(f"错误：未找到 manifest {src_id}")
        return False

    if manifest["status"] != "promoted_to_wiki":
        print(f"错误：{src_id} 当前状态为 '{manifest['status']}'，需要 'promoted_to_wiki' 才能晋升")
        return False

    title = manifest.get("title", "")
    curated_dir = workspace_path / "curated" / "promoted"
    wiki_summaries = workspace_path / "wiki" / "summaries"
    wiki_concepts = workspace_path / "wiki" / "concepts"

    _ensure_dirs(curated_dir)

    promoted_files = []

    # 复制摘要
    safe_title = sanitize_filename(title, max_length=80)
    import re

    pattern = re.sub(r'[<>:"/\\|?*]', "", title)[:80]

    for candidate_name in [f"{safe_title}.md", f"{pattern}.md"]:
        wiki_summary = wiki_summaries / candidate_name
        if wiki_summary.exists():
            dst = _copy_file(wiki_summary, curated_dir)
            promoted_files.append(f"  curated/promoted/{dst.name}")
            break

    # 复制相关概念
    compiled_summary = manifest.get("compiled_summary")
    if compiled_summary and isinstance(compiled_summary, dict):
        concepts = compiled_summary.get("concepts", [])
        if isinstance(concepts, list):
            for c in concepts:
                if isinstance(c, dict):
                    concept_name = c.get("name", "")
                elif isinstance(c, str):
                    concept_name = c
                else:
                    continue
                if not concept_name:
                    continue
                safe_concept = re.sub(r'[<>:"/\\|?*]', "", concept_name).strip()[:50]
                concept_src = wiki_concepts / f"{safe_concept}.md"
                if concept_src.exists():
                    dst = _copy_file(concept_src, curated_dir)
                    promoted_files.append(f"  curated/promoted/{dst.name}")

    if not promoted_files:
        print(f"错误：{src_id} 在 wiki/ 中没有找到可晋升的文件")
        return False

    # 更新 manifest 状态
    update_manifest_status(
        workspace_path,
        src_id,
        status="promoted",
        promoted_to="curated",
    )

    # 记录日志
    append_log(
        workspace_path,
        "PROMOTE_TO_CURATED",
        f"{src_id} | {title} | 文件数: {len(promoted_files)}",
    )

    print(f"晋升成功：{src_id} → curated/")
    for f in promoted_files:
        print(f"  {f}")
    return True


def show_status(workspace_path: Path, src_id: str) -> None:
    """显示 manifest 状态"""
    workspace_path = Path(workspace_path)
    manifest = get_manifest(workspace_path, src_id)

    if manifest is None:
        print(f"未找到 manifest: {src_id}")
        return

    print(f"ID:     {manifest['id']}")
    print(f"标题:   {manifest['title']}")
    print(f"类型:   {manifest['type']}")
    print(f"状态:   {manifest['status']}")
    print(f"质量分: {manifest.get('quality_score', 0)}")
    print(f"晋升到: {manifest.get('promoted_to', '无')}")
    print(f"来源:   {manifest.get('source_path', '无')}")
    print(f"文件:   {manifest.get('file_path', '无')}")

    error = manifest.get("error_message")
    if error:
        print(f"错误:   {error}")


def main() -> None:
    if len(sys.argv) < 4:
        print(__doc__)
        print("用法:")
        print(f"  python {sys.argv[0]} <workspace> wiki <src-id>")
        print(f"  python {sys.argv[0]} <workspace> curated <src-id>")
        print(f"  python {sys.argv[0]} <workspace> status <src-id>")
        sys.exit(1)

    workspace = Path(sys.argv[1])
    action = sys.argv[2].lower()
    src_id = sys.argv[3]

    if action == "wiki":
        ok = promote_to_wiki(workspace, src_id)
        sys.exit(0 if ok else 1)
    elif action == "curated":
        ok = promote_to_curated(workspace, src_id)
        sys.exit(0 if ok else 1)
    elif action == "status":
        show_status(workspace, src_id)
    else:
        print(f"未知操作: {action}，支持: wiki / curated / status")
        sys.exit(1)


if __name__ == "__main__":
    main()
