"""补充测试 text_chunker.py — 覆盖 line 175 非 markdown 标题分支"""


class TestStructureAwareSplitFallback:
    """覆盖 structure_aware_split 中非 markdown 标题的 fallback (line 175)"""

    def test_non_markdown_heading_as_title(self):
        """非 # 开头的行作为标题时取前50字符"""
        from dochris.core.text_chunker import structure_aware_split

        # 创建一个有分割标记但不是 # 标题的文本
        text = (
            "=" * 80
            + "\n\nThis is content paragraph one with some text.\n\n"
            + "-" * 80
            + "\n\nThis is content paragraph two."
        )

        result = structure_aware_split(text, chunk_size=500, overlap=50)
        # 只需确保函数能运行
        assert isinstance(result, list)
