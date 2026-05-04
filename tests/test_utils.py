"""
测试 core/utils.py 模块
"""

import time
from pathlib import Path


class TestComputeFileHash:
    """测试 compute_file_hash 函数"""

    def test_compute_hash_sha256(self, tmp_path):
        """测试计算 SHA256 哈希"""
        from dochris.core.utils import compute_file_hash

        test_file = tmp_path / "test.txt"
        test_file.write_text("hello world", encoding="utf-8")

        result = compute_file_hash(test_file, "sha256")

        assert result is not None
        assert len(result) == 64  # SHA256 输出 64 个十六进制字符
        # 验证一致性
        result2 = compute_file_hash(test_file, "sha256")
        assert result == result2

    def test_compute_hash_md5(self, tmp_path):
        """测试计算 MD5 哈希"""
        from dochris.core.utils import compute_file_hash

        test_file = tmp_path / "test.txt"
        test_file.write_text("test content", encoding="utf-8")

        result = compute_file_hash(test_file, "md5")

        assert result is not None
        assert len(result) == 32  # MD5 输出 32 个十六进制字符

    def test_compute_hash_nonexistent_file(self, tmp_path):
        """测试不存在的文件"""
        from dochris.core.utils import compute_file_hash

        result = compute_file_hash(tmp_path / "nonexistent.txt")

        assert result is None


class TestIsMeaningfulText:
    """测试 is_meaningful_text 函数"""

    def test_meaningful_text_valid(self):
        """测试有意义文本"""
        from dochris.core.utils import is_meaningful_text

        # 使用足够长的文本
        long_text = "这是一段有意义的文本内容。" * 10
        assert is_meaningful_text(long_text)
        assert is_meaningful_text("a" * 100)
        assert is_meaningful_text("test", min_length=4)

    def test_meaningful_text_too_short(self):
        """测试过短文本"""
        from dochris.core.utils import is_meaningful_text

        assert not is_meaningful_text("short")
        assert not is_meaningful_text("a" * 50, min_length=100)

    def test_meaningful_text_empty(self):
        """测试空文本"""
        from dochris.core.utils import is_meaningful_text

        assert not is_meaningful_text("")
        assert not is_meaningful_text("   ")
        assert not is_meaningful_text(None)  # type: ignore


class TestTruncateText:
    """测试 truncate_text 函数"""

    def test_truncate_no_truncation_needed(self):
        """测试不需要截断"""
        from dochris.core.utils import truncate_text

        result = truncate_text("short", 20)
        assert result == "short"

    def test_truncate_with_suffix(self):
        """测试带后缀截断"""
        from dochris.core.utils import truncate_text

        result = truncate_text("This is a very long text that should be truncated", 20)
        assert len(result) == 20
        assert result.endswith("...")

    def test_truncate_custom_suffix(self):
        """测试自定义后缀"""
        from dochris.core.utils import truncate_text

        result = truncate_text("Long text here", 10, suffix=">>")
        assert result.endswith(">>")
        assert len(result) == 10

    def test_truncate_exact_length(self):
        """测试正好等于最大长度"""
        from dochris.core.utils import truncate_text

        result = truncate_text("exactlen", 8)
        assert result == "exactlen"


class TestSanitizeFilename:
    """测试 sanitize_filename 函数"""

    def test_sanitize_clean_filename(self):
        """测试清理文件名"""
        from dochris.core.utils import sanitize_filename

        assert sanitize_filename("test.pdf") == "test.pdf"
        assert sanitize_filename("document.txt") == "document.txt"

    def test_sanitize_path_traversal(self):
        """测试路径遍历字符清理"""
        from dochris.core.utils import sanitize_filename

        result = sanitize_filename("../etc/passwd")
        assert ".." not in result
        assert "/" not in result

    def test_sanitize_backslash(self):
        """测试反斜杠清理"""
        from dochris.core.utils import sanitize_filename

        result = sanitize_filename("file\\name")
        assert "\\" not in result

    def test_sanitize_special_chars(self):
        """测试特殊字符清理"""
        from dochris.core.utils import sanitize_filename

        result = sanitize_filename('file<>:"|?*name')
        assert "<" not in result
        assert ">" not in result

    def test_sanitize_empty_filename(self):
        """测试空文件名"""
        from dochris.core.utils import sanitize_filename

        result = sanitize_filename("")
        assert result == "_"

    def test_sanitize_max_length(self):
        """测试长度限制"""
        from dochris.core.utils import sanitize_filename

        long_name = "a" * 300
        result = sanitize_filename(long_name, max_length=80)
        assert len(result) == 80


