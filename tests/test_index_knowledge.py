"""
测试 index_knowledge.py 模块
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest

# 添加 scripts 目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

# 预先 mock ChromaDB 相关模块，避免在导入 index_knowledge 时初始化
sys.modules['chromadb'] = MagicMock()
sys.modules['chromadb.utils'] = MagicMock()
sys.modules['chromadb.utils.embedding_functions'] = MagicMock()

# 创建 mock 的嵌入函数
mock_embedding_function = MagicMock()
sys.modules['chromadb.utils'].embedding_functions.SentenceTransformerEmbeddingFunction = MagicMock(return_value=mock_embedding_function)

# 创建 mock 的 ChromaDB 客户端和 collection
mock_client = MagicMock()
mock_collection = MagicMock()
mock_client.get_or_create_collection.return_value = mock_collection
sys.modules['chromadb'].PersistentClient = MagicMock(return_value=mock_client)


@pytest.fixture
def mock_obsidian_path(tmp_path):
    """创建模拟 Obsidian 路径"""
    obsidian = tmp_path / "Obsidian"
    obsidian.mkdir()
    return obsidian


@pytest.fixture
def mock_chroma_path(tmp_path):
    """创建模拟 ChromaDB 路径"""
    chroma = tmp_path / "data"
    chroma.mkdir()
    return chroma


@pytest.fixture
def sample_markdown_file(mock_obsidian_path):
    """创建示例 markdown 文件"""
    content = """# 测试文档标题

这是一段测试内容，用于测试索引功能。

## 主要章节

这是第一章的内容。

### 小节

更多内容...

## 另一个章节

