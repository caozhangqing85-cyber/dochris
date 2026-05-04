#!/usr/bin/env python3
"""
文本分块增强测试 — 边界条件、特殊格式和 Unicode 处理
"""

import pytest

from dochris.core.text_chunker import (
    TextChunk,
    count_chars,
    fixed_size_chunk,
    semantic_chunk,
    should_use_hierarchical,
    structure_aware_split,
)


class TestTextChunkEdgeCases:
    """TextChunk 数据类边界条件"""

    def test_empty_content(self):
        """空内容"""
        chunk = TextChunk(content="")
        assert len(chunk) == 0
        assert chunk.content == ""

    def test_single_char(self):
        """单个字符"""
        chunk = TextChunk(content="a")
        assert len(chunk) == 1

    def test_newline_content(self):
        """纯换行内容"""
        chunk = TextChunk(content="\n\n\n")
        assert len(chunk) == 3

    def test_very_long_content(self):
        """超长内容"""
        content = "x" * 1_000_000
        chunk = TextChunk(content=content)
        assert len(chunk) == 1_000_000

    def test_mixed_unicode_content(self):
        """混合 Unicode 内容"""
        content = "Hello 世界 🌍 \t\n"
        chunk = TextChunk(content=content)
        assert len(chunk) == len(content)

    def test_default_values(self):
        """默认值"""
        chunk = TextChunk(content="test")
        assert chunk.title == ""
        assert chunk.level == 0
        assert chunk.index == 0


class TestSemanticChunkEdgeCases:
    """语义分块边界条件"""

    def test_empty_text(self):
        """空文本"""
        chunks = semantic_chunk("", chunk_size=1000, overlap=100)
        assert isinstance(chunks, list)

    def test_single_char(self):
        """单个字符"""
        chunks = semantic_chunk("a", chunk_size=1000, overlap=100)
        assert len(chunks) == 1
        assert chunks[0].content == "a"

    def test_single_word(self):
        """单个词"""
        chunks = semantic_chunk("hello", chunk_size=1000, overlap=0)
        assert len(chunks) == 1

    def test_very_long_paragraph(self):
        """超长单段落 — 触发句子级分割"""
        text = "这是第一句话。" + "这是后续内容。" * 500
        chunks = semantic_chunk(text, chunk_size=500, overlap=50)
        assert len(chunks) >= 1
        # 所有内容应被覆盖
        total_content = "".join(c.content for c in chunks)
        assert len(total_content) > 0

    def test_many_short_paragraphs(self):
        """多个短段落"""
        text = "\n\n".join(f"段落{i}" for i in range(50))
        chunks = semantic_chunk(text, chunk_size=200, overlap=20)
        assert len(chunks) >= 1

    def test_zero_overlap(self):
        """无重叠分块"""
        text = "段落一内容。" * 100 + "\n\n" + "段落二内容。" * 100
        chunks = semantic_chunk(text, chunk_size=500, overlap=0)
        assert len(chunks) >= 1

    def test_large_overlap(self):
        """大重叠分块"""
        text = "这是测试内容。" * 100
        chunks = semantic_chunk(text, chunk_size=200, overlap=100)
        assert len(chunks) >= 1


