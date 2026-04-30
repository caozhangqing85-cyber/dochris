#!/usr/bin/env python3
"""
代码解析器测试 — 覆盖语言检测、提取和边界条件
"""

from pathlib import Path

import pytest

from dochris.parsers.code_parser import (
    _detect_language,
    _extract_docstrings_and_comments,
    detect_code_file,
    extract_from_code,
)


class TestDetectCodeFile:
    """测试代码文件检测"""

    @pytest.mark.parametrize(
        "filename,expected",
        [
            ("test.py", True),
            ("test.js", True),
            ("test.ts", True),
            ("test.java", True),
            ("test.c", True),
            ("test.cpp", True),
            ("test.go", True),
            ("test.rs", True),
            ("test.rb", True),
            ("test.cs", True),
            ("test.kt", True),
            ("test.swift", True),
            ("test.lua", True),
            ("test.zig", True),
            ("test.php", True),
            ("test.m", True),
            ("test.mm", True),
            ("test.txt", False),
            ("test.pdf", False),
            ("test.md", False),
            ("test.html", False),
            ("test.css", False),
            ("test.json", False),
            ("test.yaml", False),
            ("README", False),
            ("Makefile", False),
        ],
    )
    def test_detect_code_file_extensions(self, filename: str, expected: bool):
        """检测各种文件扩展名"""
        result = detect_code_file(Path(filename))
        assert result is expected

    def test_uppercase_extension(self):
        """大写扩展名也能检测"""
        assert detect_code_file(Path("TEST.PY")) is True
        assert detect_code_file(Path("Test.JS")) is True

    def test_no_extension(self):
        """无扩展名返回 False"""
        assert detect_code_file(Path("Makefile")) is False
        assert detect_code_file(Path("README")) is False

    def test_path_with_directory(self):
        """带目录的路径也能正确检测"""
        assert detect_code_file(Path("src/main.py")) is True
        assert detect_code_file(Path("/home/user/project/app.go")) is True


class TestDetectLanguage:
    """测试代码语言检测"""

    @pytest.mark.parametrize(
        "filename,language",
        [
            ("test.py", "python"),
            ("test.js", "javascript"),
            ("test.ts", "typescript"),
            ("test.java", "java"),
            ("test.c", "c"),
            ("test.cpp", "c++"),
            ("test.go", "go"),
            ("test.rs", "rust"),
            ("test.rb", "ruby"),
            ("test.cs", "c#"),
            ("test.kt", "kotlin"),
            ("test.swift", "swift"),
            ("test.lua", "lua"),
            ("test.zig", "zig"),
            ("test.php", "php"),
        ],
    )
    def test_language_detection(self, filename: str, language: str):
        """正确检测文件语言"""
        assert _detect_language(Path(filename)) == language

    def test_unknown_extension(self):
        """未知扩展名返回 unknown"""
        assert _detect_language(Path("test.xyz")) == "unknown"
        assert _detect_language(Path("test.abc")) == "unknown"

    def test_objc_extensions(self):
        """Objective-C 扩展名返回 unknown（不在映射中）"""
        # .m 和 .mm 在 detect_code_file 中支持但不在 _detect_language 映射中
        assert _detect_language(Path("test.m")) == "unknown"
        assert _detect_language(Path("test.mm")) == "unknown"


