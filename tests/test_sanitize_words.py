"""测试 admin/sanitize_sensitive_words.py 模块"""


class TestShouldSkipFile:
    """测试 should_skip_file"""

    def test_high_risk_filename(self):
        from dochris.admin.sanitize_sensitive_words import should_skip_file

        skip, word = should_skip_file("毒品相关内容.pdf")
        assert skip is True
        assert word == "毒品"

    def test_high_risk_case_insensitive(self):
        from dochris.admin.sanitize_sensitive_words import should_skip_file

        # 中文没有大小写，但函数调用 .lower()
        skip, word = should_skip_file("裸露图片.jpg")
        assert skip is True

    def test_safe_filename(self):
        from dochris.admin.sanitize_sensitive_words import should_skip_file

        skip, word = should_skip_file("Python编程指南.pdf")
        assert skip is False
        assert word is None

    def test_all_high_risk_words(self):
        from dochris.admin.sanitize_sensitive_words import HIGH_RISK_WORDS, should_skip_file

        for word in HIGH_RISK_WORDS:
            skip, found = should_skip_file(f"test_{word}_file.txt")
            assert skip is True, f"应跳过包含 '{word}' 的文件"


class TestSanitizeFilename:
    """测试 sanitize_filename"""

    def test_removes_sensitive_words(self):
        from dochris.admin.sanitize_sensitive_words import sanitize_filename

        result = sanitize_filename("男朋友的故事.pdf")
        assert "男朋友" not in result
        assert "男性朋友" in result

    def test_preserves_extension_removal(self):
        from dochris.admin.sanitize_sensitive_words import sanitize_filename

        result = sanitize_filename("测试文件.txt")
        assert ".txt" not in result  # 扩展名被移除

    def test_no_sensitive_words_unchanged(self):
        from dochris.admin.sanitize_sensitive_words import sanitize_filename

        result = sanitize_filename("正常文件名.pdf")
        assert result == "正常文件名"

    def test_multiple_sensitive_words(self):
        from dochris.admin.sanitize_sensitive_words import sanitize_filename

        result = sanitize_filename("老公和老婆的对话.pdf")
        assert "老公" not in result
        assert "老婆" not in result


class TestSanitizePdfContent:
    """测试 sanitize_pdf_content"""

    def test_replaces_sensitive_words(self):
        from dochris.admin.sanitize_sensitive_words import sanitize_pdf_content

        content = "这是一个关于政治的话题"
        result = sanitize_pdf_content(content)
        assert "政治" not in result
        assert "政策" in result

    def test_preserves_clean_content(self):
        from dochris.admin.sanitize_sensitive_words import sanitize_pdf_content

        content = "Python 是一门优秀的编程语言"
        result = sanitize_pdf_content(content)
        assert result == content

    def test_regex_replacements(self):
        from dochris.admin.sanitize_sensitive_words import sanitize_pdf_content

        content = "这段色情暴力内容需要过滤"
        result = sanitize_pdf_content(content)
        assert "色情" not in result
        assert "暴力" not in result


class TestSanitizePrompt:
    """测试 sanitize_prompt"""

    def test_replaces_sensitive_words(self):
        from dochris.admin.sanitize_sensitive_words import sanitize_prompt

        prompt = "分析赌博行业的政治影响"
        result = sanitize_prompt(prompt)
        assert "赌博" not in result
        assert "政治" not in result

    def test_clean_prompt_unchanged(self):
        from dochris.admin.sanitize_sensitive_words import sanitize_prompt

        prompt = "请总结这篇文章的主要内容"
        result = sanitize_prompt(prompt)
        assert result == prompt


class TestSensitiveWordMap:
    """测试敏感词映射数据结构"""

    def test_word_map_is_dict(self):
        from dochris.admin.sanitize_sensitive_words import SENSITIVE_WORD_MAP

        assert isinstance(SENSITIVE_WORD_MAP, dict)

    def test_word_map_not_empty(self):
        from dochris.admin.sanitize_sensitive_words import SENSITIVE_WORD_MAP

        assert len(SENSITIVE_WORD_MAP) > 0

    def test_ordered_list_matches_dict(self):
        from dochris.admin.sanitize_sensitive_words import (
            SENSITIVE_WORD_MAP,
            SENSITIVE_WORDS_ORDERED,
        )

        # 验证字典和有序列表的键一致
        for word, replacement in SENSITIVE_WORDS_ORDERED:
            assert word in SENSITIVE_WORD_MAP
            assert SENSITIVE_WORD_MAP[word] == replacement

    def test_high_risk_words_not_empty(self):
        from dochris.admin.sanitize_sensitive_words import HIGH_RISK_WORDS

        assert len(HIGH_RISK_WORDS) > 0
        for word in HIGH_RISK_WORDS:
            assert isinstance(word, str)
            assert len(word) > 0
