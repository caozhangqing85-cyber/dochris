"""知识图谱构建器 — 从 manifests + wiki 构建知识图谱"""

from __future__ import annotations

import hashlib
import json
import logging
import re
from pathlib import Path

from dochris.graph.models import GraphEdge, GraphNode, KnowledgeGraph

logger = logging.getLogger(__name__)

# Obsidian [[wiki-link]] 提取正则
_WIKI_LINK_RE = re.compile(r"\[\[([^\]]+)\]\]")
_H1_RE = re.compile(r"^#\s+(.+?)\s*$", re.MULTILINE)
_SOURCE_SUFFIX_RE = re.compile(r"_SRC-(\d+)$")
_NUMBERED_SUFFIX_RE = re.compile(r"_(\d+)$")


def _normalize_concept_name(name: str) -> str:
    """规范化概念显示名，同时保留 Unicode 和语义标点。"""
    return re.sub(r"\s+", " ", name.strip())


def _canonical_concept_name(
    path: Path,
    content: str,
    content_hash: str,
    hashes_by_stem: dict[str, set[str]],
) -> str:
    """从 H1 或可验证的文件关系推导稳定概念名。"""
    heading = _H1_RE.search(content)
    if heading:
        return _normalize_concept_name(heading.group(1))

    source_base = _SOURCE_SUFFIX_RE.sub("", path.stem)
    if source_base != path.stem:
        return _normalize_concept_name(source_base)

    numbered = _NUMBERED_SUFFIX_RE.search(path.stem)
    if numbered:
        base_stem = path.stem[: numbered.start()]
        if content_hash in hashes_by_stem.get(base_stem, set()):
            return _normalize_concept_name(base_stem)

    return _normalize_concept_name(path.stem)


def _canonical_summary_path(paths: list[Path]) -> Path:
    """为内容相同的摘要别名选择稳定主文件，优先使用 source ID。"""
    for path in paths:
        if re.fullmatch(r"SRC-\d+", path.stem):
            return path

    stems = {path.stem for path in paths}
    for path in paths:
        numbered = _NUMBERED_SUFFIX_RE.search(path.stem)
        if numbered and path.stem[: numbered.start()] in stems:
            base_stem = path.stem[: numbered.start()]
            return next(candidate for candidate in paths if candidate.stem == base_stem)

    return paths[0]