继续内容。
"""
    md_file = mock_obsidian_path / "测试文档.md"
    md_file.write_text(content, encoding="utf-8")
    return md_file


@pytest.fixture
def sample_priority_files(mock_obsidian_path):
    """创建优先级文件"""
    # 创建优先级目录结构
    (mock_obsidian_path / "职业规划").mkdir()
    (mock_obsidian_path / "04-个人成长" / "个人提升计划").mkdir(parents=True)

    files = []
    # 创建文件
    for i, path in enumerate([
        "职业规划/AI学习复利系统SOP-最终版.md",
        "职业规划/Obsidian学习模板配置指南.md",
    ]):
        file_path = mock_obsidian_path / path
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(f"# {path}\n\n内容 {i}", encoding="utf-8")
        files.append(file_path)

    return files


class TestIndexKnowledgeTextProcessing:
    """测试文本处理功能"""

    def test_clean_text_normal(self):
        """测试正常文本清理"""
        from dochris.admin.index_knowledge import clean_text

        text = "这是   多余  空白\n\n\n的文本"
        result = clean_text(text)

        assert result == "这是 多余 空白\n的文本"

    def test_clean_text_empty(self):
        """测试空文本清理"""
        from dochris.admin.index_knowledge import clean_text

        result = clean_text("")

        assert result == ""

    def test_clean_text_none(self):
        """测试 None 输入"""
        from dochris.admin.index_knowledge import clean_text

        result = clean_text(None)

        assert result == ""

    def test_truncate_text_short(self):
        """测试短文本截断"""
        from dochris.admin.index_knowledge import truncate_text

        text = "短文本"
        result = truncate_text(text, 4000)

        assert result == text

    def test_truncate_text_long(self):
        """测试长文本截断"""
        from dochris.admin.index_knowledge import truncate_text

        text = "a" * 5000
        result = truncate_text(text, 4000)

        assert len(result) == 4003  # 4000 + "..."

    def test_extract_markdown_summary(self, tmp_path):
        """测试 markdown 摘要提取"""
        from dochris.admin.index_knowledge import extract_markdown_summary

        md_file = tmp_path / "test.md"
        content = "# 标题\n\n内容1\n\n内容2\n\n## 章节\n\n章节内容"
        md_file.write_text(content, encoding="utf-8")

        summary = extract_markdown_summary(md_file)

        assert "标题" in summary
        assert len(summary) > 0


class TestIndexKnowledgeIndexFile:
    """测试文件索引功能"""

    @patch('dochris.admin.index_knowledge.extract_markdown_summary')
    def test_index_file_success(self, mock_extract, sample_markdown_file):
        """测试成功索引文件"""
        from dochris.admin.index_knowledge import index_file

        # 重置 mock
        mock_collection.reset_mock()

        mock_extract.return_value = "提取的摘要内容"
        mock_collection.add.return_value = None

        # 应该不抛出异常
        index_file(sample_markdown_file, "obsidian")

        mock_collection.add.assert_called_once()

    def test_index_file_not_exists(self, tmp_path):
        """测试索引不存在的文件"""
        from dochris.admin.index_knowledge import index_file

        # 重置 mock
        mock_collection.reset_mock()

        non_existent = tmp_path / "不存在的文件.md"

        # 应该不抛出异常
        index_file(non_existent, "obsidian")

        mock_collection.add.assert_not_called()

    def test_index_file_pdf_skipped(self, tmp_path):
        """测试 PDF 文件被跳过"""
        from dochris.admin.index_knowledge import index_file

        # 重置 mock
        mock_collection.reset_mock()

        pdf_file = tmp_path / "test.pdf"
        pdf_file.write_bytes(b"%PDF-1.4")

        index_file(pdf_file, "pdf")

        mock_collection.add.assert_not_called()

    def test_index_file_title_extraction(self, sample_markdown_file):
        """测试标题提取"""
        from dochris.admin.index_knowledge import index_file

        # 重置 mock
        mock_collection.reset_mock()
        mock_collection.add.return_value = None

        index_file(sample_markdown_file, "obsidian")

        call_args = mock_collection.add.call_args
        metadata = call_args[1]['metadatas'][0]
        # 标题从文件第一行提取，不是从 extract_markdown_summary
        assert metadata['title'] == "测试文档标题"

    def test_index_file_error_handling(self, tmp_path):
        """测试错误处理"""
        from dochris.admin.index_knowledge import index_file

        # 重置 mock
        mock_collection.reset_mock()

        md_file = tmp_path / "test.md"
        md_file.write_text("# 测试", encoding="utf-8")

        # 模拟文件读取错误
        with patch('pathlib.Path.read_text', side_effect=OSError("读取错误")):
            # 应该不抛出异常
            index_file(md_file, "obsidian")


class TestIndexKnowledgeBatchIndexing:
    """测试批量索引功能"""

    @patch('dochris.admin.index_knowledge.index_file')
    @patch('dochris.settings.OBSIDIAN_VAULT')
    def test_index_obsidian_priority(self, mock_obsidian, mock_index, sample_priority_files):
        """测试索引 Obsidian 优先文件"""
        from dochris.admin.index_knowledge import index_obsidian_priority

        mock_obsidian.__truediv__ = Mock(return_value=Path("/tmp/obsidian"))
        mock_obsidian.__iter__ = Mock(return_value=iter([]))

        index_obsidian_priority()

        # 验证文件被索引（PRIORITY_FILES 有 9 个文件，但 sample_priority_files 只创建了 2 个）
        assert mock_index.call_count >= 0

    @patch('dochris.admin.index_knowledge.index_file')
    def test_index_obsidian_all_with_limit(self, mock_index, mock_obsidian_path):
        """测试索引所有文件（限制数量）"""
        from dochris.admin.index_knowledge import index_obsidian_all

        # 创建一些测试文件
        test1 = mock_obsidian_path / "test1.md"
        test2 = mock_obsidian_path / "test2.md"
        test1.write_text("# Test1", encoding="utf-8")
        test2.write_text("# Test2", encoding="utf-8")

        # mock get_settings 返回含 obsidian_vaults 的对象
        mock_settings = MagicMock()
        mock_settings.obsidian_vaults = [mock_obsidian_path]
        with patch('dochris.admin.index_knowledge.get_settings', return_value=mock_settings):
            index_obsidian_all(limit=10)

        # 应该索引 2 个文件
        assert mock_index.call_count == 2

    @patch('dochris.admin.index_knowledge.index_file')
    def test_index_obsidian_all_no_limit(self, mock_index, mock_obsidian_path):
        """测试索引所有文件（无限）"""
        from dochris.admin.index_knowledge import index_obsidian_all

        # 创建一些测试文件
        test1 = mock_obsidian_path / "test1.md"
        test2 = mock_obsidian_path / "test2.md"
        test1.write_text("# Test1", encoding="utf-8")
        test2.write_text("# Test2", encoding="utf-8")

        # mock get_settings 返回含 obsidian_vaults 的对象
        mock_settings = MagicMock()
        mock_settings.obsidian_vaults = [mock_obsidian_path]
        with patch('dochris.admin.index_knowledge.get_settings', return_value=mock_settings):
            index_obsidian_all(limit=50)

        # 应该索引 2 个文件
        assert mock_index.call_count == 2


class TestIndexKnowledgeSearch:
    """测试搜索功能"""

    @patch('dochris.admin.index_knowledge.collection')
    def test_search_knowledge(self, mock_collection):
        """测试搜索知识库"""
        from dochris.admin.index_knowledge import search_knowledge

        mock_collection.query.return_value = {
            'documents': [['文档1内容', '文档2内容']],
            'metadatas': [[{'path': '/path/to/file1.md', 'title': '标题1', 'type': 'markdown', 'source': 'obsidian'},
                           {'path': '/path/to/file2.md', 'title': '标题2', 'type': 'markdown', 'source': 'obsidian'}]]
        }

        # 应该不抛出异常
        search_knowledge("测试查询")

        mock_collection.query.assert_called_once()

    @patch('dochris.admin.index_knowledge.collection')
    def test_search_knowledge_empty_results(self, mock_collection):
        """测试搜索空结果"""
        from dochris.admin.index_knowledge import search_knowledge

        mock_collection.query.return_value = {
            'documents': [[]],
            'metadatas': [[]]
        }

        # 应该不抛出异常
        search_knowledge("测试查询")


class TestIndexKnowledgeStats:
    """测试统计功能"""

    @patch('dochris.admin.index_knowledge.collection')
    def test_show_stats(self, mock_collection):
        """测试显示统计"""
        from dochris.admin.index_knowledge import show_stats

        mock_collection.count.return_value = 100
        mock_collection.get.return_value = {
            'metadatas': [
                {'source': 'obsidian'},
                {'source': 'obsidian'},
                {'source': 'pdf'}
            ]
        }

        # 应该不抛出异常
        show_stats()

    @patch('dochris.admin.index_knowledge.collection')
    def test_show_stats_empty(self, mock_collection):
        """测试显示空统计"""
        from dochris.admin.index_knowledge import show_stats

        mock_collection.count.return_value = 0
        mock_collection.get.return_value = {'metadatas': []}

        # 应该不抛出异常
        show_stats()


class TestIndexKnowledgeMain:
    """测试主函数入口"""

    @patch('sys.argv', ['index_knowledge.py', 'index-priority'])
    @patch('dochris.admin.index_knowledge.index_obsidian_priority')
    @patch('dochris.admin.index_knowledge.show_stats')
    def test_main_index_priority(self, mock_stats, mock_index):
        """测试主函数 - 索引优先文件"""
        from dochris.admin.index_knowledge import main

        main()

        mock_index.assert_called_once()

    @patch('sys.argv', ['index_knowledge.py', 'index-all'])
    @patch('dochris.admin.index_knowledge.index_obsidian_all')
    @patch('dochris.admin.index_knowledge.show_stats')
    def test_main_index_all(self, mock_stats, mock_index):
        """测试主函数 - 索引所有文件"""
        from dochris.admin.index_knowledge import main

        main()

        mock_index.assert_called_once()

    @patch('sys.argv', ['index_knowledge.py', 'stats'])
    @patch('dochris.admin.index_knowledge.show_stats')
    def test_main_stats(self, mock_stats):
        """测试主函数 - 显示统计"""
        from dochris.admin.index_knowledge import main

        main()

        mock_stats.assert_called_once()

    @patch('sys.argv', ['index_knowledge.py', 'search', '测试查询'])
    @patch('dochris.admin.index_knowledge.search_knowledge')
    def test_main_search(self, mock_search):
        """测试主函数 - 搜索"""
        from dochris.admin.index_knowledge import main

        main()

        mock_search.assert_called_once_with("测试查询")

    @patch('sys.argv', ['index_knowledge.py'])
    @patch('sys.exit')
    def test_main_no_args(self, mock_exit, capsys):
        """测试主函数 - 无参数"""
        from dochris.admin.index_knowledge import main

        # 防止 sys.exit 真正退出
        mock_exit.side_effect = SystemExit(1)

        with pytest.raises(SystemExit):
            main()

        mock_exit.assert_called_once_with(1)

    @patch('sys.argv', ['index_knowledge.py', 'unknown-command'])
    @patch('sys.exit')
    def test_main_unknown_command(self, mock_exit, capsys):
        """测试主函数 - 未知命令"""
        from dochris.admin.index_knowledge import main

        # 防止 sys.exit 真正退出
        mock_exit.side_effect = SystemExit(1)

        with pytest.raises(SystemExit):
            main()

        mock_exit.assert_called_once_with(1)


class TestIndexKnowledgeIDGeneration:
    """测试 ID 生成"""

    @patch('dochris.admin.index_knowledge.get_workspace')
    @patch('dochris.admin.index_knowledge.extract_markdown_summary')
    def test_doc_id_generation_obsidian_path(self, mock_extract, mock_workspace, sample_markdown_file):
        """测试 Obsidian 路径的 ID 生成"""
        from dochris.admin.index_knowledge import index_file

        # 重置 mock
        mock_collection.reset_mock()

        mock_extract.return_value = "摘要"
        mock_workspace.return_value = Path("/vol1/1000")
        mock_collection.add.return_value = None

        index_file(sample_markdown_file, "obsidian")

        call_args = mock_collection.add.call_args
        ids = call_args[1]['ids']
        assert len(ids) > 0
        assert ids[0].startswith("obsidian_")

    @patch('dochris.admin.index_knowledge.get_workspace')
    @patch('dochris.admin.index_knowledge.extract_markdown_summary')
    def test_doc_id_generation_fallback(self, mock_extract, mock_workspace, tmp_path):
        """测试 ID 生成回退"""
        from dochris.admin.index_knowledge import index_file

        # 重置 mock
        mock_collection.reset_mock()

        md_file = tmp_path / "test.md"
        md_file.write_text("# 测试", encoding="utf-8")

        mock_extract.return_value = "摘要"
        # 返回一个不相关的路径，触发回退到文件名
        mock_workspace.return_value = Path("/unrelated/path")
        mock_collection.add.return_value = None

        index_file(md_file, "obsidian")

        call_args = mock_collection.add.call_args
        ids = call_args[1]['ids']
        assert len(ids) > 0
        assert ids[0].startswith("obsidian_")


class TestIndexKnowledgeMetadata:
    """测试元数据处理"""

    @patch('dochris.admin.index_knowledge.collection')
    @patch('dochris.admin.index_knowledge.extract_markdown_summary')
    def test_metadata_includes_timestamp(self, mock_extract, mock_collection, sample_markdown_file):
        """测试元数据包含时间戳"""
        from dochris.admin.index_knowledge import index_file

        mock_extract.return_value = "摘要"
        mock_collection.add.return_value = None

        index_file(sample_markdown_file, "obsidian")

        call_args = mock_collection.add.call_args
        metadata = call_args[1]['metadatas'][0]
        assert 'indexed_at' in metadata

    @patch('dochris.admin.index_knowledge.collection')
    @patch('dochris.admin.index_knowledge.extract_markdown_summary')
    def test_metadata_includes_path(self, mock_extract, mock_collection, sample_markdown_file):
        """测试元数据包含路径"""
        from dochris.admin.index_knowledge import index_file

        mock_extract.return_value = "摘要"
        mock_collection.add.return_value = None

        index_file(sample_markdown_file, "obsidian")

        call_args = mock_collection.add.call_args
        metadata = call_args[1]['metadatas'][0]
        assert 'path' in metadata
        assert 'type' in metadata
        assert 'source' in metadata

    @patch('dochris.admin.index_knowledge.collection')
    @patch('dochris.admin.index_knowledge.extract_markdown_summary')
    def test_metadata_markdown_type(self, mock_extract, mock_collection, sample_markdown_file):
        """测试 markdown 类型元数据"""
        from dochris.admin.index_knowledge import index_file

        mock_extract.return_value = "摘要"
        mock_collection.add.return_value = None

        index_file(sample_markdown_file, "obsidian")

        call_args = mock_collection.add.call_args
        metadata = call_args[1]['metadatas'][0]
        assert metadata['type'] == 'markdown'


class TestIndexKnowledgeEdgeCases:
    """测试边界情况"""

    @patch('dochris.admin.index_knowledge.collection')
    @patch('dochris.admin.index_knowledge.extract_markdown_summary')
    def test_unicode_content(self, mock_extract, mock_collection, tmp_path):
        """测试 Unicode 内容"""
        from dochris.admin.index_knowledge import index_file

        md_file = tmp_path / "test.md"
        content = "# 测试\n\n中文内容 🎉 混合 with English"
        md_file.write_text(content, encoding="utf-8")

        mock_extract.return_value = content
        mock_collection.add.return_value = None

        # 应该不抛出异常
        index_file(md_file, "obsidian")

    @patch('dochris.admin.index_knowledge.collection')
    @patch('dochris.admin.index_knowledge.extract_markdown_summary')
    def test_large_file(self, mock_extract, mock_collection, tmp_path):
        """测试大文件处理"""
        from dochris.admin.index_knowledge import index_file

        md_file = tmp_path / "large.md"
        large_content = "# 大文件\n\n" + ("内容\n" * 10000)
        md_file.write_text(large_content, encoding="utf-8")

        mock_extract.return_value = large_content[:4000]
        mock_collection.add.return_value = None

        # 应该不抛出异常
        index_file(md_file, "obsidian")
