#!/usr/bin/env python3
"""
Schema Auto-Evolution：知识图谱驱动的 Manifest 结构自动优化

Karpathy 理论：Schema 层应随知识增长自动优化结构。
Dochris 实现：通过知识图谱反向丰富 manifest 元数据。

三大能力：
1. 编译配置指纹 — 追踪每个 manifest 编译时的完整配置
2. 图谱驱动丰富 — 从知识图谱反向写入关联关系到 manifest
3. 概念聚类标签 — 从概念共现模式自动生成标签

数据流：
  build_graph() → 知识图谱 → 提取关系/聚类 → 更新 manifest 元数据

新增 manifest 字段：
  compile_config: {prompt_version, model, temperature, config_hash}
  graph_relations: [{target_id, relation, weight}]
  auto_tags: [str]
  concepts_cluster: str | None

用法：
  from dochris.quality.schema_evolution import (
      compute_compile_config,
      enrich_manifests_from_graph,
      auto_tag_manifests,
      detect_stale_compilations,
  )
"""

import hashlib
import json
import logging
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

from dochris.graph.builder import build_graph
from dochris.log import append_log
from dochris.manifest import get_all_manifests
from dochris.settings import get_settings

logger = logging.getLogger(__name__)


# ============================================================
# 编译配置指纹
# ============================================================


