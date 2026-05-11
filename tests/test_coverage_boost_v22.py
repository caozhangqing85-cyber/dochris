"""覆盖率提升 v22 — auth API key + graph builder/models + web app handlers"""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


# ============================================================
# api/auth.py — 覆盖认证拒绝分支 (lines 19-23)
# ============================================================
class TestApiKeyAuth:
    """API Key 认证中间件测试"""

    @pytest.mark.asyncio
    async def test_valid_api_key_header(self, monkeypatch):
        """有效的 API Key 通过 header 传递"""
        monkeypatch.setenv("DOCHRIS_API_KEY", "test-secret-key")
        from dochris.api.auth import verify_api_key

        request = MagicMock()
        request.headers = {"X-API-Key": "test-secret-key"}
        request.query_params = {}

        # 不应抛出异常
        await verify_api_key(request)

    @pytest.mark.asyncio
    async def test_valid_api_key_query_param(self, monkeypatch):
        """有效的 API Key 通过 query param 传递"""
        monkeypatch.setenv("DOCHRIS_API_KEY", "test-secret-key")
        from dochris.api.auth import verify_api_key

        request = MagicMock()
        request.headers = {"X-API-Key": None}
        request.query_params = {"api_key": "test-secret-key"}

        await verify_api_key(request)

    @pytest.mark.asyncio
    async def test_invalid_api_key_raises_401(self, monkeypatch):
        """无效的 API Key 抛出 401"""
        monkeypatch.setenv("DOCHRIS_API_KEY", "test-secret-key")
        from dochris.api.auth import verify_api_key

        request = MagicMock()
        request.headers = {"X-API-Key": "wrong-key"}
        request.query_params = {"api_key": ""}

        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            await verify_api_key(request)
        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_no_api_key_configured_skips_auth(self, monkeypatch):
        """未配置 DOCHRIS_API_KEY 时跳过认证"""
        monkeypatch.delenv("DOCHRIS_API_KEY", raising=False)
        from dochris.api.auth import verify_api_key

        request = MagicMock()
        # 不应抛出异常
        await verify_api_key(request)


# ============================================================
# graph/models.py — to_d3, stats, search, get_neighbors
# ============================================================
class TestKnowledgeGraphModels:
    """知识图谱数据模型测试"""

    def test_to_d3_format(self):
        """to_d3 输出 D3.js 兼容格式"""
        from dochris.graph.models import GraphEdge, GraphNode, KnowledgeGraph

        graph = KnowledgeGraph()
        graph.add_node(
            GraphNode(id="src-1", label="文件1", node_type="source", metadata={"type": "pdf"})
        )
        graph.add_node(GraphNode(id="concept:AI", label="AI", node_type="concept"))
        graph.add_edge(
            GraphEdge(source="src-1", target="concept:AI", relation="contains_concept", weight=1.0)
        )

        d3 = graph.to_d3()
        assert len(d3["nodes"]) == 2
        assert d3["nodes"][0]["group"] == "source"
        assert d3["nodes"][1]["group"] == "concept"
        assert len(d3["links"]) == 1
        assert d3["links"][0]["source"] == "src-1"
        assert d3["links"][0]["target"] == "concept:AI"

    def test_stats(self):
        """stats 输出正确统计信息"""
        from dochris.graph.models import GraphEdge, GraphNode, KnowledgeGraph

        graph = KnowledgeGraph()
        graph.add_node(GraphNode(id="s1", label="A", node_type="source"))
        graph.add_node(GraphNode(id="s2", label="B", node_type="source"))
        graph.add_node(GraphNode(id="c1", label="C", node_type="concept"))
        graph.add_edge(GraphEdge(source="s1", target="c1", relation="contains_concept"))
        graph.add_edge(GraphEdge(source="s2", target="c1", relation="contains_concept"))

        stats = graph.stats()
        assert stats["total_nodes"] == 3
        assert stats["total_edges"] == 2
        assert stats["node_types"]["source"] == 2
        assert stats["node_types"]["concept"] == 1
        assert stats["relation_types"]["contains_concept"] == 2
        assert len(stats["top_connected"]) == 3
        assert stats["top_connected"][0]["id"] == "c1"
        assert stats["top_connected"][0]["degree"] == 2

    def test_search_by_label(self):
        """search 通过标签搜索"""
        from dochris.graph.models import GraphNode, KnowledgeGraph

        graph = KnowledgeGraph()
        graph.add_node(GraphNode(id="1", label="机器学习入门", node_type="source"))
        graph.add_node(GraphNode(id="2", label="深度学习基础", node_type="source"))

        results = graph.search("机器")
        assert len(results) == 1
        assert results[0].label == "机器学习入门"

    def test_search_by_id(self):
        """search 通过 ID 搜索"""
        from dochris.graph.models import GraphNode, KnowledgeGraph

        graph = KnowledgeGraph()
        graph.add_node(GraphNode(id="SRC-0001", label="文档", node_type="source"))

        results = graph.search("SRC")
        assert len(results) == 1

    def test_search_by_metadata(self):
        """search 通过 metadata 搜索"""
        from dochris.graph.models import GraphNode, KnowledgeGraph

        graph = KnowledgeGraph()
        graph.add_node(
            GraphNode(id="1", label="X", node_type="source", metadata={"desc": "人工智能"})
        )

        results = graph.search("人工智能")
        assert len(results) == 1

    def test_get_neighbors(self):
        """获取邻居节点"""
        from dochris.graph.models import GraphEdge, GraphNode, KnowledgeGraph

        graph = KnowledgeGraph()
        graph.add_node(GraphNode(id="a", label="A", node_type="source"))
        graph.add_node(GraphNode(id="b", label="B", node_type="source"))
        graph.add_node(GraphNode(id="c", label="C", node_type="source"))
        graph.add_edge(GraphEdge(source="a", target="b", relation="r1"))
        graph.add_edge(GraphEdge(source="c", target="a", relation="r2"))

        neighbors = graph.get_neighbors("a")
        neighbor_ids = {n.id for n in neighbors}
        assert neighbor_ids == {"b", "c"}


