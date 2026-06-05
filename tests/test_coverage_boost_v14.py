"""覆盖率提升 v14 — phases/phase3_query.py + workers/__main__.py"""

from unittest.mock import MagicMock, patch


# ============================================================
# phases/phase3_query.py — mock query_engine / query_utils
# ============================================================
class TestPhase3QueryModule:
    """Test the query function and module-level logic"""

    def test_search_all_combines_sources(self):
        """search_all aggregates concepts, summaries, and vector results"""
        with (
            patch("dochris.phases.phase3_query.search_concepts", return_value=[{"source": "wiki"}]),
            patch(
                "dochris.phases.phase3_query.search_summaries", return_value=[{"source": "outputs"}]
            ),
            patch("dochris.phases.phase3_query.vector_search", return_value=[{"id": "v1"}]),
        ):
            from dochris.phases.phase3_query import search_all

            result = search_all("test query", top_k=5)
        assert "concepts" in result
        assert "summaries" in result
        assert "vector_results" in result
        assert "wiki" in result["search_sources"]
        assert "outputs" in result["search_sources"]
        assert "vector" in result["search_sources"]

    def test_search_all_empty(self):
        with (
            patch("dochris.phases.phase3_query.search_concepts", return_value=[]),
            patch("dochris.phases.phase3_query.search_summaries", return_value=[]),
            patch("dochris.phases.phase3_query.vector_search", return_value=[]),
        ):
            from dochris.phases.phase3_query import search_all

            result = search_all("nonexistent")
        assert result["concepts"] == []
        assert result["search_sources"] == []

    def test_query_mode_concept(self):
        with (
            patch("dochris.phases.phase3_query.search_concepts", return_value=[{"source": "wiki"}]),
            patch("dochris.phases.phase3_query.search_summaries", return_value=[]),
        ):
            from dochris.phases.phase3_query import query

            result = query("test", mode="concept")
        assert len(result["concepts"]) == 1
        assert "wiki" in result["search_sources"]
        assert result["mode"] == "concept"

    def test_query_mode_summary(self):
        with (
            patch("dochris.phases.phase3_query.search_concepts", return_value=[]),
            patch(
                "dochris.phases.phase3_query.search_summaries", return_value=[{"source": "outputs"}]
            ),
        ):
            from dochris.phases.phase3_query import query

            result = query("test", mode="summary")
        assert len(result["summaries"]) == 1

    def test_query_mode_vector(self):
        with patch("dochris.phases.phase3_query.vector_search", return_value=[{"id": "v1"}]):
            from dochris.phases.phase3_query import query

            result = query("test", mode="vector")
        assert len(result["vector_results"]) == 1
        assert "vector" in result["search_sources"]

    def test_query_mode_combined(self):
        with (
            patch("dochris.phases.phase3_query.search_concepts", return_value=[{"source": "wiki"}]),
            patch(
                "dochris.phases.phase3_query.search_summaries", return_value=[{"source": "outputs"}]
            ),
            patch("dochris.phases.phase3_query.vector_search", return_value=[{"id": "v1"}]),
            patch("dochris.phases.phase3_query.create_client", return_value=MagicMock()),
            patch("dochris.phases.phase3_query.generate_answer", return_value="answer text"),
        ):
            from dochris.phases.phase3_query import query

            result = query("test", mode="combined")
        assert result["answer"] == "answer text"
        assert len(result["search_sources"]) == 3

    def test_query_mode_combined_no_llm(self):
        with (
            patch("dochris.phases.phase3_query.search_concepts", return_value=[{"source": "wiki"}]),
            patch("dochris.phases.phase3_query.search_summaries", return_value=[]),
            patch("dochris.phases.phase3_query.vector_search", return_value=[]),
            patch("dochris.phases.phase3_query.create_client", return_value=None),
        ):
            from dochris.phases.phase3_query import query

            result = query("test", mode="combined")
        assert "LLM 不可用" in result["answer"]

    def test_query_mode_all(self):
        with (
            patch(
                "dochris.phases.phase3_query.search_all",
                return_value={
                    "concepts": [{"source": "wiki"}],
                    "summaries": [],
                    "vector_results": [{"id": "v1"}],
                    "search_sources": ["wiki", "vector"],
                },
            ),
            patch("dochris.phases.phase3_query.create_client", return_value=MagicMock()),
            patch("dochris.phases.phase3_query.generate_answer", return_value="combined answer"),
        ):
            from dochris.phases.phase3_query import query

            result = query("test", mode="all")
        assert result["answer"] == "combined answer"

    def test_query_returns_time(self):
        with patch("dochris.phases.phase3_query.search_concepts", return_value=[]):
            from dochris.phases.phase3_query import query

            result = query("test", mode="concept")
        assert "time_seconds" in result
        assert isinstance(result["time_seconds"], float)

    def test_query_mode_combined_no_results(self):
        """Combined mode with no results shouldn't call LLM"""
        with (
            patch("dochris.phases.phase3_query.search_concepts", return_value=[]),
            patch("dochris.phases.phase3_query.search_summaries", return_value=[]),
            patch("dochris.phases.phase3_query.vector_search", return_value=[]),
        ):
            from dochris.phases.phase3_query import query

            result = query("test", mode="combined")
        assert result["answer"] is None  # No LLM call