class TestExtractDocstringsAndComments:
    """测试文档字符串和注释提取"""

    def test_python_comments(self):
        """提取 Python 注释"""
        content = "# 这是注释\ndef foo():\n    # 内部注释\n    pass\n"
        result = _extract_docstrings_and_comments(content, "python")
        assert "# 这是注释" in result
        assert "# 内部注释" in result

    def test_python_docstrings(self):
        """提取 Python 文档字符串"""
        content = 'def foo():\n    """这是文档字符串"""\n    pass\n'
        result = _extract_docstrings_and_comments(content, "python")
        assert "文档字符串" in result

    def test_javascript_comments(self):
        """提取 JavaScript 注释"""
        content = "// 行注释\n/* 块注释 */\nfunction foo() {}\n"
        result = _extract_docstrings_and_comments(content, "javascript")
        assert "// 行注释" in result
        assert "/* 块注释 */" in result

    def test_c_style_comments(self):
        """提取 C 风格注释"""
        content = "// comment\n/* block */\n* star line\n"
        result = _extract_docstrings_and_comments(content, "c")
        assert "// comment" in result
        assert "/* block */" in result

    def test_empty_content(self):
        """空内容返回空字符串"""
        result = _extract_docstrings_and_comments("", "python")
        assert result == ""

    def test_no_comments(self):
        """无注释内容返回空"""
        content = "x = 1\ny = 2\nz = x + y\n"
        result = _extract_docstrings_and_comments(content, "python")
        assert result.strip() == ""

    def test_multiline_docstring(self):
        """多行文档字符串"""
        content = '"""\n多行\n文档字符串\n"""\n'
        result = _extract_docstrings_and_comments(content, "python")
        assert "多行" in result
        assert "文档字符串" in result


class TestExtractFromCode:
    """测试代码提取功能"""

    def test_parse_python_file(self, tmp_path: Path):
        """解析 Python 文件"""
        py_file = tmp_path / "test.py"
        py_file.write_text(
            '"""模块文档"""\n\n'
            "# 注释\n"
            "def hello():\n"
            '    """问候函数"""\n'
            '    print("hello")\n\n'
            "class MyClass:\n"
            "    def method(self):\n"
            "        pass\n",
            encoding="utf-8",
        )

        result = extract_from_code(py_file)

        assert result is not None
        assert result["language"] == "python"
        assert "hello" in result["functions"]
        assert "method" in result["functions"]
        assert "MyClass" in result["classes"]

    def test_parse_javascript_file(self, tmp_path: Path):
        """解析 JavaScript 文件"""
        js_file = tmp_path / "test.js"
        js_file.write_text(
            "// JavaScript 注释\n"
            "function greet() {\n"
            "    console.log('hello');\n"
            "}\n"
            "class Animal {\n"
            "    constructor() {}\n"
            "}\n",
            encoding="utf-8",
        )

        result = extract_from_code(js_file)

        assert result is not None
        assert result["language"] == "javascript"
        # JS function 不匹配 def 正则，所以 functions 为空
        assert isinstance(result["functions"], list)
        assert "Animal" in result["classes"]

    def test_parse_typescript_file(self, tmp_path: Path):
        """解析 TypeScript 文件"""
        ts_file = tmp_path / "app.ts"
        ts_file.write_text(
            "interface User {\n"
            "    name: string;\n"
            "}\n"
            "function getUser(): User {\n"
            "    return { name: 'test' };\n"
            "}\n",
            encoding="utf-8",
        )

        result = extract_from_code(ts_file)

        assert result is not None
        assert result["language"] == "typescript"
        # TS function 不匹配 def 正则
        assert isinstance(result["functions"], list)

    def test_parse_go_file(self, tmp_path: Path):
        """解析 Go 文件"""
        go_file = tmp_path / "main.go"
        go_file.write_text(
            "package main\n\n"
            "// Main function\n"
            "func main() {\n"
            '    fmt.Println("hello")\n'
            "}\n",
            encoding="utf-8",
        )

        result = extract_from_code(go_file)

        assert result is not None
        assert result["language"] == "go"
        # Go 的 def 正则不会匹配 func，所以 functions 列表为空
        assert isinstance(result["functions"], list)

    def test_parse_rust_file(self, tmp_path: Path):
        """解析 Rust 文件"""
        rs_file = tmp_path / "main.rs"
        rs_file.write_text(
            "// Rust comment\n"
            "fn main() {\n"
            '    println!("hello");\n'
            "}\n",
            encoding="utf-8",
        )

        result = extract_from_code(rs_file)

        assert result is not None
        assert result["language"] == "rust"

    def test_file_not_found(self):
        """文件不存在返回 None"""
        result = extract_from_code(Path("/nonexistent/file.py"))
        assert result is None

    def test_empty_file(self, tmp_path: Path):
        """空文件正常处理"""
        py_file = tmp_path / "empty.py"
        py_file.write_text("", encoding="utf-8")

        result = extract_from_code(py_file)

        assert result is not None
        assert result["functions"] == []
        assert result["classes"] == []
        assert result["text"] == ""

    def test_unicode_content(self, tmp_path: Path):
        """包含 Unicode 内容的文件"""
        py_file = tmp_path / "unicode.py"
        py_file.write_text(
            "# 中文注释\n"
            "def 计算总和(a, b):\n"
            "    '''计算两个数的总和'''\n"
            "    return a + b\n",
            encoding="utf-8",
        )

        result = extract_from_code(py_file)

        assert result is not None
        assert "计算总和" in result["functions"]

    def test_large_file(self, tmp_path: Path):
        """大文件正常处理"""
        py_file = tmp_path / "large.py"
        content = "\n".join(f"def func_{i}(): pass" for i in range(100))
        py_file.write_text(content, encoding="utf-8")

        result = extract_from_code(py_file)

        assert result is not None
        assert len(result["functions"]) == 100

    def test_text_field_contains_comments(self, tmp_path: Path):
        """text 字段包含提取的注释和文档字符串"""
        py_file = tmp_path / "documented.py"
        py_file.write_text(
            "# 文件注释\n"
            "def foo():\n"
            "    pass\n",
            encoding="utf-8",
        )

        result = extract_from_code(py_file)

        assert result is not None
        assert "文件注释" in result["text"]


