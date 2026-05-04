"""测试 admin/index_knowledge.py — 向量索引脚本

注意: index_knowledge.py 在模块级初始化 ChromaDB 和 embedding 模型，
所以必须在 import 之前 mock 掉 chromadb 和 chromadb.utils.embedding_functions。
"""

import logging
import sys
from unittest.mock import MagicMock, patch

import pytest


# ── 在 import index_knowledge 之前 mock 掉 chromadb 依赖 ──
@pytest.fixture(autouse=True, scope="module")
def _mock_chromadb():
    """mock 掉 chromadb 和 embedding_functions 模块级初始化"""
    mock_chromadb = MagicMock()
    mock_client = MagicMock()
    mock_collection = MagicMock()
    mock_client.get_or_create_collection.return_value = mock_collection
    mock_chromadb.PersistentClient.return_value = mock_client

    MagicMock()
    mock_chromadb.utils = MagicMock()
    mock_chromadb.utils.embedding_functions = MagicMock()
    mock_chromadb.utils.embedding_functions.SentenceTransformerEmbeddingFunction.return_value = (
        MagicMock()
    )

    with patch.dict(
        sys.modules,
        {
            "chromadb": mock_chromadb,
            "chromadb.utils": mock_chromadb.utils,
            "chromadb.utils.embedding_functions": mock_chromadb.utils.embedding_functions,
        },
    ):
        yield mock_collection


class TestCleanText:
    """测试 clean_text 函数"""

    def test_empty_string(self):
        from dochris.admin.index_knowledge import clean_text

        assert clean_text("") == ""

    def test_removes_extra_newlines(self):
        from dochris.admin.index_knowledge import clean_text

        result = clean_text("hello\n\n\nworld")
        assert result == "hello\nworld"

    def test_removes_extra_spaces(self):
        from dochris.admin.index_knowledge import clean_text

        result = clean_text("hello   world")
        assert result == "hello world"

    def test_strips_whitespace(self):
        from dochris.admin.index_knowledge import clean_text

        result = clean_text("  hello  ")
        assert result == "hello"


class TestTruncateText:
    """测试 truncate_text 函数"""

    def test_short_text_unchanged(self):
        from dochris.admin.index_knowledge import truncate_text

        assert truncate_text("short", 100) == "short"

    def test_long_text_truncated(self):
        from dochris.admin.index_knowledge import truncate_text

        text = "a" * 5000
        result = truncate_text(text, 4000)
        assert len(result) == 4003  # 4000 + "..."
        assert result.endswith("...")


class TestExtractMarkdownSummary:
    """测试 extract_markdown_summary 函数"""

    def test_extracts_summary(self, tmp_path):
        from dochris.admin.index_knowledge import extract_markdown_summary

        md_file = tmp_path / "test.md"
        md_file.write_text(
            "# Title\n\nSome content\n\n## Section 1\n\nContent 1\n\n## Section 2\n\nContent 2\n",
            encoding="utf-8",
        )

        result = extract_markdown_summary(md_file)
        assert "Title" in result
        assert "Section 1" in result
        assert "Section 2" in result


class TestIndexFile:
    """测试 index_file 函数"""

    def test_index_nonexistent_file(self, _mock_chromadb, caplog):
        """不存在的文件直接返回"""
        from dochris.admin.index_knowledge import index_file

        with caplog.at_level(logging.WARNING, logger="dochris.admin.index_knowledge"):
            index_file("/nonexistent/file.md", "obsidian")

        _mock_chromadb.add.assert_not_called()

    def test_index_pdf_skipped(self, _mock_chromadb, tmp_path, caplog):
        """PDF 文件被跳过"""
        from dochris.admin.index_knowledge import index_file

        pdf = tmp_path / "test.pdf"
        pdf.write_bytes(b"%PDF")

        with caplog.at_level(logging.INFO, logger="dochris.admin.index_knowledge"):
            index_file(pdf, "pdf")

        _mock_chromadb.add.assert_not_called()

    def test_index_non_md_non_pdf_skipped(self, _mock_chromadb, tmp_path, caplog):
        """非 md 非 pdf 的 obsidian 文件被跳过"""
        from dochris.admin.index_knowledge import index_file

        txt = tmp_path / "test.txt"
        txt.write_text("hello", encoding="utf-8")

        with caplog.at_level(logging.INFO, logger="dochris.admin.index_knowledge"):
            index_file(txt, "obsidian")

        _mock_chromadb.add.assert_not_called()

    def test_index_md_file_success(self, _mock_chromadb, tmp_path, caplog):
        """成功索引 markdown 文件"""
        from dochris.admin.index_knowledge import index_file

        md = tmp_path / "test.md"
        md.write_text("# Test Title\n\nContent here", encoding="utf-8")

        with caplog.at_level(logging.INFO, logger="dochris.admin.index_knowledge"):
            with patch("dochris.admin.index_knowledge.get_settings") as mock_s:
                mock_s.return_value = MagicMock(obsidian_vaults=[], source_path=None)
                with patch("dochris.admin.index_knowledge.get_workspace", return_value=tmp_path):
                    index_file(md, "obsidian")

        _mock_chromadb.add.assert_called_once()
        call_kwargs = _mock_chromadb.add.call_args
        assert call_kwargs[1]["metadatas"][0]["type"] == "markdown"


