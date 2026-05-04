"""核心工具函数测试"""

from __future__ import annotations

import time
from pathlib import Path

from dochris.core.utils import (
    compute_file_hash,
    ensure_dir,
    format_timestamp,
    get_file_extension,
    get_iso_timestamp,
    is_meaningful_text,
    safe_read_text,
    sanitize_filename,
    truncate_text,
    validate_path_within_base,
)

# ── sanitize_filename ──────────────────────────────────────────


class TestSanitizeFilename:
    """清理文件名"""

    def test_normal_filename_unchanged(self):
        """正常文件名不变"""
        assert sanitize_filename("test.pdf") == "test.pdf"

    def test_path_traversal_removed(self):
        """路径遍历字符被移除"""
        result = sanitize_filename("../etc/passwd")
        assert ".." not in result
        assert "/" not in result

    def test_control_chars_removed(self):
        """控制字符被移除"""
        result = sanitize_filename("file\x00name")
        assert "\x00" not in result

    def test_empty_string_returns_replacement(self):
        """空字符串返回替换字符"""
        assert sanitize_filename("") == "_"

    def test_long_name_truncated(self):
        """超长文件名被截断"""
        long_name = "a" * 300
        result = sanitize_filename(long_name, max_length=80)
        assert len(result) <= 80

    def test_special_chars_replaced(self):
        """特殊字符被替换"""
        result = sanitize_filename("file<script>.txt")
        assert "<" not in result
        assert ">" not in result
        assert result.endswith(".txt")

    def test_backslash_replaced(self):
        """反斜杠被替换"""
        result = sanitize_filename("path\\to\\file.pdf")
        assert "\\" not in result

    def test_consecutive_replacements_collapsed(self):
        """连续替换字符被合并"""
        result = sanitize_filename("a<>b")
        assert "__" not in result


# ── is_meaningful_text ─────────────────────────────────────────


class TestIsMeaningfulText:
    """判断文本是否有意义"""

    def test_meaningful_text(self):
        """有意义的文本返回 True"""
        text = "A" * 100
        assert is_meaningful_text(text) is True

    def test_short_text_false(self):
        """短文本返回 False"""
        assert is_meaningful_text("hi") is False

    def test_empty_string_false(self):
        """空字符串返回 False"""
        assert is_meaningful_text("") is False

    def test_none_input_false(self):
        """None 输入返回 False"""
        assert is_meaningful_text(None) is False

    def test_whitespace_only_false(self):
        """纯空白返回 False"""
        assert is_meaningful_text("   " * 20) is False

    def test_custom_min_length(self):
        """自定义最小长度"""
        assert is_meaningful_text("hello", min_length=3) is True
        assert is_meaningful_text("hi", min_length=3) is False

    def test_non_string_input_false(self):
        """非字符串输入返回 False"""
        assert is_meaningful_text(123) is False  # type: ignore[arg-type]


# ── truncate_text ──────────────────────────────────────────────


class TestTruncateText:
    """截断文本"""

    def test_short_text_unchanged(self):
        """短文本不截断"""
        assert truncate_text("hello", max_length=10) == "hello"

    def test_exact_length_unchanged(self):
        """恰好等于最大长度时不截断"""
        text = "hello"
        assert truncate_text(text, max_length=5) == text

    def test_long_text_truncated(self):
        """超长文本被截断"""
        result = truncate_text("abcdefghij", max_length=5)
        assert result == "ab..."

    def test_custom_suffix(self):
        """自定义截断后缀"""
        result = truncate_text("abcdefghij", max_length=5, suffix="…")
        assert result == "abcd…"

    def test_empty_string(self):
        """空字符串直接返回"""
        assert truncate_text("", max_length=10) == ""


# ── compute_file_hash ──────────────────────────────────────────


