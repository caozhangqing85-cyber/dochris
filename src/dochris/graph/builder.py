"""知识图谱构建器 — 从 manifests + wiki 构建知识图谱"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path

from dochris.graph.models import GraphEdge, GraphNode, KnowledgeGraph

logger = logging.getLogger(__name__)

# Obsidian [[wiki-link]] 提取正则
_WIKI_LINK_RE = re.compile(r"\[\[([^\]]+)\]\]")


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
    concepts_dir = workspace_path / "wiki" / "concepts"
    summaries_dir = workspace_path / "wiki" / "summaries"

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
                    "tags": data.get("tags", []),
                },
            )
            graph.add_node(node)
            manifests_data[mid] = data

    # 2. 从 wiki/concepts/ 创建 concept 节点
    concept_file_map: dict[str, str] = {}  # concept_name -> concept_id
    if concepts_dir.exists():
        for cf in sorted(concepts_dir.glob("*.md")):
            name = cf.stem
            content = cf.read_text(encoding="utf-8", errors="ignore")
            concept_id = f"concept:{name}"

            node = GraphNode(
                id=concept_id,
                label=name,
                node_type="concept",
                metadata={"file": str(cf)},
            )
            graph.add_node(node)
            concept_file_map[name] = concept_id

            # 提取概念文件中的 wiki-links (关联概念)
            links = _WIKI_LINK_RE.findall(content)
            for link in links:
                link_name = link.strip()
                link_id = f"concept:{link_name}"
                # 延迟检查，因为目标概念可能尚未创建
                edge = GraphEdge(
                    source=concept_id,
                    target=link_id,
                    relation="related_to",
                    weight=0.5,
                )
                graph.add_edge(edge)

    # 3. 从 wiki/summaries/ 创建 summary 节点
    summary_concepts: dict[str, list[str]] = {}  # summary_id -> [concept_names]
    summary_tags: dict[str, list[str]] = {}  # summary_id -> [tags]
    if summaries_dir.exists():
        for sf in sorted(summaries_dir.glob("*.md")):
            name = sf.stem
            content = sf.read_text(encoding="utf-8", errors="ignore")
            summary_id = f"summary:{name}"

            node = GraphNode(
                id=summary_id,
                label=name,
                node_type="summary",
                metadata={"file": str(sf)},
            )
            graph.add_node(node)

            # 提取摘要中的概念链接
            concepts_in_summary: list[str] = []
            for match in _WIKI_LINK_RE.finditer(content):
                concept_name = match.group(1).strip()
                concepts_in_summary.append(concept_name)
                concept_id = f"concept:{concept_name}"
                edge = GraphEdge(
                    source=summary_id,
                    target=concept_id,
                    relation="contains_concept",
                )
                graph.add_edge(edge)
            summary_concepts[summary_id] = concepts_in_summary
            summary_tags[summary_id] = []  # 从文件名推断

    # 4. 根据 manifest 的 status 创建 source → summary 边
    for mid, data in manifests_data.items():
        status = data.get("status", "")
        if status in ("compiled", "promoted_to_wiki", "promoted"):
            # 尝试匹配 summary
            title_slug = _title_to_slug(data.get("title", mid))
            summary_id = f"summary:{title_slug}"
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
            for concept_name in concepts_list:
                concept_id = f"concept:{concept_name}"
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
        for cname in concepts:
            cid = f"concept:{cname}"
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