class TestMainFunction:
    """测试 main 函数"""

    def test_main_no_args_exits(self, _mock_chromadb):
        """无参数时退出"""
        from dochris.admin.index_knowledge import main

        with patch("sys.argv", ["index_knowledge.py"]):
            with pytest.raises(SystemExit):
                main()

    def test_main_index_priority(self, _mock_chromadb):
        """index-priority 命令"""
        from dochris.admin.index_knowledge import main

        with patch("dochris.admin.index_knowledge.index_obsidian_priority") as mock_p:
            with patch("dochris.admin.index_knowledge.show_stats") as mock_s:
                with patch("sys.argv", ["index_knowledge.py", "index-priority"]):
                    main()

        mock_p.assert_called_once()
        mock_s.assert_called_once()

    def test_main_index_all(self, _mock_chromadb):
        """index-all 命令"""
        from dochris.admin.index_knowledge import main

        with patch("dochris.admin.index_knowledge.index_obsidian_all") as mock_a:
            with patch("dochris.admin.index_knowledge.show_stats") as mock_s:
                with patch("sys.argv", ["index_knowledge.py", "index-all"]):
                    main()

        mock_a.assert_called_once_with(limit=50)
        mock_s.assert_called_once()

    def test_main_stats(self, _mock_chromadb):
        """stats 命令"""
        from dochris.admin.index_knowledge import main

        with patch("dochris.admin.index_knowledge.show_stats") as mock_s:
            with patch("sys.argv", ["index_knowledge.py", "stats"]):
                main()

        mock_s.assert_called_once()

    def test_main_unknown_command_exits(self, _mock_chromadb):
        """未知命令退出"""
        from dochris.admin.index_knowledge import main

        with patch("sys.argv", ["index_knowledge.py", "unknown"]):
            with pytest.raises(SystemExit):
                main()

    def test_main_search_no_query_exits(self, _mock_chromadb):
        """search 缺少查询词退出"""
        from dochris.admin.index_knowledge import main

        with patch("sys.argv", ["index_knowledge.py", "search"]):
            with pytest.raises(SystemExit):
                main()

    def test_main_search_with_query(self, _mock_chromadb):
        """search 命令传递查询词"""
        from dochris.admin.index_knowledge import main

        with patch("dochris.admin.index_knowledge.search_knowledge") as mock_search:
            with patch("sys.argv", ["index_knowledge.py", "search", "test query"]):
                main()

        mock_search.assert_called_once_with("test query")


class TestIndexObsidianPriority:
    """测试 index_obsidian_priority 函数"""

    def test_no_vault_configured(self, _mock_chromadb, caplog):
        """没有配置 Obsidian vault 时打印警告"""
        from dochris.admin.index_knowledge import index_obsidian_priority

        with caplog.at_level(logging.WARNING, logger="dochris.admin.index_knowledge"):
            with patch("dochris.admin.index_knowledge.get_settings") as mock_s:
                mock_s.return_value = MagicMock(obsidian_vaults=[])
                index_obsidian_priority()

        assert "未配置" in caplog.text

    def test_with_vault_and_files(self, _mock_chromadb, tmp_path, caplog):
        """有 vault 配置时索引优先文件"""
        from dochris.admin.index_knowledge import index_obsidian_priority

        vault = tmp_path / "vault"
        vault.mkdir()
        # 创建一些优先文件
        (vault / "职业规划").mkdir()
        (vault / "职业规划" / "AI学习复利系统SOP-最终版.md").write_text(
            "# AI学习\n内容", encoding="utf-8"
        )

        with caplog.at_level(logging.INFO, logger="dochris.admin.index_knowledge"):
            with patch("dochris.admin.index_knowledge.get_settings") as mock_s:
                mock_s.return_value = MagicMock(obsidian_vaults=[vault])
                with patch("dochris.admin.index_knowledge.index_file") as mock_index:
                    index_obsidian_priority()

        mock_index.assert_called()