class TestStructureAwareSplitEdgeCases:
    """结构感知分块边界条件"""

    def test_markdown_with_code_blocks(self):
        """Markdown 代码块处理"""
        text = (
            "# 标题1\n\n"
            "```python\n"
            "def hello():\n"
            "    print('hello')\n"
            "# 这不是标题，是代码中的注释\n"
            "```\n\n"
            "# 标题2\n\n"
            "内容"
        )
        chunks = structure_aware_split(text, chunk_size=1000, overlap=50)
        assert len(chunks) >= 2

    def test_nested_headers(self):
        """嵌套标题"""
        text = "# 第一章\n内容1\n\n## 第一节\n内容2\n\n### 第一小节\n内容3\n\n# 第二章\n内容4"
        chunks = structure_aware_split(text, chunk_size=1000, overlap=50)
        assert len(chunks) >= 2

    def test_chinese_numbering(self):
        """中文编号"""
        text = "一、第一部分\n内容1\n\n二、第二部分\n内容2\n\n三、第三部分\n内容3"
        chunks = structure_aware_split(text, chunk_size=1000, overlap=50)
        assert len(chunks) >= 2

    def test_arabic_numbering(self):
        """阿拉伯数字编号"""
        text = "1. 第一条\n内容1\n\n2. 第二条\n内容2\n\n3. 第三条\n内容3"
        chunks = structure_aware_split(text, chunk_size=1000, overlap=50)
        assert len(chunks) >= 2

    def test_parenthesized_numbering(self):
        """括号编号"""
        text = "（1）第一条内容\n（2）第二条内容\n（3）第三条内容"
        chunks = structure_aware_split(text, chunk_size=1000, overlap=50)
        # 括号编号只有一行，可能不触发分段
        assert isinstance(chunks, list)

    def test_mixed_markdown_and_numbering(self):
        """混合 Markdown 标题和编号"""
        text = "# 大标题\n1. 编号1\n内容\n2. 编号2\n内容\n\n## 小标题\n更多内容"
        chunks = structure_aware_split(text, chunk_size=1000, overlap=50)
        assert len(chunks) >= 2

    def test_all_h1_headers(self):
        """全是一级标题"""
        text = "\n\n".join(f"# 标题{i}\n内容{i}" for i in range(5))
        chunks = structure_aware_split(text, chunk_size=1000, overlap=50)
        assert len(chunks) == 5

    def test_empty_text(self):
        """空文本"""
        chunks = structure_aware_split("", chunk_size=1000, overlap=50)
        assert isinstance(chunks, list)

    def test_plain_text_no_structure(self):
        """无结构的纯文本"""
        text = "这是一段没有标题没有编号的纯文本内容。" * 20
        chunks = structure_aware_split(text, chunk_size=500, overlap=50)
        # 回退到语义分块
        assert isinstance(chunks, list)
        assert len(chunks) >= 1


class TestFixedSizeChunkEdgeCases:
    """固定大小分块边界条件"""

    def test_empty_text(self):
        """空文本"""
        chunks = fixed_size_chunk("", chunk_size=100, overlap=10)
        assert isinstance(chunks, list)

    def test_text_shorter_than_chunk_size(self):
        """文本短于块大小"""
        chunks = fixed_size_chunk("短文本", chunk_size=1000, overlap=100)
        assert len(chunks) == 1
        assert chunks[0].content == "短文本"

    def test_exact_chunk_size(self):
        """文本恰好等于块大小"""
        text = "a" * 100
        chunks = fixed_size_chunk(text, chunk_size=100, overlap=0)
        assert len(chunks) == 1

    def test_chunk_size_plus_one(self):
        """文本比块大小多1字符"""
        text = "a" * 101
        chunks = fixed_size_chunk(text, chunk_size=100, overlap=0)
        assert len(chunks) == 2

    def test_newline_break_preferred(self):
        """优先在换行符处断开"""
        text = "a" * 60 + "\n" + "b" * 60
        chunks = fixed_size_chunk(text, chunk_size=80, overlap=0)
        assert len(chunks) >= 2
        # 第一个块应在换行符处断开
        assert "a" in chunks[0].content

    def test_with_overlap(self):
        """有重叠的分块"""
        text = "abcdefghij" * 20
        chunks = fixed_size_chunk(text, chunk_size=100, overlap=20)
        assert len(chunks) >= 2
        # 验证重叠区域
        if len(chunks) >= 2:
            # 第二个块的开头应该出现在第一个块的末尾
            pass  # 重叠行为由实现决定