class TestExtractFromCodeEdgeCases:
    """代码提取边界条件"""

    def test_file_with_only_code_no_comments(self, tmp_path: Path):
        """只有代码没有注释"""
        py_file = tmp_path / "nocomments.py"
        py_file.write_text("x = 1\ny = 2\nz = x + y\n", encoding="utf-8")

        result = extract_from_code(py_file)

        assert result is not None
        assert result["text"] == ""

    def test_file_with_read_error(self, tmp_path: Path):
        """读取错误返回 None"""
        # 使用不存在的路径
        result = extract_from_code(Path("/nonexistent/path.py"))
        assert result is None

    def test_nested_classes(self, tmp_path: Path):
        """嵌套类定义"""
        py_file = tmp_path / "nested.py"
        py_file.write_text(
            "class Outer:\n"
            "    class Inner:\n"
            "        pass\n",
            encoding="utf-8",
        )

        result = extract_from_code(py_file)

        assert result is not None
        assert "Outer" in result["classes"]
        assert "Inner" in result["classes"]

    def test_multiple_functions(self, tmp_path: Path):
        """多个函数定义"""
        py_file = tmp_path / "multi.py"
        py_file.write_text(
            "def foo(): pass\n"
            "def bar(): pass\n"
            "def baz(): pass\n",
            encoding="utf-8",
        )

        result = extract_from_code(py_file)

        assert result is not None
        assert set(result["functions"]) == {"foo", "bar", "baz"}


