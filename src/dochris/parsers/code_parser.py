#!/usr/bin/env python3
"""
代码文件解析 (无需 LLM)
"""

import logging
import re
from pathlib import Path

logger = logging.getLogger(__name__)


def detect_code_file(file_path: Path) -> bool:
    """检测是否为代码文件"""
    code_extensions = {
        ".py",
        ".js",
        ".ts",
        ".java",
        ".c",
        ".cpp",
        ".go",
        ".rs",
        ".rb",
        ".cs",
        ".kt",
        ".swift",
        ".lua",
        ".zig",
        ".php",
        ".m",
        ".mm",
    }
    return file_path.suffix.lower() in code_extensions


def extract_from_code(file_path: Path) -> dict[str, str] | None:
    """
    从代码文件提取内容 (无需 LLM)

    Returns:
        {
            "text": "提取的文本",
            "language": "代码语言",
            "functions": ["函数1", "函数2"],
            "classes": ["类1", "类2"]
        }
    """
    try:
        content = file_path.read_text(encoding="utf-8", errors="replace")

        # 简单提取
        functions = re.findall(r"def\s+(\w+)", content)
        classes = re.findall(r"class\s+(\w+)", content)

        language = _detect_language(file_path)

        # 提取 docstring 和注释
        text = _extract_docstrings_and_comments(content, language)

        return {"text": text, "language": language, "functions": functions, "classes": classes}
    except OSError as e:
        logger.warning(f"Failed to parse code file {file_path}: {e}")
        return None


def _detect_language(file_path: Path) -> str:
    """检测代码语言"""
    ext_map = {
        ".py": "python",
        ".js": "javascript",
        ".ts": "typescript",
        ".java": "java",
        ".c": "c",
        ".cpp": "c++",
        ".go": "go",
        ".rs": "rust",
        ".rb": "ruby",
        ".cs": "c#",
        ".kt": "kotlin",
        ".swift": "swift",
        ".lua": "lua",
        ".zig": "zig",
        ".php": "php",
    }
    return ext_map.get(file_path.suffix.lower(), "unknown")


def _extract_docstrings_and_comments(content: str, language: str) -> str:
    """提取文档字符串和注释"""
    lines = []
    in_docstring = False

    for line in content.split("\n"):
        stripped = line.strip()

        # Python docstring
        if language == "python":
            if '"""' in stripped or "'''" in stripped:
                in_docstring = not in_docstring
            if in_docstring or stripped.startswith("#"):
                lines.append(line)
        # 其他语言的注释
        elif stripped.startswith(("#", "//", "/*", "*")):
            lines.append(line)

    return "\n".join(lines)
