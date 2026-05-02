"""知识图谱数据模型"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class GraphNode:
    """图节点"""

    id: str
    label: str
    node_type: str  # "source", "concept", "summary"
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """序列化为字典"""
        return {
            "id": self.id,
            "label": self.label,
            "node_type": self.node_type,
            "metadata": self.metadata,
        }


@dataclass
class GraphEdge:
    """图边"""

    source: str  # node id
    target: str  # node id
    relation: str  # "compiled_to", "contains_concept", "related_to", "same_type"
    weight: float = 1.0

    def to_dict(self) -> dict[str, Any]:
        """序列化为字典"""
        return {
            "source": self.source,
            "target": self.target,
            "relation": self.relation,
            "weight": self.weight,
        }


@dataclass
class KnowledgeGraph:
    """知识图谱"""

    nodes: dict[str, GraphNode] = field(default_factory=dict)
    edges: list[GraphEdge] = field(default_factory=list)

    def add_node(self, node: GraphNode) -> None:
        """添加节点"""
        self.nodes[node.id] = node

    def add_edge(self, edge: GraphEdge) -> None:
        """添加边"""
        self.edges.append(edge)

    def get_node(self, node_id: str) -> GraphNode | None:
        """获取节点"""
        return self.nodes.get(node_id)

    def get_neighbors(self, node_id: str) -> list[GraphNode]:
        """获取邻居节点"""
        neighbor_ids: set[str] = set()
        for edge in self.edges:
            if edge.source == node_id:
                neighbor_ids.add(edge.target)
            elif edge.target == node_id:
                neighbor_ids.add(edge.source)
        return [self.nodes[nid] for nid in neighbor_ids if nid in self.nodes]

    def to_dict(self) -> dict[str, Any]:
        """JSON 序列化"""
        return {
            "nodes": [n.to_dict() for n in self.nodes.values()],
            "edges": [e.to_dict() for e in self.edges],
        }

    def to_d3(self) -> dict[str, Any]:
        """D3.js 力导向图格式"""
        return {
            "nodes": [
                {
                    "id": n.id,
                    "label": n.label,
                    "group": n.node_type,
                    "metadata": n.metadata,
                }
                for n in self.nodes.values()
            ],
            "links": [
                {
                    "source": e.source,
                    "target": e.target,
                    "relation": e.relation,
                    "weight": e.weight,
                }
                for e in self.edges
            ],
        }

    def stats(self) -> dict[str, Any]:
        """统计信息"""
        type_counts: dict[str, int] = {}
        for node in self.nodes.values():
            type_counts[node.node_type] = type_counts.get(node.node_type, 0) + 1

        relation_counts: dict[str, int] = {}
        for edge in self.edges:
            relation_counts[edge.relation] = relation_counts.get(edge.relation, 0) + 1

        # 计算节点连接数
        degree: dict[str, int] = {}
        for edge in self.edges:
            degree[edge.source] = degree.get(edge.source, 0) + 1
            degree[edge.target] = degree.get(edge.target, 0) + 1

        top_connected = sorted(degree.items(), key=lambda x: x[1], reverse=True)[:10]

        return {
            "total_nodes": len(self.nodes),
            "total_edges": len(self.edges),
            "node_types": type_counts,
            "relation_types": relation_counts,
            "top_connected": [
                {
                    "id": nid,
                    "label": self.nodes[nid].label if nid in self.nodes else nid,
                    "degree": deg,
                }
                for nid, deg in top_connected
            ],
        }

    def search(self, query: str, limit: int = 20) -> list[GraphNode]:
        """在图谱中搜索节点（标签匹配）"""
        query_lower = query.lower()
        results: list[tuple[int, GraphNode]] = []
        for node in self.nodes.values():
            label_lower = node.label.lower()
            if query_lower in label_lower:
                score = 2 if label_lower == query_lower else 1
                results.append((score, node))
            elif query_lower in node.id.lower():
                results.append((1, node))
            else:
                # 搜索 metadata
                for v in node.metadata.values():
                    if isinstance(v, str) and query_lower in v.lower():
                        results.append((0, node))
                        break

        results.sort(key=lambda x: x[0], reverse=True)
        return [node for _, node in results[:limit]]