class TestEnsureDir:
    """测试 ensure_dir 函数"""

    def test_ensure_dir_creates_directory(self, tmp_path):
        """测试创建目录"""
        from dochris.core.utils import ensure_dir

        new_dir = tmp_path / "new" / "nested" / "dir"
        result = ensure_dir(new_dir)

        assert result.exists()
        assert result.is_dir()

    def test_ensure_dir_existing_directory(self, tmp_path):
        """测试已存在的目录"""
        from dochris.core.utils import ensure_dir

        existing_dir = tmp_path / "existing"
        existing_dir.mkdir()

        result = ensure_dir(existing_dir)

        assert result.exists()


class TestGetFileExtension:
    """测试 get_file_extension 函数"""

    def test_get_extension_lowercase(self):
        """测试小写扩展名"""
        from dochris.core.utils import get_file_extension

        assert get_file_extension(Path("test.PDF")) == ".pdf"
        assert get_file_extension(Path("test.TXT")) == ".txt"
        assert get_file_extension(Path("test.Mp4")) == ".mp4"

    def test_get_extension_no_extension(self):
        """测试无扩展名文件"""
        from dochris.core.utils import get_file_extension

        assert get_file_extension(Path("README")) == ""
        assert get_file_extension(Path("Makefile")) == ""


class TestSafeReadText:
    """测试 safe_read_text 函数"""

    def test_safe_read_existing_file(self, tmp_path):
        """测试读取存在的文件"""
        from dochris.core.utils import safe_read_text

        test_file = tmp_path / "test.txt"
        test_file.write_text("content", encoding="utf-8")

        result = safe_read_text(test_file)

        assert result == "content"

    def test_safe_read_nonexistent_file(self, tmp_path):
        """测试读取不存在的文件"""
        from dochris.core.utils import safe_read_text

        result = safe_read_text(tmp_path / "nonexistent.txt")

        assert result is None

    def test_safe_read_with_encoding(self, tmp_path):
        """测试指定编码"""
        from dochris.core.utils import safe_read_text

        test_file = tmp_path / "test.txt"
        test_file.write_text("内容", encoding="utf-8")

        result = safe_read_text(test_file, encoding="utf-8")

        assert "内容" in result


class TestFormatTimestamp:
    """测试 format_timestamp 函数"""

    def test_format_timestamp_default(self):
        """测试默认格式"""
        from dochris.core.utils import format_timestamp

        ts = time.time()
        result = format_timestamp(ts)

        assert isinstance(result, str)
        assert len(result) == 19  # "YYYY-MM-DD HH:MM:SS"

    def test_format_timestamp_custom_format(self):
        """测试自定义格式"""
        from dochris.core.utils import format_timestamp

        ts = time.time()
        result = format_timestamp(ts, fmt="%Y-%m-%d")

        assert len(result) == 10  # "YYYY-MM-DD"


class TestGetIsoTimestamp:
    """测试 get_iso_timestamp 函数"""

    def test_get_iso_timestamp(self):
        """测试获取 ISO 时间戳"""
        from dochris.core.utils import get_iso_timestamp

        result = get_iso_timestamp()

        assert isinstance(result, str)
        assert "T" in result  # ISO 格式包含 T


class TestValidatePathWithinBase:
    """测试 validate_path_within_base 函数"""

    def test_validate_safe_path(self, tmp_path):
        """测试安全路径"""
        from dochris.core.utils import validate_path_within_base

        safe_path = tmp_path / "subdir" / "file.txt"

        assert validate_path_within_base(safe_path, tmp_path) is True

    def test_validate_outside_path(self, tmp_path):
        """测试外部路径"""
        from dochris.core.utils import validate_path_within_base

        outside_path = Path("/etc/passwd")

        assert validate_path_within_base(outside_path, tmp_path) is False

    def test_validate_path_traversal(self, tmp_path):
        """测试路径遍历攻击"""
        from dochris.core.utils import validate_path_within_base

        # 创建一个子目录
        (tmp_path / "safe").mkdir()

        # 尝试使用 .. 跳出
        traversal_path = tmp_path / "safe" / ".." / ".." / "etc"

        assert validate_path_within_base(traversal_path, tmp_path) is False