def build_graph(workspace_path: Path | str) -> KnowledgeGraph:
    """从 manifests + wiki 构建知识图谱

    Args:
        workspace_path: 工作区路径

    Returns:
        构建好的知识图谱
    """
    workspace_path = Path(workspace_path)
    graph = KnowledgeGraph()

    manifests_dir = workspace_path / "manifests" / "sources"
    # 扫描 outputs/concepts（编译产物）和 wiki/concepts（已晋升），去重
    concepts_dirs = [
        workspace_path / "outputs" / "concepts",
        workspace_path / "wiki" / "concepts",
    ]
    summaries_dirs = [
        workspace_path / "outputs" / "summaries",
        workspace_path / "wiki" / "summaries",
    ]

    # 1. 从 manifest 创建 source 节点
    manifests_data: dict[str, dict] = {}
    if manifests_dir.exists():
        for mf in sorted(manifests_dir.glob("*.json")):
            try:
                data = json.loads(mf.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError) as e:
                logger.warning(f"读取 manifest 失败 {mf.name}: {e}")
                continue

            mid = data.get("id", mf.stem)
            title = data.get("title", mid)
            node = GraphNode(
                id=mid,
                label=title,
                node_type="source",
                metadata={
                    "type": data.get("type", "unknown"),
                    "status": data.get("status", "unknown"),
                    "quality_score": data.get("quality_score"),
                    "trust_level": data.get("trust_level"),
                    "tags": data.get("tags", []),
                },
            )
            graph.add_node(node)
            manifests_data[mid] = data

    # 2. 从 concepts 目录创建 canonical concept 节点。
    # 文件仍全部保留在 metadata，Graph 只合并有 H1/内容证据的同一概念。
    concept_files: list[Path] = []
    for concepts_dir in concepts_dirs:
        if not concepts_dir.exists():
            continue
        concept_files.extend(sorted(concepts_dir.glob("*.md")))

    concept_contents = {
        path: path.read_text(encoding="utf-8", errors="ignore") for path in concept_files
    }
    concept_hashes = {
        path: hashlib.sha256(content.encode("utf-8")).hexdigest()
        for path, content in concept_contents.items()
    }
    hashes_by_stem: dict[str, set[str]] = {}
    for path, content_hash in concept_hashes.items():
        hashes_by_stem.setdefault(path.stem, set()).add(content_hash)

    concept_aliases: dict[str, str] = {}
    concept_records: list[tuple[str, str]] = []
    for cf in concept_files:
        content = concept_contents[cf]
        content_hash = concept_hashes[cf]
        name = _canonical_concept_name(cf, content, content_hash, hashes_by_stem)
        concept_id = f"concept:{name}"
        source_match = _SOURCE_SUFFIX_RE.search(cf.stem)

        concept_node = graph.get_node(concept_id)
        if concept_node is None:
            concept_node = GraphNode(
                id=concept_id,
                label=name,
                node_type="concept",
                metadata={
                    "file": str(cf),
                    "files": [],
                    "aliases": [],
                    "variants": [],
                    "duplicate_files": [],
                    "source_ids": [],
                },
            )
            graph.add_node(concept_node)

        metadata = concept_node.metadata
        metadata["files"].append(str(cf))
        if cf.stem not in metadata["aliases"]:
            metadata["aliases"].append(cf.stem)

        variant_hashes = {variant["hash"] for variant in metadata["variants"]}
        if content_hash in variant_hashes:
            if str(cf) != metadata["file"]:
                metadata["duplicate_files"].append(str(cf))
        else:
            metadata["variants"].append({"file": str(cf), "hash": content_hash})

        if source_match:
            source_id = f"SRC-{source_match.group(1)}"
            if source_id not in metadata["source_ids"]:
                metadata["source_ids"].append(source_id)

        concept_aliases[cf.stem] = concept_id
        concept_aliases[name] = concept_id
        concept_records.append((concept_id, content))

    # 所有 alias 建立后再解析 wiki-links，避免排序导致的断边。
    concept_edge_keys: set[tuple[str, str]] = set()
    for concept_id, content in concept_records:
        for link in _WIKI_LINK_RE.findall(content):
            link_name = _normalize_concept_name(link)
            link_id = concept_aliases.get(link_name, f"concept:{link_name}")
            edge_key = (concept_id, link_id)
            if edge_key in concept_edge_keys:
                continue
            concept_edge_keys.add(edge_key)
            graph.add_edge(
                GraphEdge(
                    source=concept_id,
                    target=link_id,
                    relation="related_to",
                    weight=0.5,
                )
            )

    # 3. 从 outputs/summaries + wiki/summaries 创建 canonical summary 节点。
    # title symlink、promote 副本和原始 SRC 文件按内容 hash 合并，路径仍全部留痕。
    summary_files: list[Path] = []
    for summaries_dir in summaries_dirs:
        if summaries_dir.exists():
            summary_files.extend(sorted(summaries_dir.glob("*.md")))

    summary_contents = {
        path: path.read_text(encoding="utf-8", errors="ignore") for path in summary_files
    }
    summary_groups: dict[str, list[Path]] = {}
    for path, content in summary_contents.items():
        content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
        summary_groups.setdefault(content_hash, []).append(path)

    summary_aliases: dict[str, str] = {}
    summary_concepts: dict[str, list[str]] = {}  # summary_id -> [concept_ids]
    summary_tags: dict[str, list[str]] = {}  # summary_id -> [tags]
    summary_edge_keys: set[tuple[str, str]] = set()
    for content_hash, paths in summary_groups.items():
        primary_path = _canonical_summary_path(paths)
        name = primary_path.stem
        summary_id = f"summary:{name}"

        summary_node = graph.get_node(summary_id)
        if summary_node is None:
            summary_node = GraphNode(
                id=summary_id,
                label=name,
                node_type="summary",
                metadata={
                    "file": str(primary_path),
                    "files": [],
                    "aliases": [],
                    "variants": [],
                    "duplicate_files": [],
                },
            )
            graph.add_node(summary_node)

        metadata = summary_node.metadata
        for path in paths:
            metadata["files"].append(str(path))
            if path.stem not in metadata["aliases"]:
                metadata["aliases"].append(path.stem)
            summary_aliases[path.stem] = summary_id
            if path != primary_path:
                metadata["duplicate_files"].append(str(path))
        metadata["variants"].append({"file": str(primary_path), "hash": content_hash})

        # 相同内容只解析一次；不同内容但同 canonical id 时会作为 variant 补充边。
        concepts_in_summary = summary_concepts.setdefault(summary_id, [])
        content = summary_contents[primary_path]
        for match in _WIKI_LINK_RE.finditer(content):
            concept_name = _normalize_concept_name(match.group(1))
            concept_id = concept_aliases.get(concept_name, f"concept:{concept_name}")
            if concept_id not in concepts_in_summary:
                concepts_in_summary.append(concept_id)
            edge_key = (summary_id, concept_id)
            if edge_key not in summary_edge_keys:
                summary_edge_keys.add(edge_key)
                graph.add_edge(
                    GraphEdge(
                        source=summary_id,
                        target=concept_id,
                        relation="contains_concept",
                    )
                )
        summary_tags[summary_id] = []  # 从文件名推断

    # 4. 根据 manifest 的 status 创建 source → summary 边
    for mid, data in manifests_data.items():
        status = data.get("status", "")
        if status in ("compiled", "promoted_to_wiki", "promoted"):
            # 尝试匹配 summary
            title_slug = _title_to_slug(data.get("title", mid))
            summary_id = summary_aliases.get(title_slug) or summary_aliases.get(
                mid, f"summary:{title_slug}"
            )
            if summary_id in graph.nodes:
                edge = GraphEdge(
                    source=mid,
                    target=summary_id,
                    relation="compiled_to",
                )
                graph.add_edge(edge)

            # 从 manifest 的 compiled_summary.concepts 创建边
            compiled = data.get("compiled_summary") or {}
            concepts_list = compiled.get("concepts", [])
            for concept_entry in concepts_list:
                # 概念可能是 dict 或 string
                if isinstance(concept_entry, dict):
                    concept_name = str(concept_entry.get("name", ""))
                else:
                    concept_name = str(concept_entry) if concept_entry else ""
                if not concept_name:
                    continue
                concept_name = _normalize_concept_name(concept_name)
                concept_id = concept_aliases.get(concept_name, f"concept:{concept_name}")
                if concept_id in graph.nodes:
                    edge = GraphEdge(
                        source=mid,
                        target=concept_id,
                        relation="contains_concept",
                    )
                    graph.add_edge(edge)

    # 5. 根据 tags 共享创建 summary → summary 边
    # 以及 concept → concept 共现边
    concept_to_summaries: dict[str, list[str]] = {}
    for sid, concepts in summary_concepts.items():
        for cid in concepts:
            concept_to_summaries.setdefault(cid, []).append(sid)

    for _cid, sids in concept_to_summaries.items():
        if len(sids) > 1:
            for i in range(len(sids)):
                for j in range(i + 1, len(sids)):
                    edge = GraphEdge(
                        source=sids[i],
                        target=sids[j],
                        relation="related_to",
                        weight=0.3,
                    )
                    graph.add_edge(edge)

    # 6. 根据文件类型创建 source → source 边
    type_groups: dict[str, list[str]] = {}
    for mid, data in manifests_data.items():
        file_type = data.get("type", "unknown")
        type_groups.setdefault(file_type, []).append(mid)

    for _file_type, mids in type_groups.items():
        # 只连接同类型的前 50 个节点（避免图过大）
        for i in range(min(len(mids), 50)):
            for j in range(i + 1, min(len(mids), 50)):
                edge = GraphEdge(
                    source=mids[i],
                    target=mids[j],
                    relation="same_type",
                    weight=0.1,
                )
                graph.add_edge(edge)

    # 清理无效边（指向不存在节点的边）
    valid_node_ids = set(graph.nodes.keys())
    invalid_edges = [
        e for e in graph.edges if e.source not in valid_node_ids or e.target not in valid_node_ids
    ]
    if invalid_edges:
        logger.debug(f"清理 {len(invalid_edges)} 条无效边（指向不存在节点）")
    graph.edges = [
        e for e in graph.edges if e.source in valid_node_ids and e.target in valid_node_ids
    ]

    if not graph.nodes:
        logger.info("知识图谱构建完成: 空图谱（工作区无数据）")
    else:
        logger.info(f"知识图谱构建完成: {len(graph.nodes)} 节点, {len(graph.edges)} 边")
    return graph


def _title_to_slug(title: str) -> str:
    """将标题转换为文件名 slug

    去除文件系统不安全字符，保留 Unicode 字母数字和连字符。
    """
    slug = title.strip()
    # 移除文件系统不安全字符
    slug = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "", slug)
    # 空格替换为连字符
    slug = slug.replace(" ", "-")
    # 合并连续连字符
    slug = re.sub(r"-{2,}", "-", slug)
    return slug.strip("-") or title.strip()
