"""补充测试 sanitize_sensitive_words.py main 函数"""

from unittest.mock import patch

import pytest


class TestSanitizeMain:
    """覆盖 main 函数 (lines 220-225)"""

    def test_main_prints_sanitized_filename(self):
        """main 函数打印清洗结果"""
        from dochris.admin.sanitize_sensitive_words import main

        with patch("builtins.print") as mock_print:
            main()

        output = " ".join(str(c) for c in mock_print.call_args_list)
        assert "原始文件名" in output
        assert "清洗后文件名" in output