class TestComputeFileHash:
    """计算文件哈希"""

    def test_sha256(self, tmp_path):
        """SHA-256 哈希正确"""
        f = tmp_path / "test.txt"
        f.write_text("hello world", encoding="utf-8")
        result = compute_file_hash(f)
        assert result is not None
        assert len(result) == 64  # SHA-256 hex length

    def test_md5(self, tmp_path):
        """MD5 哈希正确"""
        f = tmp_path / "test.txt"
        f.write_text("test", encoding="utf-8")
        result = compute_file_hash(f, algorithm="md5")
        assert result is not None
        assert len(result) == 32  # MD5 hex length

    def test_nonexistent_file_returns_none(self):
        """文件不存在返回 None"""
        assert compute_file_hash(Path("/nonexistent/file")) is None

    def test_deterministic(self, tmp_path):
        """相同文件多次计算结果一致"""
        f = tmp_path / "test.txt"
        f.write_bytes(b"consistent content")
        h1 = compute_file_hash(f)
        h2 = compute_file_hash(f)
        assert h1 == h2

    def test_different_content_different_hash(self, tmp_path):
        """不同内容不同哈希"""
        f1 = tmp_path / "a.txt"
        f2 = tmp_path / "b.txt"
        f1.write_bytes(b"aaa")
        f2.write_bytes(b"bbb")
        assert compute_file_hash(f1) != compute_file_hash(f2)


# ── ensure_dir ─────────────────────────────────────────────────


class TestEnsureDir:
    """确保目录存在"""

    def test_creates_directory(self, tmp_path):
        """创建不存在的目录"""
        new_dir = tmp_path / "a" / "b" / "c"
        result = ensure_dir(new_dir)
        assert result.exists()
        assert result.is_dir()

    def test_existing_directory_ok(self, tmp_path):
        """已存在的目录直接返回"""
        result = ensure_dir(tmp_path)
        assert result == tmp_path


# ── get_file_extension ─────────────────────────────────────────


class TestGetFileExtension:
    """获取文件扩展名"""

    def test_pdf(self):
        assert get_file_extension(Path("test.PDF")) == ".pdf"

    def test_no_extension(self):
        assert get_file_extension(Path("README")) == ""

    def test_double_extension(self):
        assert get_file_extension(Path("archive.tar.gz")) == ".gz"


# ── safe_read_text ─────────────────────────────────────────────


class TestSafeReadText:
    """安全读取文本"""

    def test_reads_existing_file(self, tmp_path):
        """读取存在的文件"""
        f = tmp_path / "hello.txt"
        f.write_text("你好世界", encoding="utf-8")
        assert safe_read_text(f) == "你好世界"

    def test_nonexistent_returns_none(self):
        """文件不存在返回 None"""
        assert safe_read_text(Path("/no/such/file")) is None


# ── format_timestamp ───────────────────────────────────────────


class TestFormatTimestamp:
    """格式化时间戳"""

    def test_default_format(self):
        """默认格式"""
        ts = time.time()
        result = format_timestamp(ts)
        assert "202" in result  # 年份

    def test_custom_format(self):
        """自定义格式"""
        ts = time.time()
        result = format_timestamp(ts, fmt="%Y/%m/%d")
        assert "/" in result


# ── get_iso_timestamp ──────────────────────────────────────────


class TestGetIsoTimestamp:
    """获取 ISO 时间戳"""

    def test_returns_string(self):
        result = get_iso_timestamp()
        assert isinstance(result, str)
        assert "T" in result


# ── validate_path_within_base ──────────────────────────────────


class TestValidatePathWithinBase:
    """验证路径在基础目录内"""

    def test_path_within_base(self, tmp_path):
        """路径在基础目录内返回 True"""
        assert validate_path_within_base(tmp_path / "file.txt", tmp_path) is True

    def test_path_outside_base(self, tmp_path):
        """路径在基础目录外返回 False"""
        assert validate_path_within_base(Path("/etc/passwd"), tmp_path) is False

    def test_traversal_attack(self, tmp_path):
        """路径遍历攻击被阻止"""
        assert validate_path_within_base(tmp_path / "../etc/passwd", tmp_path) is False

    def test_deep_subdirectory(self, tmp_path):
        """深层子目录返回 True"""
        assert validate_path_within_base(tmp_path / "a" / "b" / "c.txt", tmp_path) is True
