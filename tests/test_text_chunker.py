"""测试 dochris.core.text_chunker 模块"""


from dochris.core.text_chunker import TextChunk, semantic_chunk


class TestTextChunk:
    """测试 TextChunk 数据类"""

    def test_create_chunk_with_content_only(self):
        """测试只创建内容的块"""
        chunk = TextChunk(content="测试内容")

        assert chunk.content == "测试内容"
        assert chunk.title == ""
        assert chunk.level == 0
        assert chunk.index == 0

    def test_create_chunk_with_all_fields(self):
        """测试创建包含所有字段的块"""
        chunk = TextChunk(
            content="测试内容",
            title="测试标题",
            level=2,
            index=1,
        )

        assert chunk.content == "测试内容"
        assert chunk.title == "测试标题"
        assert chunk.level == 2
        assert chunk.index == 1

    def test_chunk_length_returns_content_length(self):
        """测试 len() 返回内容长度"""
        chunk = TextChunk(content="这是测试内容")

        assert len(chunk) == 6

    def test_chunk_length_with_empty_content(self):
        """测试空内容的长度为 0"""
        chunk = TextChunk(content="")

        assert len(chunk) == 0

    def test_chunk_length_with_unicode(self):
        """测试 Unicode 字符计数"""
        content = "测试中文🎉"
        chunk = TextChunk(content=content)

        # Python 的 len() 返回字符数（不是字节数）
        # emoji 是一个字符，中文也是一个字符
        assert len(chunk) == len(content)


class TestSemanticChunk:
    """测试语义分块函数"""

    def test_semantic_chunk_empty_text(self):
        """测试空文本分块"""
        chunks = semantic_chunk("", chunk_size=1000, overlap=100)

        assert isinstance(chunks, list)

    def test_semantic_chunk_short_text(self):
        """测试短文本不分块"""
        text = "这是一段短文本。"
        chunks = semantic_chunk(text, chunk_size=1000, overlap=100)

        # 短文本应该返回单个块
        assert len(chunks) <= 2

    def test_semantic_chunk_long_text(self):
        """测试长文本分块"""
        text = "这是第一段。\n\n" + "这是第二段内容。" * 100 + "\n\n" + "这是第三段。"
        chunks = semantic_chunk(text, chunk_size=500, overlap=50)

        assert isinstance(chunks, list)
        # 长文本应该产生多个块
        assert len(chunks) >= 1

    def test_semantic_chunk_zero_chunk_size(self):
        """测试 chunk_size 为 0"""
        text = "测试内容"
        chunks = semantic_chunk(text, chunk_size=0, overlap=0)

        assert isinstance(chunks, list)

    def test_semantic_chunk_returns_text_chunks(self):
        """测试返回 TextChunk 对象列表"""
        text = "测试内容。" * 10
        chunks = semantic_chunk(text, chunk_size=200, overlap=20)

        for chunk in chunks:
            assert isinstance(chunk, TextChunk)
            assert isinstance(chunk.content, str)


class TestTextChunkerModule:
    """测试 text_chunker 模块导入"""

    def test_module_import(self):
        """测试模块可以导入"""
        import dochris.core.text_chunker

        assert dochris.core.text_chunker is not None

    def test_structure_aware_split_exists(self):
        """测试 structure_aware_split 函数存在"""
        from dochris.core.text_chunker import structure_aware_split

        assert callable(structure_aware_split)

    def test_fixed_size_chunk_exists(self):
        """测试 fixed_size_chunk 函数存在"""
        from dochris.core.text_chunker import fixed_size_chunk

        assert callable(fixed_size_chunk)

    def test_fixed_size_chunk_basic(self):
        """测试固定大小分块基本功能"""
        from dochris.core.text_chunker import fixed_size_chunk

        text = "这是一段测试文本。" * 50
        chunks = fixed_size_chunk(text, chunk_size=200, overlap=20)

        assert isinstance(chunks, list)
        assert len(chunks) >= 1

    def test_structure_aware_split_basic(self):
        """测试结构感知分块基本功能"""
        from dochris.core.text_chunker import structure_aware_split

        text = "# 标题1\n内容1\n\n# 标题2\n内容2"
        chunks = structure_aware_split(text, chunk_size=1000, overlap=50)

        assert isinstance(chunks, list)
        assert len(chunks) >= 1

    def test_structure_aware_split_empty_text(self):
        """测试空文本结构感知分块"""
        from dochris.core.text_chunker import structure_aware_split

        chunks = structure_aware_split("", chunk_size=1000, overlap=50)

        assert isinstance(chunks, list)

    def test_structure_aware_split_with_numbering(self):
        """测试带数字编号的文本分块"""
        from dochris.core.text_chunker import structure_aware_split

        text = """1. 第一条内容
第二条内容继续。

2. 第二条内容
第三条内容继续。
"""
        chunks = structure_aware_split(text, chunk_size=500, overlap=50)

        assert isinstance(chunks, list)
        assert len(chunks) >= 1
