#!/usr/bin/env python3
"""
测试 parsers/ 下的解析器
"""

import sys
import tempfile
import unittest
from pathlib import Path

# 添加 scripts 目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))


class TestPDFParser(unittest.TestCase):
    """测试 PDF 解析器"""

    def test_parse_with_markitdown_mock(self):
        """测试 markitdown 解析（mock）"""
        from dochris.parsers.pdf_parser import parse_with_markitdown

        # 测试不存在的文件
        result = parse_with_markitdown(Path("/nonexistent/file.pdf"))
        # 应该返回 None 或抛出异常
        self.assertIsNone(result)

    def test_parse_pdf_function_exists(self):
        """测试 parse_pdf 函数存在"""
        from dochris.parsers.pdf_parser import parse_pdf

        # 函数应该存在
        self.assertTrue(callable(parse_pdf))


class TestDocumentParser(unittest.TestCase):
    """测试文档解析器"""

    def test_detect_document_file(self):
        """测试文档文件检测"""
        from dochris.parsers.doc_parser import detect_document_file

        # 测试不同扩展名 - 基于实际实现调整
        # doc_parser 检测特定的文档类型
        self.assertTrue(detect_document_file(Path("test.txt")))
        # 其他扩展名可能返回 False，取决于实现

    def test_detect_code_file(self):
        """测试代码文件检测"""
        from dochris.parsers.code_parser import detect_code_file

        # 测试代码文件
        self.assertTrue(detect_code_file(Path("test.py")))
        self.assertTrue(detect_code_file(Path("test.js")))
        self.assertFalse(detect_code_file(Path("test.pdf")))


class TestParserExtraction(unittest.TestCase):
    """测试提取功能"""

    def test_extract_from_code(self):
        """测试代码提取"""
        from dochris.parsers.code_parser import extract_from_code

        # 创建测试文件
        temp_file = tempfile.NamedTemporaryFile(suffix=".py", delete=False)
        try:
            temp_file.write(b"""
def hello_world():
    print("Hello, World!")

class MyClass:
    def method(self):
        pass
""")
            temp_file.close()

            result = extract_from_code(Path(temp_file.name))
            self.assertIsNotNone(result)
            self.assertIn("language", result)

        finally:
            Path(temp_file.name).unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