class TestExtractFromCodeMoreLanguages:
    """更多语言类型的代码提取测试"""

    def test_parse_php_file(self, tmp_path: Path):
        """解析 PHP 文件"""
        php_file = tmp_path / "index.php"
        php_file.write_text(
            "<?php\n"
            "// PHP comment\n"
            "function hello() {\n"
            "    echo 'hello';\n"
            "}\n"
            "class User {\n"
            "    public function getName() {}\n"
            "}\n",
            encoding="utf-8",
        )

        result = extract_from_code(php_file)

        assert result is not None
        assert result["language"] == "php"

    def test_parse_ruby_file(self, tmp_path: Path):
        """解析 Ruby 文件"""
        rb_file = tmp_path / "app.rb"
        rb_file.write_text(
            "# Ruby comment\n"
            "def greet\n"
            "  puts 'hello'\n"
            "end\n"
            "class Animal\n"
            "end\n",
            encoding="utf-8",
        )

        result = extract_from_code(rb_file)

        assert result is not None
        assert result["language"] == "ruby"
        assert "greet" in result["functions"]
        assert "Animal" in result["classes"]

    def test_parse_kotlin_file(self, tmp_path: Path):
        """解析 Kotlin 文件"""
        kt_file = tmp_path / "Main.kt"
        kt_file.write_text(
            "// Kotlin comment\n"
            "fun main() {\n"
            "    println(\"hello\")\n"
            "}\n"
            "class Calculator {\n"
            "    fun add(a: Int, b: Int) = a + b\n"
            "}\n",
            encoding="utf-8",
        )

        result = extract_from_code(kt_file)

        assert result is not None
        assert result["language"] == "kotlin"

    def test_parse_swift_file(self, tmp_path: Path):
        """解析 Swift 文件"""
        swift_file = tmp_path / "App.swift"
        swift_file.write_text(
            "// Swift comment\n"
            "func greet() {\n"
            "    print(\"hello\")\n"
            "}\n"
            "class Vehicle {\n"
            "}\n",
            encoding="utf-8",
        )

        result = extract_from_code(swift_file)

        assert result is not None
        assert result["language"] == "swift"

    def test_parse_lua_file(self, tmp_path: Path):
        """解析 Lua 文件"""
        lua_file = tmp_path / "init.lua"
        lua_file.write_text(
            "-- Lua comment\n"
            "function hello()\n"
            "    print('hello')\n"
            "end\n",
            encoding="utf-8",
        )

        result = extract_from_code(lua_file)

        assert result is not None
        assert result["language"] == "lua"

    def test_parse_zig_file(self, tmp_path: Path):
        """解析 Zig 文件"""
        zig_file = tmp_path / "main.zig"
        zig_file.write_text(
            "// Zig comment\n"
            "pub fn main() void {\n"
            "    std.debug.print(\"hello\", .{});\n"
            "}\n",
            encoding="utf-8",
        )

        result = extract_from_code(zig_file)

        assert result is not None
        assert result["language"] == "zig"

    def test_parse_csharp_file(self, tmp_path: Path):
        """解析 C# 文件"""
        cs_file = tmp_path / "Program.cs"
        cs_file.write_text(
            "// C# comment\n"
            "class Program {\n"
            "    static void Main() {}\n"
            "}\n",
            encoding="utf-8",
        )

        result = extract_from_code(cs_file)

        assert result is not None
        assert result["language"] == "c#"

    def test_non_code_file_returns_none_for_extract(self, tmp_path: Path):
        """非代码文件的 extract 结果仍有 text"""
        txt_file = tmp_path / "readme.txt"
        txt_file.write_text("Hello world", encoding="utf-8")

        result = extract_from_code(txt_file)

        assert result is not None
        assert result["language"] == "unknown"

    def test_file_with_binary_content(self, tmp_path: Path):
        """包含非法 UTF-8 字符的文件使用 replace 模式"""
        py_file = tmp_path / "binary.py"
        py_file.write_bytes(b"# comment\nx = b'\\xff\\xfe'\n")

        result = extract_from_code(py_file)

        assert result is not None

    def test_file_with_mixed_indentation(self, tmp_path: Path):
        """混合缩进的文件"""
        py_file = tmp_path / "mixed_indent.py"
        py_file.write_text(
            "def foo():\n"
            "    pass\n"
            "\tdef bar():\n"
            "\t\tpass\n",
            encoding="utf-8",
        )

        result = extract_from_code(py_file)

        assert result is not None
        assert "foo" in result["functions"]
        assert "bar" in result["functions"]