def compute_compile_config(
    model: str = "",
    temperature: float = 0.1,
    prompt_version: str = "v1",
    chunk_size: int = 4000,
    chunk_overlap: int = 200,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """计算编译配置指纹

    将所有影响编译结果的参数序列化为配置字典，
    并计算哈希值用于变更检测。

    Args:
        model: LLM 模型名称
        temperature: 温度参数
        prompt_version: prompt 模板版本号
        chunk_size: 分块大小
        chunk_overlap: 分块重叠
        extra: 其他影响编译的参数

    Returns:
        配置字典，包含 config_hash 字段
    """
    config = {
        "model": model,
        "temperature": temperature,
        "prompt_version": prompt_version,
        "chunk_size": chunk_size,
        "chunk_overlap": chunk_overlap,
        "timestamp": datetime.now().isoformat(),
    }
    if extra:
        config.update(extra)

    # 计算配置哈希（排除 timestamp，只哈希影响输出的参数）
    hash_payload = json.dumps(
        {k: v for k, v in config.items() if k != "timestamp"},
        sort_keys=True,
    )
    config["config_hash"] = hashlib.sha256(hash_payload.encode()).hexdigest()[:16]

    return config


def stamp_manifest_config(
    workspace_path: Path,
    src_id: str,
    compile_config: dict[str, Any],
) -> bool:
    """为 manifest 打上编译配置指纹

    Args:
        workspace_path: 工作区路径
        src_id: manifest ID
        compile_config: compute_compile_config() 返回的配置

    Returns:
        是否成功
    """
    manifest_path = workspace_path / "manifests" / "sources" / f"{src_id}.json"
    if not manifest_path.exists():
        return False

    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["compile_config"] = compile_config
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return True
    except (json.JSONDecodeError, OSError) as e:
        logger.warning(f"写入编译配置失败 {src_id}: {e}")
        return False


# ============================================================
# 图谱驱动 Manifest 丰富
# ============================================================


def enrich_manifests_from_graph(workspace_path: Path) -> dict[str, Any]:
    """从知识图谱反向丰富 manifest 元数据

    将图谱中的关系（概念关联、主题聚类）写回 manifest，
    使 manifest 成为"活的"元数据，而非静态 JSON。

    Args:
        workspace_path: 工作区路径

    Returns:
        {"enriched": int, "errors": int, "details": str}
    """
    workspace_path = Path(workspace_path)

    # 构建知识图谱
    graph = build_graph(workspace_path)

    if not graph.nodes:
        return {"enriched": 0, "errors": 0, "details": "知识图谱为空"}

    # 按源文件节点提取关系
    source_nodes = {nid: n for nid, n in graph.nodes.items() if n.node_type == "source"}

    # 构建邻接表
    adjacency: dict[str, list[dict]] = defaultdict(list)
    for edge in graph.edges:
        adjacency[edge.source].append(
            {
                "target": edge.target,
                "relation": edge.relation,
                "weight": edge.weight,
            }
        )
        adjacency[edge.target].append(
            {
                "target": edge.source,
                "relation": f"reverse_{edge.relation}",
                "weight": edge.weight,
            }
        )

    enriched = 0
    errors = 0

    for src_id in source_nodes:
        manifest_path = workspace_path / "manifests" / "sources" / f"{src_id}.json"
        if not manifest_path.exists():
            continue

        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

            # 提取与该 manifest 相关的关系
            relations = []
            for edge_info in adjacency.get(src_id, []):
                target_id = edge_info["target"]
                if target_id in graph.nodes:
                    target_node = graph.nodes[target_id]
                    relations.append(
                        {
                            "target_id": target_id,
                            "target_label": target_node.label,
                            "target_type": target_node.node_type,
                            "relation": edge_info["relation"],
                            "weight": edge_info["weight"],
                        }
                    )

            # 按权重排序，取前 10 个最强关联
            relations.sort(key=lambda x: x["weight"], reverse=True)
            top_relations = relations[:10]

            if top_relations:
                manifest["graph_relations"] = top_relations
                manifest["graph_updated_at"] = datetime.now().isoformat()
                manifest_path.write_text(
                    json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
                )
                enriched += 1

        except (json.JSONDecodeError, OSError) as e:
            logger.warning(f"丰富 manifest 失败 {src_id}: {e}")
            errors += 1

    append_log(
        workspace_path,
        "SCHEMA_ENRICHMENT",
        f"enriched={enriched} errors={errors} nodes={len(graph.nodes)} edges={len(graph.edges)}",
    )

    return {
        "enriched": enriched,
        "errors": errors,
        "total_nodes": len(graph.nodes),
        "total_edges": len(graph.edges),
        "details": f"已丰富 {enriched} 个 manifest 的图谱关系",
    }


# ============================================================
# 概念聚类自动标签
# ============================================================


def auto_tag_manifests(workspace_path: Path) -> dict[str, Any]:
    """从概念共现模式自动生成 manifest 标签

    策略：
    1. 统计每个 manifest 的概念列表
    2. 通过概念共现构建主题聚类
    3. 将高频概念对作为标签写入 manifest

    Args:
        workspace_path: 工作区路径

    Returns:
        {"tagged": int, "tags_created": int, "details": str}
    """
    workspace_path = Path(workspace_path)
    manifests = get_all_manifests(workspace_path)

    # 收集每个 manifest 的概念列表
    manifest_concepts: dict[str, list[str]] = {}
    concept_counter = Counter()

    for m in manifests:
        compiled = m.get("compiled_summary") or {}
        concepts = compiled.get("concepts", [])
        if not isinstance(concepts, list):
            continue

        names = []
        for c in concepts:
            if isinstance(c, dict):
                name = c.get("name", "")
            elif isinstance(c, str):
                name = c
            else:
                continue
            if name:
                names.append(name)
                concept_counter[name] += 1

        if names:
            manifest_concepts[m["id"]] = names

    # 概念共现矩阵
    co_occurrence: Counter = Counter()
    for _src_id, concepts in manifest_concepts.items():
        unique = list(set(concepts))
        for i in range(len(unique)):
            for j in range(i + 1, len(unique)):
                pair = tuple(sorted([unique[i], unique[j]]))
                co_occurrence[pair] += 1

    # 构建概念到主题标签的映射
    # 策略：高频共现的概念对形成主题标签
    topic_map: dict[str, str] = {}
    for (c1, c2), count in co_occurrence.most_common(50):
        if count >= 2:
            label = f"{c1}+{c2}"
            topic_map.setdefault(c1, label)
            topic_map.setdefault(c2, label)

    # 为 manifest 生成自动标签
    tagged = 0
    tags_created = 0

    for m in manifests:
        src_id = m["id"]
        concepts = manifest_concepts.get(src_id, [])
        if not concepts:
            continue

        # 生成标签：概念名 + 共现主题
        auto_tags = list(set(concepts[:5]))
        for c in concepts:
            if c in topic_map:
                auto_tags.append(topic_map[c])

        auto_tags = list(set(auto_tags))[:10]
        if not auto_tags:
            continue

        # 写入 manifest
        manifest_path = workspace_path / "manifests" / "sources" / f"{src_id}.json"
        if not manifest_path.exists():
            continue

        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            existing_tags = set(manifest.get("tags", []))
            new_tags = [t for t in auto_tags if t not in existing_tags]

            if new_tags:
                manifest["tags"] = sorted(existing_tags | set(new_tags))
                manifest["auto_tags"] = new_tags
                manifest["auto_tagged_at"] = datetime.now().isoformat()
                manifest_path.write_text(
                    json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
                )
                tagged += 1
                tags_created += len(new_tags)
        except (json.JSONDecodeError, OSError) as e:
            logger.warning(f"写入自动标签失败 {src_id}: {e}")

    append_log(
        workspace_path,
        "AUTO_TAG",
        f"tagged={tagged} tags_created={tags_created}",
    )

    return {
        "tagged": tagged,
        "tags_created": tags_created,
        "concept_count": len(concept_counter),
        "topic_clusters": len(set(topic_map.values())),
        "details": f"已为 {tagged} 个 manifest 生成 {tags_created} 个自动标签",
    }


# ============================================================
# 陈旧编译检测
# ============================================================


def detect_stale_compilations(
    workspace_path: Path,
    current_config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """检测使用旧配置编译的 manifest

    对比每个 manifest 的 compile_config.config_hash 与当前配置哈希，
    找出需要重编译的陈旧 manifest。

    Args:
        workspace_path: 工作区路径
        current_config: 当前编译配置（None 则使用默认值）

    Returns:
        {"stale": list[str], "current_hash": str, "details": str}
    """
    workspace_path = Path(workspace_path)

    if current_config is None:
        settings = get_settings()
        current_config = compute_compile_config(
            model=settings.model,
            temperature=settings.llm_temperature,
        )

    current_hash = current_config.get("config_hash", "")
    manifests = get_all_manifests(workspace_path)

    stale = []
    up_to_date = []
    no_config = []

    for m in manifests:
        if m["status"] not in ("compiled", "promoted_to_wiki", "promoted"):
            continue

        compile_config = m.get("compile_config")
        if not compile_config:
            no_config.append(m["id"])
            continue

        manifest_hash = compile_config.get("config_hash", "")
        if manifest_hash != current_hash:
            stale.append(m["id"])
        else:
            up_to_date.append(m["id"])

    return {
        "stale": stale,
        "stale_count": len(stale),
        "up_to_date_count": len(up_to_date),
        "no_config_count": len(no_config),
        "current_hash": current_hash,
        "current_config": current_config,
        "details": f"检测到 {len(stale)} 个陈旧、{len(up_to_date)} 个最新、{len(no_config)} 个无配置",
    }