# ============================================================
# graph/builder.py — _title_to_slug + build_graph with mock fs
# ============================================================
class TestGraphBuilder:
    """知识图谱构建器测试"""

    def test_title_to_slug(self):
        """标题转 slug"""
        from dochris.graph.builder import _title_to_slug

        assert _title_to_slug("hello world") == "hello-world"
        assert _title_to_slug("  spaces  ") == "spaces"
        assert _title_to_slug("no-changes") == "no-changes"

    def test_build_graph_empty_workspace(self, tmp_path):
        """空工作区返回空图谱"""
        from dochris.graph.builder import build_graph

        graph = build_graph(tmp_path)
        assert len(graph.nodes) == 0
        assert len(graph.edges) == 0

    def test_build_graph_with_manifests(self, tmp_path):
        """从 manifest 构建图谱"""
        from dochris.graph.builder import build_graph

        manifests_dir = tmp_path / "manifests" / "sources"
        manifests_dir.mkdir(parents=True)

        manifest = {
            "id": "SRC-0001",
            "title": "测试文档",
            "type": "pdf",
            "status": "compiled",
            "quality_score": 95,
            "tags": ["test"],
        }
        (manifests_dir / "SRC-0001.json").write_text(
            json.dumps(manifest, ensure_ascii=False), encoding="utf-8"
        )

        graph = build_graph(tmp_path)
        assert "SRC-0001" in graph.nodes
        assert graph.nodes["SRC-0001"].node_type == "source"
        assert graph.nodes["SRC-0001"].label == "测试文档"

    def test_build_graph_with_concepts(self, tmp_path):
        """从 concept 文件构建图谱"""
        from dochris.graph.builder import build_graph

        manifests_dir = tmp_path / "manifests" / "sources"
        manifests_dir.mkdir(parents=True)
        concepts_dir = tmp_path / "wiki" / "concepts"
        concepts_dir.mkdir(parents=True)

        (manifests_dir / "empty.json").write_text("{}", encoding="utf-8")
        concept_content = "# AI\n\n相关概念: [[机器学习]] [[深度学习]]\n"
        (concepts_dir / "AI.md").write_text(concept_content, encoding="utf-8")
        (concepts_dir / "机器学习.md").write_text("# 机器学习\n", encoding="utf-8")

        graph = build_graph(tmp_path)
        assert "concept:AI" in graph.nodes
        assert "concept:机器学习" in graph.nodes
        # AI -> 机器学习, AI -> 深度学习 edges
        concept_edges = [e for e in graph.edges if e.relation == "related_to"]
        assert len(concept_edges) >= 1

    def test_build_graph_with_summaries(self, tmp_path):
        """从 summary 文件构建图谱"""
        from dochris.graph.builder import build_graph

        manifests_dir = tmp_path / "manifests" / "sources"
        manifests_dir.mkdir(parents=True)
        summaries_dir = tmp_path / "wiki" / "summaries"
        summaries_dir.mkdir(parents=True)
        concepts_dir = tmp_path / "wiki" / "concepts"
        concepts_dir.mkdir(parents=True)

        manifest = {
            "id": "SRC-0001",
            "title": "test-doc",
            "type": "article",
            "status": "compiled",
        }
        (manifests_dir / "SRC-0001.json").write_text(
            json.dumps(manifest, ensure_ascii=False), encoding="utf-8"
        )
        summary = "# test-doc\n\n包含概念 [[AI]]\n"
        (summaries_dir / "test-doc.md").write_text(summary, encoding="utf-8")
        (concepts_dir / "AI.md").write_text("# AI\n", encoding="utf-8")

        graph = build_graph(tmp_path)
        assert "summary:test-doc" in graph.nodes
        # source → summary edge
        compiled_edges = [
            e for e in graph.edges if e.source == "SRC-0001" and e.relation == "compiled_to"
        ]
        assert len(compiled_edges) == 1

    def test_build_graph_corrupted_manifest(self, tmp_path):
        """损坏的 manifest 文件被跳过"""
        from dochris.graph.builder import build_graph

        manifests_dir = tmp_path / "manifests" / "sources"
        manifests_dir.mkdir(parents=True)

        (manifests_dir / "bad.json").write_text("{invalid json", encoding="utf-8")

        graph = build_graph(tmp_path)
        assert len(graph.nodes) == 0


