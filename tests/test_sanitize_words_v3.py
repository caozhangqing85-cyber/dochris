"""补充测试 sanitize_sensitive_words.py — 覆盖 sanitize_filename/sanitize_pdf_content/sanitize_prompt"""

import pytest


class TestSanitizeFilename:
    """测试 sanitize_filename 函数"""

    def test_no_sensitive_words_unchanged(self):
        from dochris.admin.sanitize_sensitive_words import sanitize_filename

        result = sanitize_filename("普通文件名.txt")
        assert result == "普通文件名"


class TestSanitizePdfContent:
    """测试 sanitize_pdf_content 函数"""

    def test_no_changes_when_clean(self):
        from dochris.admin.sanitize_sensitive_words import sanitize_pdf_content

        content = "这是一段普通文本"
        result = sanitize_pdf_content(content)
        assert result == content


class TestShouldSkipFile:
    """测试 should_skip_file 函数"""

    def test_normal_file_not_skipped(self):
        from dochris.admin.sanitize_sensitive_words import should_skip_file

        result = should_skip_file("普通文件.pdf")
        assert result == (False, None)
