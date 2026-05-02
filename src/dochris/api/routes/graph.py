"""知识图谱路由 — GET /api/v1/graph"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Query

from dochris.graph.builder import build_graph
from dochris.settings import get_settings

logger = logging.getLogger(__name__)
router = APIRouter(tags=["graph"])


def _get_graph() -> Any:
    """获取缓存的图谱实例"""
    from dochris.graph.models import KnowledgeGraph

    settings = get_settings()
    graph: KnowledgeGraph = build_graph(settings.workspace)
    return graph


@router.get("/graph")
async def get_graph(format: str = Query("json", description="输出格式: json|d3|stats")) -> Any:
    """获取知识图谱数据"""
    graph = _get_graph()
    if format == "d3":
        return graph.to_d3()
    elif format == "stats":
        return graph.stats()
    else:
        return graph.to_dict()


@router.get("/graph/search")
async def search_graph(
    q: str = Query(..., description="搜索关键词"),
    limit: int = Query(20, ge=1, le=100, description="返回数量限制"),
) -> Any:
    """在图谱中搜索节点"""
    graph = _get_graph()
    nodes = graph.search(q, limit=limit)
    return {
        "query": q,
        "total": len(nodes),
        "nodes": [n.to_dict() for n in nodes],
    }


@router.get("/graph/node/{node_id}")
async def get_node(node_id: str) -> Any:
    """获取节点详情和邻居"""
    graph = _get_graph()
    node = graph.get_node(node_id)
    if not node:
        return {"error": f"节点不存在: {node_id}", "node": None}
    neighbors = graph.get_neighbors(node_id)
    return {
        "node": node.to_dict(),
        "neighbors": [n.to_dict() for n in neighbors],
        "neighbor_count": len(neighbors),
    }