class TestIndexObsidianAll:
    """测试 index_obsidian_all 函数"""

    def test_no_vault_configured(self, _mock_chromadb, caplog):
        """没有配置 Obsidian vault 时打印警告"""
        from dochris.admin.index_knowledge import index_obsidian_all

        with caplog.at_level(logging.WARNING, logger="dochris.admin.index_knowledge"):
            with patch("dochris.admin.index_knowledge.get_settings") as mock_s:
                mock_s.return_value = MagicMock(obsidian_vaults=[])
                index_obsidian_all()

        assert "未配置" in caplog.text

    def test_with_vault_files(self, _mock_chromadb, tmp_path, caplog):
        """有 vault 文件时索引"""
        from dochris.admin.index_knowledge import index_obsidian_all

        vault = tmp_path / "vault"
        vault.mkdir()
        (vault / "test1.md").write_text("# T1", encoding="utf-8")
        (vault / "test2.md").write_text("# T2", encoding="utf-8")

        with caplog.at_level(logging.INFO, logger="dochris.admin.index_knowledge"):
            with patch("dochris.admin.index_knowledge.get_settings") as mock_s:
                mock_s.return_value = MagicMock(obsidian_vaults=[vault])
                with patch("dochris.admin.index_knowledge.index_file") as mock_index:
                    index_obsidian_all(limit=10)

        assert mock_index.call_count == 2


class TestSearchKnowledge:
    """测试 search_knowledge 函数"""

    def test_search_no_results(self, _mock_chromadb, caplog):
        """搜索无结果"""
        from dochris.admin.index_knowledge import search_knowledge

        _mock_chromadb.query.return_value = {"documents": [[]], "metadatas": [[]]}

        with caplog.at_level(logging.INFO, logger="dochris.admin.index_knowledge"):
            search_knowledge("test query")

        assert "未找到" in caplog.text

    def test_search_with_results(self, _mock_chromadb, caplog):
        """搜索有结果"""
        from dochris.admin.index_knowledge import search_knowledge

        _mock_chromadb.query.return_value = {
            "documents": [["内容片段"]],
            "metadatas": [
                [{"title": "测试", "path": "/test.md", "type": "markdown", "source": "obsidian"}]
            ],
        }

        with caplog.at_level(logging.INFO, logger="dochris.admin.index_knowledge"):
            search_knowledge("测试")

        assert "测试" in caplog.text


class TestShowStats:
    """测试 show_stats 函数"""

    def test_show_stats(self, _mock_chromadb, caplog):
        """显示统计信息"""
        from dochris.admin.index_knowledge import show_stats

        _mock_chromadb.count.return_value = 10
        _mock_chromadb.get.return_value = {
            "metadatas": [
                {"source": "obsidian"},
                {"source": "pdf"},
                {"source": "obsidian"},
            ]
        }

        with caplog.at_level(logging.INFO, logger="dochris.admin.index_knowledge"):
            show_stats()

        assert "10" in caplog.text


class TestIndexFileWithPathFallback:
    """覆盖 index_file 路径回退分支"""

    def test_index_md_with_obsidian_vault(self, _mock_chromadb, tmp_path, caplog):
        """文件不在 workspace 但在 obsidian_vault 下"""
        from dochris.admin.index_knowledge import index_file

        md = tmp_path / "vault" / "test.md"
        md.parent.mkdir(exist_ok=True)
        md.write_text("# Test Title\n\nContent here", encoding="utf-8")

        vault_path = tmp_path / "vault"

        with caplog.at_level(logging.INFO, logger="dochris.admin.index_knowledge"):
            with patch("dochris.admin.index_knowledge.get_settings") as mock_s:
                mock_s.return_value = MagicMock(
                    obsidian_vaults=[vault_path],
                    source_path=None,
                )
                with patch(
                    "dochris.admin.index_knowledge.get_workspace", return_value=tmp_path / "other"
                ):
                    index_file(md, "obsidian")

        _mock_chromadb.add.assert_called()

    def test_index_md_with_source_path(self, _mock_chromadb, tmp_path, caplog):
        """文件不在 workspace 但在 source_path 下"""
        from dochris.admin.index_knowledge import index_file

        md = tmp_path / "source" / "test.md"
        md.parent.mkdir(exist_ok=True)
        md.write_text("# Test Title\n\nContent here", encoding="utf-8")

        source_path = tmp_path / "source"

        with caplog.at_level(logging.INFO, logger="dochris.admin.index_knowledge"):
            with patch("dochris.admin.index_knowledge.get_settings") as mock_s:
                mock_s.return_value = MagicMock(
                    obsidian_vaults=[],
                    source_path=source_path,
                )
                with patch(
                    "dochris.admin.index_knowledge.get_workspace", return_value=tmp_path / "other"
                ):
                    index_file(md, "obsidian")

        _mock_chromadb.add.assert_called()
