"""知识图谱 CLI 命令"""

from __future__ import annotations

import json
import logging
from argparse import Namespace
from pathlib import Path

from dochris.cli.cli_utils import EXIT_FAILURE, EXIT_SUCCESS
from dochris.graph.builder import build_graph
from dochris.settings import get_settings

logger = logging.getLogger(__name__)


def cmd_graph(args: Namespace) -> int:
    """知识图谱操作

    Args:
        args: 命令行参数

    Returns:
        退出码
    """
    settings = get_settings()
    workspace = settings.workspace

    subcommand = getattr(args, "graph_command", None)

    if subcommand == "stats":
        return _cmd_stats(workspace)
    elif subcommand == "export":
        output = getattr(args, "output", None) or "graph.json"
        return _cmd_export(workspace, output)
    elif subcommand == "search":
        query = getattr(args, "query", "")
        if not query:
            print("错误: 请提供搜索关键词")
            return EXIT_FAILURE
        return _cmd_search(workspace, query)
    else:
        print("用法: kb graph <stats|export|search>")
        return EXIT_FAILURE


def _cmd_stats(workspace: Path) -> int:
    """显示图谱统计"""
    graph = build_graph(workspace)
    stats = graph.stats()

    print(f"节点总数: {stats['total_nodes']}")
    print(f"边总数:   {stats['total_edges']}")
    print()
    print("节点类型:")
    for ntype, count in stats.get("node_types", {}).items():
        print(f"  {ntype}: {count}")
    print()
    print("关系类型:")
    for rtype, count in stats.get("relation_types", {}).items():
        print(f"  {rtype}: {count}")

    top = stats.get("top_connected", [])
    if top:
        print()
        print("连接数 Top 10:")
        for item in top[:10]:
            print(f"  {item['label']} ({item['id']}): {item['degree']} 条连接")

    return EXIT_SUCCESS


def _cmd_export(workspace: Path, output_path: str) -> int:
    """导出图谱为 JSON"""
    graph = build_graph(workspace)
    data = graph.to_dict()

    out = Path(output_path)
    out.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"已导出到: {out}")
    print(f"  节点: {len(data['nodes'])}")
    print(f"  边:   {len(data['edges'])}")
    return EXIT_SUCCESS


def _cmd_search(workspace: Path, query: str) -> int:
    """搜索图谱节点"""
    graph = build_graph(workspace)
    nodes = graph.search(query)

    if not nodes:
        print(f"未找到匹配 '{query}' 的节点")
        return EXIT_SUCCESS

    print(f"找到 {len(nodes)} 个匹配节点:")
    for node in nodes:
        neighbors = graph.get_neighbors(node.id)
        print(f"  [{node.node_type}] {node.label} (id: {node.id}, 连接: {len(neighbors)})")

    return EXIT_SUCCESS
