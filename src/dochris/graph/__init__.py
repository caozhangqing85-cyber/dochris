"""知识图谱模块 — 从 manifests + wiki 构建知识图谱"""

from dochris.graph.builder import build_graph
from dochris.graph.models import KnowledgeGraph

__all__ = ["KnowledgeGraph", "build_graph"]
