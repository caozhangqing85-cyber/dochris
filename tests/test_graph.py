"""知识图谱测试"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from dochris.graph.builder import build_graph
from dochris.graph.models import GraphEdge, GraphNode, KnowledgeGraph

pytestmark = pytest.mark.fast


class TestGraphModels:
    """知识图谱数据模型测试"""

    def test_graph_node_creation(self) -> None:
        """测试节点创建"""
        node = GraphNode(
            id="SRC-0001",
            label="Test PDF",
            node_type="source",
            metadata={"type": "pdf", "quality_score": 90},
        )
        assert node.id == "SRC-0001"
        assert node.label == "Test PDF"
        assert node.node_type == "source"
        assert node.metadata["quality_score"] == 90

    def test_graph_edge_creation(self) -> None:
        """测试边创建"""
        edge = GraphEdge(source="SRC-0001", target="SUM-0001", relation="compiled_to", weight=1.0)
        assert edge.source == "SRC-0001"
        assert edge.relation == "compiled_to"

    def test_knowledge_graph_add_node(self) -> None:
        """测试添加节点"""
        g = KnowledgeGraph()
        node = GraphNode(id="SRC-0001", label="Test", node_type="source")
        g.add_node(node)
        assert g.get_node("SRC-0001") is not None
        assert g.get_node("NONEXISTENT") is None

    def test_knowledge_graph_add_edge(self) -> None:
        """测试添加边"""
        g = KnowledgeGraph()
        g.add_node(GraphNode(id="A", label="A", node_type="source"))
        g.add_node(GraphNode(id="B", label="B", node_type="concept"))
        g.add_edge(GraphEdge(source="A", target="B", relation="related_to"))
        assert len(g.edges) == 1

    def test_knowledge_graph_get_neighbors(self) -> None:
        """测试获取邻居节点"""
        g = KnowledgeGraph()
        g.add_node(GraphNode(id="A", label="A", node_type="source"))
        g.add_node(GraphNode(id="B", label="B", node_type="concept"))
        g.add_node(GraphNode(id="C", label="C", node_type="concept"))
        g.add_edge(GraphEdge(source="A", target="B", relation="related_to"))
        g.add_edge(GraphEdge(source="A", target="C", relation="related_to"))
        neighbors = g.get_neighbors("A")
        assert len(neighbors) == 2
        labels = {n.label for n in neighbors}
        assert labels == {"B", "C"}

    def test_knowledge_graph_to_dict(self) -> None:
        """测试 JSON 序列化"""
        g = KnowledgeGraph()
        g.add_node(GraphNode(id="SRC-1", label="Test", node_type="source"))
        d = g.to_dict()
        assert "nodes" in d
        assert "edges" in d
        assert len(d["nodes"]) == 1

    def test_knowledge_graph_to_d3(self) -> None:
        """测试 D3 格式输出"""
        g = KnowledgeGraph()
        g.add_node(GraphNode(id="n1", label="Node1", node_type="source"))
        g.add_edge(GraphEdge(source="n1", target="n2", relation="compiled_to"))
        d3 = g.to_d3()
        assert d3["nodes"][0]["group"] == "source"
        assert d3["links"][0]["source"] == "n1"

    def test_knowledge_graph_stats(self) -> None:
        """测试统计信息"""
        g = KnowledgeGraph()
        g.add_node(GraphNode(id="S1", label="S", node_type="source"))
        g.add_node(GraphNode(id="C1", label="C", node_type="concept"))
        g.add_edge(GraphEdge(source="S1", target="C1", relation="has_concept"))
        stats = g.stats()
        assert stats["total_nodes"] == 2
        assert stats["total_edges"] == 1
        assert stats["node_types"]["source"] == 1

    def test_knowledge_graph_search(self) -> None:
        """测试搜索节点"""
        g = KnowledgeGraph()
        g.add_node(GraphNode(id="S1", label="深度学习入门", node_type="source"))
        g.add_node(GraphNode(id="S2", label="Python 基础", node_type="source"))
        results = g.search("深度", limit=10)
        assert len(results) == 1
        assert results[0].id == "S1"

    def test_knowledge_graph_search_limit(self) -> None:
        """测试搜索数量限制"""
        g = KnowledgeGraph()
        for i in range(10):
            g.add_node(GraphNode(id=f"n{i}", label=f"测试{i}", node_type="source"))
        results = g.search("测试", limit=5)
        assert len(results) == 5

    def test_knowledge_graph_search_by_id(self) -> None:
        """测试通过 ID 搜索"""
        g = KnowledgeGraph()
        g.add_node(GraphNode(id="SRC-0001", label="完全无关", node_type="source"))
        results = g.search("SRC-0001")
        assert len(results) == 1

    def test_knowledge_graph_search_by_metadata(self) -> None:
        """测试通过 metadata 搜索"""
        g = KnowledgeGraph()
        g.add_node(
            GraphNode(id="n1", label="XXX", node_type="source", metadata={"tag": "机器学习"})
        )
        results = g.search("机器学习")
        assert len(results) == 1

    def test_graph_node_to_dict(self) -> None:
        """测试节点序列化"""
        node = GraphNode(id="S1", label="Test", node_type="source", metadata={"q": 90})
        d = node.to_dict()
        assert d["id"] == "S1"
        assert d["metadata"]["q"] == 90

    def test_edge_to_dict(self) -> None:
        """测试边序列化"""
        edge = GraphEdge(source="a", target="b", relation="related_to", weight=0.5)
        d = edge.to_dict()
        assert d["weight"] == 0.5

    def test_stats_top_connected(self) -> None:
        """测试 Top 连接数统计"""
        g = KnowledgeGraph()
        g.add_node(GraphNode(id="hub", label="Hub", node_type="source"))
        for i in range(5):
            g.add_node(GraphNode(id=f"n{i}", label=f"N{i}", node_type="concept"))
            g.add_edge(GraphEdge(source="hub", target=f"n{i}", relation="related_to"))
        stats = g.stats()
        assert stats["top_connected"][0]["id"] == "hub"
        assert stats["top_connected"][0]["degree"] == 5


class TestGraphBuilder:
    """图谱构建测试"""

    def test_build_graph_empty_workspace(self, tmp_path: Path) -> None:
        """测试空工作区"""
        graph = build_graph(tmp_path)
        stats = graph.stats()
        assert stats["total_nodes"] == 0
        assert stats["total_edges"] == 0

    def test_build_graph_with_manifests(self, tmp_path: Path) -> None:
        """测试从 manifest 构建 source 节点"""
        manifests_dir = tmp_path / "manifests" / "sources"
        manifests_dir.mkdir(parents=True)
        manifest = {
            "id": "SRC-0001",
            "title": "Test Document",
            "type": "pdf",
            "status": "compiled",
            "quality_score": 85,
            "tags": ["AI", "ML"],
        }
        (manifests_dir / "SRC-0001.json").write_text(json.dumps(manifest), encoding="utf-8")

        graph = build_graph(tmp_path)
        assert graph.get_node("SRC-0001") is not None
        assert graph.nodes["SRC-0001"].metadata["type"] == "pdf"

    def test_build_graph_with_concepts(self, tmp_path: Path) -> None:
        """测试从 wiki/concepts/ 创建 concept 节点"""
        concepts_dir = tmp_path / "wiki" / "concepts"
        concepts_dir.mkdir(parents=True)
        content = "# 深度学习\n\n深度学习是机器学习的子领域\n\n## 相关\n- [[神经网络]]\n"
        (concepts_dir / "深度学习.md").write_text(content, encoding="utf-8")

        graph = build_graph(tmp_path)
        assert "concept:深度学习" in graph.nodes

    def test_build_graph_with_summaries(self, tmp_path: Path) -> None:
        """测试从 wiki/summaries/ 创建 summary 节点"""
        summaries_dir = tmp_path / "wiki" / "summaries"
        summaries_dir.mkdir(parents=True)
        content = "# 摘要\n\n## 相关概念\n- [[概念A]]\n"
        (summaries_dir / "test.md").write_text(content, encoding="utf-8")

        graph = build_graph(tmp_path)
        assert "summary:test" in graph.nodes

    def test_build_graph_edges(self, tmp_path: Path) -> None:
        """测试同类型 source 节点的边"""
        manifests_dir = tmp_path / "manifests" / "sources"
        manifests_dir.mkdir(parents=True)

        for i in range(3):
            m = {
                "id": f"SRC-{i:04d}",
                "title": f"Doc {i}",
                "type": "pdf",
                "status": "compiled",
                "quality_score": 80,
                "tags": ["AI"],
            }
            (manifests_dir / f"SRC-{i:04d}.json").write_text(json.dumps(m), encoding="utf-8")

        graph = build_graph(tmp_path)
        same_type = [e for e in graph.edges if e.relation == "same_type"]
        assert len(same_type) >= 2

    def test_build_graph_summary_concept_edge(self, tmp_path: Path) -> None:
        """测试 summary → concept 边"""
        concepts_dir = tmp_path / "wiki" / "concepts"
        concepts_dir.mkdir(parents=True)
        summaries_dir = tmp_path / "wiki" / "summaries"
        summaries_dir.mkdir(parents=True)

        (concepts_dir / "测试概念.md").write_text("# 测试概念\n", encoding="utf-8")
        (summaries_dir / "test.md").write_text(
            "# 摘要\n\n## 相关概念\n- [[测试概念]]\n", encoding="utf-8"
        )

        graph = build_graph(tmp_path)
        has_edge = any(
            e.relation == "contains_concept"
            and e.source == "summary:test"
            and e.target == "concept:测试概念"
            for e in graph.edges
        )
        assert has_edge

    def test_build_graph_source_compiled_to_summary(self, tmp_path: Path) -> None:
        """测试 source → compiled_to → summary 边"""
        manifests_dir = tmp_path / "manifests" / "sources"
        manifests_dir.mkdir(parents=True)
        summaries_dir = tmp_path / "wiki" / "summaries"
        summaries_dir.mkdir(parents=True)

        manifest = {
            "id": "SRC-0001",
            "title": "test-title",
            "type": "article",
            "status": "compiled",
            "quality_score": 100,
        }
        (manifests_dir / "SRC-0001.json").write_text(
            json.dumps(manifest, ensure_ascii=False), encoding="utf-8"
        )
        (summaries_dir / "test-title.md").write_text("# 摘要\n", encoding="utf-8")

        graph = build_graph(tmp_path)
        has_compiled = any(
            e.relation == "compiled_to" and e.source == "SRC-0001" for e in graph.edges
        )
        assert has_compiled

    def test_build_graph_cleans_invalid_edges(self, tmp_path: Path) -> None:
        """测试清理无效边"""
        summaries_dir = tmp_path / "wiki" / "summaries"
        summaries_dir.mkdir(parents=True)
        content = "# 摘要\n\n## 相关概念\n- [[不存在的概念]]\n"
        (summaries_dir / "test.md").write_text(content, encoding="utf-8")

        graph = build_graph(tmp_path)
        valid_ids = set(graph.nodes.keys())
        for edge in graph.edges:
            assert edge.source in valid_ids
            assert edge.target in valid_ids

    def test_build_graph_manifest_with_concepts(self, tmp_path: Path) -> None:
        """测试 manifest 的 compiled_summary.concepts 创建边"""
        manifests_dir = tmp_path / "manifests" / "sources"
        manifests_dir.mkdir(parents=True)
        concepts_dir = tmp_path / "wiki" / "concepts"
        concepts_dir.mkdir(parents=True)

        (concepts_dir / "向量搜索.md").write_text("# 向量搜索\n", encoding="utf-8")

        manifest = {
            "id": "SRC-0001",
            "title": "Test",
            "type": "article",
            "status": "compiled",
            "compiled_summary": {"concepts": ["向量搜索"]},
        }
        (manifests_dir / "SRC-0001.json").write_text(
            json.dumps(manifest, ensure_ascii=False), encoding="utf-8"
        )

        graph = build_graph(tmp_path)
        has_concept_edge = any(
            e.source == "SRC-0001"
            and e.target == "concept:向量搜索"
            and e.relation == "contains_concept"
            for e in graph.edges
        )
        assert has_concept_edge

    def test_build_graph_invalid_manifest(self, tmp_path: Path) -> None:
        """测试无效 manifest 文件不导致崩溃"""
        manifests_dir = tmp_path / "manifests" / "sources"
        manifests_dir.mkdir(parents=True)
        (manifests_dir / "bad.json").write_text("not valid json{{", encoding="utf-8")

        graph = build_graph(tmp_path)
        # 应该正常完成，不崩溃
        assert isinstance(graph, KnowledgeGraph)

    def test_build_graph_concept_wiki_links(self, tmp_path: Path) -> None:
        """测试概念文件中的 wiki-links 创建 related_to 边"""
        concepts_dir = tmp_path / "wiki" / "concepts"
        concepts_dir.mkdir(parents=True)

        (concepts_dir / "概念A.md").write_text(
            "# 概念A\n\n## 相关\n- [[概念B]]\n", encoding="utf-8"
        )
        (concepts_dir / "概念B.md").write_text("# 概念B\n", encoding="utf-8")

        graph = build_graph(tmp_path)
        has_related = any(
            e.relation == "related_to"
            and e.source == "concept:概念A"
            and e.target == "concept:概念B"
            for e in graph.edges
        )
        assert has_related

    def test_build_graph_merges_identical_numbered_concept_aliases(self, tmp_path: Path) -> None:
        """完全相同的编号副本应合并，并保留可审计的别名与文件来源。"""
        concepts_dir = tmp_path / "wiki" / "concepts"
        concepts_dir.mkdir(parents=True)
        summaries_dir = tmp_path / "outputs" / "summaries"
        summaries_dir.mkdir(parents=True)

        content = "# 量子比特\n\n相同正文\n"
        base_file = concepts_dir / "量子比特.md"
        alias_file = concepts_dir / "量子比特_1.md"
        base_file.write_text(content, encoding="utf-8")
        alias_file.write_text(content, encoding="utf-8")
        (summaries_dir / "量子计算.md").write_text(
            "# 量子计算\n\n- [[量子比特_1]]\n", encoding="utf-8"
        )

        graph = build_graph(tmp_path)

        assert "concept:量子比特" in graph.nodes
        assert "concept:量子比特_1" not in graph.nodes
        metadata = graph.nodes["concept:量子比特"].metadata
        assert metadata["aliases"] == ["量子比特", "量子比特_1"]
        assert metadata["files"] == [str(base_file), str(alias_file)]
        assert metadata["duplicate_files"] == [str(alias_file)]
        assert any(
            edge.source == "summary:量子计算"
            and edge.target == "concept:量子比特"
            and edge.relation == "contains_concept"
            for edge in graph.edges
        )

    def test_build_graph_keeps_numbered_concept_without_equivalence_evidence(
        self, tmp_path: Path
    ) -> None:
        """仅有编号后缀不能证明等价，不能把独立概念静默合并。"""
        concepts_dir = tmp_path / "wiki" / "concepts"
        concepts_dir.mkdir(parents=True)
        (concepts_dir / "协议.md").write_text("# 协议\n\n基础概念\n", encoding="utf-8")
        (concepts_dir / "协议_1.md").write_text("# 协议_1\n\n独立概念\n", encoding="utf-8")

        graph = build_graph(tmp_path)

        assert "concept:协议" in graph.nodes
        assert "concept:协议_1" in graph.nodes

    def test_build_graph_preserves_source_variants_under_canonical_concept(
        self, tmp_path: Path
    ) -> None:
        """同标题的来源变体应共用概念身份，同时保留不同正文和 source 关联。"""
        concepts_dir = tmp_path / "outputs" / "concepts"
        concepts_dir.mkdir(parents=True)
        manifests_dir = tmp_path / "manifests" / "sources"
        manifests_dir.mkdir(parents=True)

        base_file = concepts_dir / "SOLID原则.md"
        variant_file = concepts_dir / "SOLID原则_SRC-0004.md"
        base_file.write_text("# SOLID原则\n\n版本 A\n", encoding="utf-8")
        variant_file.write_text("# SOLID原则\n\n版本 B\n", encoding="utf-8")
        manifest = {
            "id": "SRC-0004",
            "title": "SOLID",
            "type": "article",
            "status": "compiled",
            "compiled_summary": {"concepts": ["SOLID原则_SRC-0004"]},
        }
        (manifests_dir / "SRC-0004.json").write_text(
            json.dumps(manifest, ensure_ascii=False), encoding="utf-8"
        )

        graph = build_graph(tmp_path)

        assert "concept:SOLID原则" in graph.nodes
        assert "concept:SOLID原则_SRC-0004" not in graph.nodes
        metadata = graph.nodes["concept:SOLID原则"].metadata
        assert metadata["aliases"] == ["SOLID原则", "SOLID原则_SRC-0004"]
        assert metadata["files"] == [str(base_file), str(variant_file)]
        assert len(metadata["variants"]) == 2
        assert metadata["source_ids"] == ["SRC-0004"]
        assert any(
            edge.source == "SRC-0004"
            and edge.target == "concept:SOLID原则"
            and edge.relation == "contains_concept"
            for edge in graph.edges
        )

    def test_build_graph_merges_identical_summary_aliases_and_keeps_source_edge(
        self, tmp_path: Path
    ) -> None:
        """相同摘要的 SRC、标题和 promote 副本应只投影成一个文档节点。"""
        summaries_dir = tmp_path / "outputs" / "summaries"
        summaries_dir.mkdir(parents=True)
        wiki_summaries_dir = tmp_path / "wiki" / "summaries"
        wiki_summaries_dir.mkdir(parents=True)
        manifests_dir = tmp_path / "manifests" / "sources"
        manifests_dir.mkdir(parents=True)

        content = "# 摘要\n\n- [[量子比特]]\n"
        source_file = summaries_dir / "SRC-0002.md"
        title_alias = summaries_dir / "量子计算.md.md"
        promoted_alias = wiki_summaries_dir / "SRC-0002_1.md"
        for path in (source_file, title_alias, promoted_alias):
            path.write_text(content, encoding="utf-8")

        manifest = {
            "id": "SRC-0002",
            "title": "量子计算.md",
            "type": "article",
            "status": "promoted_to_wiki",
        }
        (manifests_dir / "SRC-0002.json").write_text(
            json.dumps(manifest, ensure_ascii=False), encoding="utf-8"
        )

        graph = build_graph(tmp_path)

        summary_nodes = [node for node in graph.nodes.values() if node.node_type == "summary"]
        assert [node.id for node in summary_nodes] == ["summary:SRC-0002"]
        metadata = summary_nodes[0].metadata
        assert metadata["aliases"] == ["SRC-0002", "量子计算.md", "SRC-0002_1"]
        assert metadata["files"] == [str(source_file), str(title_alias), str(promoted_alias)]
        assert metadata["duplicate_files"] == [str(title_alias), str(promoted_alias)]
        assert any(
            edge.source == "SRC-0002"
            and edge.target == "summary:SRC-0002"
            and edge.relation == "compiled_to"
            for edge in graph.edges
        )

    def test_schema_enrichment_consumes_canonical_graph(self, tmp_path: Path) -> None:
        """schema enrich 应写入 canonical 关系，不能回写文件别名节点。"""
        from dochris.quality.schema_evolution import enrich_manifests_from_graph

        concepts_dir = tmp_path / "outputs" / "concepts"
        concepts_dir.mkdir(parents=True)
        summaries_dir = tmp_path / "outputs" / "summaries"
        summaries_dir.mkdir(parents=True)
        manifests_dir = tmp_path / "manifests" / "sources"
        manifests_dir.mkdir(parents=True)

        concept_content = "# 量子比特\n\n概念正文\n"
        (concepts_dir / "量子比特.md").write_text(concept_content, encoding="utf-8")
        (concepts_dir / "量子比特_SRC-0002.md").write_text(concept_content, encoding="utf-8")
        summary_content = "# 摘要\n\n- [[量子比特_SRC-0002]]\n"
        (summaries_dir / "SRC-0002.md").write_text(summary_content, encoding="utf-8")
        (summaries_dir / "量子计算.md.md").write_text(summary_content, encoding="utf-8")
        manifest = {
            "id": "SRC-0002",
            "title": "量子计算.md",
            "type": "article",
            "status": "compiled",
            "compiled_summary": {"concepts": ["量子比特_SRC-0002"]},
        }
        manifest_path = manifests_dir / "SRC-0002.json"
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")

        result = enrich_manifests_from_graph(tmp_path)

        assert result["enriched"] == 1
        enriched = json.loads(manifest_path.read_text(encoding="utf-8"))
        target_ids = {relation["target_id"] for relation in enriched["graph_relations"]}
        assert "concept:量子比特" in target_ids
        assert "summary:SRC-0002" in target_ids
        assert "concept:量子比特_SRC-0002" not in target_ids
        assert "summary:量子计算.md" not in target_ids