class TestVectorSearch:
    def test_vector_search_delegates(self):
        """vector_search delegates to query_engine.vector_search"""
        with patch("dochris.phases.phase3_query.query_engine") as mock_qe:
            mock_qe.vector_search.return_value = [{"id": "v1"}]
            mock_qe._chromadb_client_cache = None
            from dochris.phases.phase3_query import vector_search

            result = vector_search("query", top_k=3)
        assert len(result) == 1


class TestInteractiveMode:
    def test_interactive_quit(self):
        from dochris.phases.phase3_query import interactive_mode

        with patch("builtins.input", return_value="quit"):
            logger = MagicMock()
            interactive_mode(logger)

    def test_interactive_exit(self):
        from dochris.phases.phase3_query import interactive_mode

        with patch("builtins.input", return_value="exit"):
            logger = MagicMock()
            interactive_mode(logger)

    def test_interactive_eof(self):
        from dochris.phases.phase3_query import interactive_mode

        with patch("builtins.input", side_effect=EOFError):
            logger = MagicMock()
            interactive_mode(logger)

    def test_interactive_keyboard_interrupt(self):
        from dochris.phases.phase3_query import interactive_mode

        with patch("builtins.input", side_effect=KeyboardInterrupt):
            logger = MagicMock()
            interactive_mode(logger)

    def test_interactive_empty_input(self):
        from dochris.phases.phase3_query import interactive_mode

        with patch("builtins.input", side_effect=["", "quit"]):
            logger = MagicMock()
            interactive_mode(logger)

    def test_interactive_with_mode_prefix(self):
        from dochris.phases.phase3_query import interactive_mode

        with (
            patch(
                "dochris.phases.phase3_query.query",
                return_value={
                    "query": "test",
                    "mode": "concept",
                    "concepts": [],
                    "summaries": [],
                    "vector_results": [],
                    "search_sources": [],
                    "answer": None,
                    "time_seconds": 0.1,
                },
            ) as mock_query,
            patch("dochris.phases.phase3_query.print_result"),
            patch("builtins.input", side_effect=["concept test query", "quit"]),
        ):
            logger = MagicMock()
            interactive_mode(logger)
            mock_query.assert_called_once_with("test query", mode="concept", logger=logger)


# ============================================================
# workers/__main__.py
# ============================================================
class TestWorkersMain:
    def test_main_imports_succeed(self, capsys):
        """Verify workers __main__ imports compiler_worker and monitor_worker"""
        import subprocess
        import sys
        from pathlib import Path

        src_dir = str(Path(__file__).parent.parent / "src")
        env = __import__("os").environ.copy()
        env["PYTHONPATH"] = src_dir

        result = subprocess.run(
            [sys.executable, "-c", "from dochris.workers import __main__"],
            capture_output=True,
            text=True,
            timeout=10,
            env=env,
        )
        # The module runs print statements at import time
        assert "Workers import test completed" in result.stdout or result.returncode == 0
