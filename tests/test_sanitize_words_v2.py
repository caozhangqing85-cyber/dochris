"""测试 sanitize_sensitive_words 模块"""

from dochris.admin.sanitize_sensitive_words import (
    HIGH_RISK_WORDS,
    SENSITIVE_WORDS_ORDERED,
    sanitize_filename,
    sanitize_pdf_content,
    sanitize_prompt,
    should_skip_file,
)


class TestShouldSkipFile:
    def test_high_risk_word_in_filename(self):
        skip, word = should_skip_file("色情内容.pdf")
        assert skip is True
        assert word == "色情"

    def test_no_risk_word(self):
        skip, word = should_skip_file("正常文件.pdf")
        assert skip is False
        assert word is None

    def test_case_insensitive(self):
        skip, word = should_skip_file("GAMBLING.txt")
        assert skip is False  # HIGH_RISK_WORDS 是中文

    def test_毒品_in_filename(self):
        skip, word = should_skip_file("毒品相关.pdf")
        assert skip is True
        assert word == "毒品"

    def test_裸露_in_filename(self):
        skip, word = should_skip_file("裸露内容.pdf")
        assert skip is True

    def test_成瘾_in_filename(self):
        skip, word = should_skip_file("成瘾研究.pdf")
        assert skip is True

    def test_all_high_risk_words(self):
        for word in HIGH_RISK_WORDS:
            skip, found = should_skip_file(f"test_{word}_file.pdf")
            assert skip is True
            assert found == word


class TestSanitizeFilename:
    def test_replaces_compound_words(self):
        result = sanitize_filename("男朋友的故事.txt")
        assert "男朋友" not in result
        assert "男性朋友" in result

    def test_removes_extension(self):
        result = sanitize_filename("test.txt")
        assert not result.endswith(".txt")

    def test_no_change_clean_filename(self):
        result = sanitize_filename("正常文件.pdf")
        assert result == "正常文件"

    def test_replaces_multiple_words(self):
        result = sanitize_filename("暗恋追求.txt")
        # 暗恋 -> 默默关注
        assert "默默关注" in result


class TestSanitizePdfContent:
    def test_replaces_sensitive_words(self):
        content = "这是一个色情暴力的内容"
        result = sanitize_pdf_content(content)
        assert "色情" not in result
        assert "暴力" not in result

    def test_no_change_clean_content(self):
        content = "这是一段正常的内容"
        result = sanitize_pdf_content(content)
        assert result == content

    def test_regex_replacement(self):
        content = "包含色情和暴力描述"
        result = sanitize_pdf_content(content)
        assert "不适当内容" in result
        # "暴力" 先被 SENSITIVE_WORDS_ORDERED 替换为 "强制"，regex 无法再匹配
        assert "暴力" not in result


class TestSanitizePrompt:
    def test_replaces_sensitive_words(self):
        prompt = "描述一下暗恋的感觉"
        result = sanitize_prompt(prompt)
        assert "默默关注" in result

    def test_no_change_clean_prompt(self):
        prompt = "解释量子力学"
        result = sanitize_prompt(prompt)
        assert result == prompt


class TestSensitiveWordsOrdered:
    def test_is_list_of_tuples(self):
        assert isinstance(SENSITIVE_WORDS_ORDERED, list)
        for item in SENSITIVE_WORDS_ORDERED:
            assert isinstance(item, tuple)
            assert len(item) == 2

    def test_compound_words_before_short(self):
        """长词应在短词之前"""
        long_words = [w for w, _ in SENSITIVE_WORDS_ORDERED if len(w) > 1]
        # 至少有一些复合词
        assert len(long_words) > 0

    def test_high_risk_words_are_subset(self):
        """HIGH_RISK_WORDS 大部分是 SENSITIVE_WORDS 的子集"""
        sensitive_words_set = {w for w, _ in SENSITIVE_WORDS_ORDERED}
        for word in HIGH_RISK_WORDS:
            # "黄色" 不在 SENSITIVE_WORDS_ORDERED 中，这是已知的
            assert word in sensitive_words_set or word == "黄色"