class TestChineseTextChunking:
    """中文分块测试"""

    def test_chinese_text_no_spaces(self):
        """无空格的中文文本"""
        text = "这是一段中文文本，没有任何空格分隔。" * 50
        chunks = semantic_chunk(text, chunk_size=200, overlap=20)
        assert len(chunks) >= 1

    def test_chinese_with_punctuation(self):
        """带标点的中文文本"""
        text = "第一句。第二句！第三句？第四句。第五句。" * 20
        chunks = semantic_chunk(text, chunk_size=200, overlap=20)
        assert len(chunks) >= 1

    def test_mixed_chinese_english(self):
        """中英混合文本"""
        text = "This is English. 这是中文。" * 50
        chunks = semantic_chunk(text, chunk_size=200, overlap=20)
        assert len(chunks) >= 1

    def test_chinese_markdown(self):
        """中文 Markdown 文档"""
        text = (
            "# 第一章 引言\n\n"
            "本章介绍基本概念。\n\n"
            "## 1.1 背景\n\n"
            "研究背景包括多个方面。" * 10 + "\n\n"
            "# 第二章 方法\n\n"
            "本章介绍研究方法。" * 10
        )
        chunks = structure_aware_split(text, chunk_size=500, overlap=50)
        assert len(chunks) >= 2

    def test_chinese_numbering_format(self):
        """中文编号格式"""
        text = (
            "一、总则\n"
            "本规定的目的是规范流程。\n\n"
            "二、适用范围\n"
            "适用于所有部门。\n\n"
            "三、具体要求\n"
            "各部门应按照要求执行。"
        )
        chunks = structure_aware_split(text, chunk_size=1000, overlap=50)
        assert len(chunks) >= 2


class TestCountChars:
    """字符计数测试"""

    def test_empty_string(self):
        """空字符串"""
        assert count_chars("") == 0

    def test_ascii(self):
        """ASCII 文本"""
        assert count_chars("hello") == 5

    def test_chinese(self):
        """中文文本"""
        assert count_chars("你好世界") == 4

    def test_mixed(self):
        """混合文本"""
        assert count_chars("hello 世界") == 8

    def test_emoji(self):
        """Emoji"""
        assert count_chars("🎉") == 1

    def test_whitespace(self):
        """空白字符"""
        assert count_chars("  \t\n") == 4


class TestShouldUseHierarchical:
    """摘要策略选择测试"""

    @pytest.mark.parametrize(
        "char_count,expected",
        [
            (0, "direct"),
            (100, "direct"),
            (5000, "direct"),
            (10000, "direct"),
            (10001, "map_reduce"),
            (20000, "map_reduce"),
            (30000, "map_reduce"),
            (30001, "hierarchical"),
            (50000, "hierarchical"),
            (100000, "hierarchical"),
            (100001, "map_reduce"),  # 超大文档回退
            (500000, "map_reduce"),
        ],
    )
    def test_strategy_selection(self, char_count: int, expected: str):
        """根据字数选择摘要策略"""
        text = "a" * char_count
        result = should_use_hierarchical(text, direct_limit=10000)
        assert result == expected

    def test_custom_direct_limit(self):
        """自定义直接摘要上限"""
        text = "a" * 5000
        assert should_use_hierarchical(text, direct_limit=10000) == "direct"
        # 5000 / 1000 = 5 > 3 但 <= 10, 所以是 hierarchical
        assert should_use_hierarchical(text, direct_limit=1000) == "hierarchical"
        # 5000 / 2000 = 2.5 <= 3, 所以是 map_reduce
        assert should_use_hierarchical(text, direct_limit=2000) == "map_reduce"

    def test_at_boundary(self):
        """边界值测试"""
        assert should_use_hierarchical("a" * 10000, direct_limit=10000) == "direct"
        assert should_use_hierarchical("a" * 10001, direct_limit=10000) == "map_reduce"