# ============================================================
# web/app.py — handler edge cases
# ============================================================
class TestWebAppHandlers:
    """Web UI handler 边界测试"""

    def test_handle_query_empty_input(self):
        """空查询返回提示"""
        from dochris.web.app import handle_query

        result = handle_query("", 5)
        assert "请输入查询内容" in result

    def test_handle_query_exception(self):
        """查询异常返回错误"""
        from dochris.web.app import handle_query

        with patch("dochris.web.query_tab._do_query", side_effect=RuntimeError("fail")):
            result = handle_query("test", 5)
        assert "查询出错" in result

    def test_handle_refresh_files_exception(self):
        """刷新文件异常"""
        from dochris.web.app import handle_refresh_files

        with patch("dochris.web.file_tab._get_file_table", side_effect=RuntimeError("fail")):
            rows, status = handle_refresh_files()
        assert rows == []
        assert "刷新失败" in status

    def test_handle_refresh_status_exception(self):
        """获取状态异常"""
        from dochris.web.app import handle_refresh_status

        with patch("dochris.web.status_tab.get_system_status", side_effect=RuntimeError("fail")):
            result = handle_refresh_status()
        assert "获取状态失败" in result

    def test_handle_refresh_quality_exception(self):
        """获取质量数据异常"""
        from dochris.web.app import handle_refresh_quality

        with patch(
            "dochris.web.quality_tab._get_quality_dashboard", side_effect=RuntimeError("fail")
        ):
            result = handle_refresh_quality()
        assert "获取质量数据失败" in result

    def test_handle_upload_no_files(self):
        """无文件上传"""
        from dochris.web.app import handle_upload

        rows, status = handle_upload([])
        assert rows == []
        assert "未选择文件" in status

    def test_format_query_results_empty(self):
        """空结果格式化"""
        from dochris.web.app import _format_query_results

        result = _format_query_results({"time_seconds": 0.5})
        assert "未找到相关结果" in result

    def test_format_query_results_with_vector(self):
        """有向量结果的格式化"""
        from dochris.web.app import _format_query_results

        result = _format_query_results(
            {
                "time_seconds": 0.1,
                "vector_results": [
                    {"score": 0.95, "title": "测试", "content": "内容", "source": "/test.md"}
                ],
            }
        )
        assert "测试" in result
        assert "0.950" in result

    def test_format_query_results_with_concepts(self):
        """有概念匹配的格式化"""
        from dochris.web.app import _format_query_results

        result = _format_query_results(
            {
                "time_seconds": 0.1,
                "concepts": [{"name": "AI"}],
            }
        )
        assert "AI" in result

    def test_format_query_results_with_answer(self):
        """有 AI 回答的格式化"""
        from dochris.web.app import _format_query_results

        result = _format_query_results(
            {
                "time_seconds": 1.0,
                "answer": "这是AI回答",
            }
        )
        assert "AI 回答" in result
        assert "这是AI回答" in result

    def test_handle_upload_with_files(self, tmp_path):
        """有文件上传"""
        from dochris.web.app import handle_upload

        mock_settings = MagicMock()
        mock_settings.workspace = tmp_path
        mock_settings.raw_dir = tmp_path / "raw"

        source_file = tmp_path / "source" / "测试文件.md"
        source_file.parent.mkdir()
        source_file.write_text("hello", encoding="utf-8")
        mock_file = MagicMock(name=str(source_file))
        mock_file.name = str(source_file)
        mock_file.orig_name = "测试文件.md"

        with patch("dochris.web.file_tab.get_settings", return_value=mock_settings):
            rows, status = handle_upload([mock_file])

        assert "新增待编译 1 个" in status
        assert rows[0][1] == "测试文件.md"

    def test_handle_upload_with_filedata_dict(self, tmp_path):
        """兼容 Gradio API 传入的 FileData dict"""
        from dochris.web.app import handle_upload

        mock_settings = MagicMock()
        mock_settings.workspace = tmp_path
        mock_settings.raw_dir = tmp_path / "raw"

        source_file = tmp_path / "source" / "api-temp-name.md"
        source_file.parent.mkdir()
        source_file.write_text("hello", encoding="utf-8")
        file_data = {"path": str(source_file), "orig_name": "接口上传文件.md"}

        with patch("dochris.web.file_tab.get_settings", return_value=mock_settings):
            rows, status = handle_upload([file_data])

        assert "新增待编译 1 个" in status
        assert rows[0][1] == "接口上传文件.md"
        assert rows[0][5] == "raw/articles/接口上传文件.md"

    def test_handle_compile_exception(self):
        """编译异常"""
        from dochris.web.app import handle_compile

        with patch("asyncio.run", side_effect=RuntimeError("compile fail")):
            result = handle_compile(10)
        assert "编译出错" in result

    def test_handle_graph_refresh_exception(self):
        """图谱刷新异常"""
        from dochris.web.app import _handle_graph_refresh

        with patch("dochris.web.graph_tab._get_graph_html", side_effect=RuntimeError("graph fail")):
            result = _handle_graph_refresh()
        assert "获取知识图谱失败" in result

    def test_build_graph_with_manifest_concepts(self, tmp_path):
        """manifest 有 compiled_summary.concepts 时创建边"""
        from dochris.graph.builder import build_graph

        manifests_dir = tmp_path / "manifests" / "sources"
        manifests_dir.mkdir(parents=True)
        concepts_dir = tmp_path / "wiki" / "concepts"
        concepts_dir.mkdir(parents=True)

        manifest = {
            "id": "SRC-0001",
            "title": "Doc",
            "type": "pdf",
            "status": "compiled",
            "compiled_summary": {
                "concepts": ["AI", "ML"],
            },
        }
        (manifests_dir / "SRC-0001.json").write_text(
            json.dumps(manifest, ensure_ascii=False), encoding="utf-8"
        )
        (concepts_dir / "AI.md").write_text("# AI\n", encoding="utf-8")
        (concepts_dir / "ML.md").write_text("# ML\n", encoding="utf-8")

        graph = build_graph(tmp_path)
        concept_edges = [
            e for e in graph.edges if e.source == "SRC-0001" and e.relation == "contains_concept"
        ]
        assert len(concept_edges) == 2

    def test_build_graph_same_type_edges(self, tmp_path):
        """同类型 source 创建 same_type 边"""
        from dochris.graph.builder import build_graph

        manifests_dir = tmp_path / "manifests" / "sources"
        manifests_dir.mkdir(parents=True)

        for i in range(3):
            manifest = {
                "id": f"SRC-{i:04d}",
                "title": f"Doc{i}",
                "type": "pdf",
                "status": "ingested",
            }
            (manifests_dir / f"SRC-{i:04d}.json").write_text(
                json.dumps(manifest, ensure_ascii=False), encoding="utf-8"
            )

        graph = build_graph(tmp_path)
        same_type_edges = [e for e in graph.edges if e.relation == "same_type"]
        assert len(same_type_edges) == 3  # C(3,2) = 3

    def test_build_graph_with_summary_concepts_overlap(self, tmp_path):
        """多个 summary 共享概念时创建 summary→summary 边"""
        from dochris.graph.builder import build_graph

        manifests_dir = tmp_path / "manifests" / "sources"
        manifests_dir.mkdir(parents=True)
        summaries_dir = tmp_path / "wiki" / "summaries"
        summaries_dir.mkdir(parents=True)
        concepts_dir = tmp_path / "wiki" / "concepts"
        concepts_dir.mkdir(parents=True)

        (manifests_dir / "empty.json").write_text("{}", encoding="utf-8")
        (summaries_dir / "doc1.md").write_text("# Doc1\n\n包含 [[AI]]\n", encoding="utf-8")
        (summaries_dir / "doc2.md").write_text("# Doc2\n\n包含 [[AI]]\n", encoding="utf-8")
        (concepts_dir / "AI.md").write_text("# AI\n", encoding="utf-8")

        graph = build_graph(tmp_path)
        # summary:doc1 → summary:doc2 related_to edge (via shared concept AI)
        related_edges = [
            e
            for e in graph.edges
            if e.relation == "related_to"
            and e.source.startswith("summary:")
            and e.target.startswith("summary:")
        ]
        assert len(related_edges) >= 1
