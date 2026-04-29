#!/usr/bin/env python3
"""
测试敏感词清洗
"""

import sys
import unittest
from pathlib import Path

# 添加 scripts 目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))


class TestSanitize(unittest.TestCase):
    """测试敏感词清洗"""

    def test_sanitize_filename(self):
        """测试文件名清洗"""
        from dochris.admin.sanitize_sensitive_words import sanitize_filename

        # 测试敏感词替换
        filename = "男朋友女朋友测试.pdf"
        result = sanitize_filename(filename)
        self.assertNotIn("男朋友", result)
        self.assertNotIn("女朋友", result)

    def test_sanitize_content(self):
        """测试内容清洗"""
        from dochris.admin.sanitize_sensitive_words import sanitize_pdf_content

        content = "这是一个关于男朋友和女朋友的故事"
        result = sanitize_pdf_content(content)
        self.assertNotIn("男朋友", result)

    def test_should_skip_file(self):
        """测试高风险文件跳过"""
        from dochris.admin.sanitize_sensitive_words import should_skip_file

        # 高风险词汇
        should_skip, word = should_skip_file("色情内容.pdf")
        self.assertTrue(should_skip)
        self.assertEqual(word, "色情")

        # 正常文件
        should_skip, word = should_skip_file("正常文档.pdf")
        self.assertFalse(should_skip)

    def test_sanitize_prompt(self):
        """测试 prompt 清洗"""
        from dochris.admin.sanitize_sensitive_words import sanitize_prompt

        prompt = "请分析这个关于暴力的故事"
        result = sanitize_prompt(prompt)
        self.assertNotIn("暴力", result)


if __name__ == "__main__":
    unittest.main()