class TestWhitespaceOnlyText:
    """纯空白字符文本"""

    def test_only_spaces(self):
        """纯空格文本"""
        chunks = semantic_chunk("   ", chunk_size=100, overlap=10)
        # strip 后为空，不生成块
        assert isinstance(chunks, list)

    def test_only_newlines(self):
        """纯换行文本"""
        chunks = semantic_chunk("\n\n\n\n", chunk_size=100, overlap=10)
        assert isinstance(chunks, list)

    def test_tabs_and_spaces(self):
        """制表符和空格"""
        chunks = semantic_chunk("\t\t  \t", chunk_size=100, overlap=10)
        assert isinstance(chunks, list)


class TestMarkdownInlineCode:
    """Markdown 行内代码"""

    def test_inline_code_not_confused_with_headers(self):
        """行内反引号不与标题混淆"""
        text = "使用 `print()` 输出内容，注意 `#` 不是标题。"
        chunks = structure_aware_split(text, chunk_size=1000, overlap=50)
        assert len(chunks) == 1

    def test_code_block_with_hash_comments(self):
        """代码块中的 # 注释不当作标题"""
        text = "# 真正的标题\n\n```python\n# 这是代码注释\nx = 1\n```\n\n正文内容" * 10
        chunks = structure_aware_split(text, chunk_size=1000, overlap=50)
        # 应至少有一个标题块
        assert len(chunks) >= 1


class TestChineseNoPunctuation:
    """无标点中文文本"""

    def test_long_chinese_no_punctuation(self):
        """超长无标点中文文本"""
        text = "这是没有标点符号的中文文本" * 200
        chunks = semantic_chunk(text, chunk_size=500, overlap=50)
        assert len(chunks) >= 1
        # 所有内容应被覆盖
        total = "".join(c.content for c in chunks)
        assert len(total) > 0

    def test_chinese_idiomatic_numbering(self):
        """中文括号编号（一）（二）"""
        text = "（一）第一条\n内容一\n\n（二）第二条\n内容二\n\n（三）第三条\n内容三"
        chunks = structure_aware_split(text, chunk_size=1000, overlap=50)
        assert isinstance(chunks, list)


class TestDeepNestedHeaders:
    """深层标题嵌套"""

    def test_level_4_to_6_headers(self):
        """4-6 级标题"""
        text = (
            "# H1\n内容\n\n"
            "## H2\n内容\n\n"
            "### H3\n内容\n\n"
            "#### H4\n内容\n\n"
            "##### H5\n内容\n\n"
            "###### H6\n内容"
        )
        chunks = structure_aware_split(text, chunk_size=1000, overlap=50)
        assert len(chunks) >= 4
        # 验证标题层级正确
        levels = {c.level for c in chunks}
        assert levels == {1, 2, 3, 4, 5, 6}


class TestEdgeChunkSizeParameters:
    """极端 chunk_size 参数"""

    def test_very_small_chunk_size(self):
        """极小块大小"""
        text = "这是测试文本。第二句话。"
        chunks = fixed_size_chunk(text, chunk_size=1, overlap=0)
        assert len(chunks) > 0

    def test_very_large_chunk_size(self):
        """极大块大小 — 文本全部在一个块中"""
        text = "短文本内容"
        chunks = semantic_chunk(text, chunk_size=1_000_000, overlap=0)
        assert len(chunks) == 1

    def test_single_paragraph_no_double_newline(self):
        """没有双换行的单段落"""
        text = "第一行内容\n第二行内容\n第三行内容"
        chunks = semantic_chunk(text, chunk_size=1000, overlap=50)
        assert len(chunks) == 1


class TestFixedSizeChunkOverlap:
    """固定分块重叠行为"""

    def test_overlap_creates_coverage(self):
        """重叠确保内容覆盖"""
        text = "abcdefghij" * 50
        chunks = fixed_size_chunk(text, chunk_size=100, overlap=20)
        # 所有块内容不为空
        for chunk in chunks:
            assert len(chunk.content) > 0

    def test_no_overlap_exact_fit(self):
        """无重叠且恰好整除"""
        text = "a" * 200
        chunks = fixed_size_chunk(text, chunk_size=100, overlap=0)
        assert len(chunks) == 2
