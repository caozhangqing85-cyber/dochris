"""
缓存模块单元测试
"""

import json
from datetime import datetime, timedelta

from dochris.core.cache import (
    cache_dir,
    clear_cache,
    file_hash,
    load_cached,
    save_cached,
)


class TestFileHash:
    """测试文件哈希函数"""

    def test_file_hash_existing_file(self, temp_workspace):
        """测试计算现有文件的哈希"""
        test_file = temp_workspace / "test.txt"
        test_file.write_text("Hello, World!", encoding="utf-8")

        result = file_hash(test_file)
        assert result is not None
        assert isinstance(result, str)
        assert len(result) == 64  # SHA256 输出长度
        assert result.isalnum()

    def test_file_hash_nonexistent_file(self, temp_workspace):
        """测试不存在文件的哈希"""
        test_file = temp_workspace / "nonexistent.txt"
        result = file_hash(test_file)
        assert result is None

    def test_file_hash_same_content_same_hash(self, temp_workspace):
        """测试相同内容产生相同哈希"""
        file1 = temp_workspace / "file1.txt"
        file2 = temp_workspace / "file2.txt"
        content = "Same content"

        file1.write_text(content, encoding="utf-8")
        file2.write_text(content, encoding="utf-8")

        hash1 = file_hash(file1)
        hash2 = file_hash(file2)

        # 相同内容应该产生相同哈希（哈希不包含路径）
        assert hash1 == hash2

    def test_file_hash_different_content_different_hash(self, temp_workspace):
        """测试不同内容产生不同哈希"""
        file1 = temp_workspace / "file1.txt"
        file2 = temp_workspace / "file2.txt"

        file1.write_text("Content 1", encoding="utf-8")
        file2.write_text("Content 2", encoding="utf-8")

        hash1 = file_hash(file1)
        hash2 = file_hash(file2)

        assert hash1 != hash2


class TestCacheDir:
    """测试缓存目录函数"""

    def test_cache_dir_creates_directory(self, temp_workspace):
        """测试缓存目录创建"""
        cache_path = cache_dir(temp_workspace)
        assert cache_path.exists()
        assert cache_path.is_dir()
        assert "cache" in str(cache_path)

    def test_cache_dir_returns_same_path(self, temp_workspace):
        """测试多次调用返回相同路径"""
        path1 = cache_dir(temp_workspace)
        path2 = cache_dir(temp_workspace)
        assert path1 == path2


class TestLoadCached:
    """测试加载缓存函数"""

    def test_load_cached_no_hash(self, temp_workspace):
        """测试空哈希返回 None"""
        cache_path = cache_dir(temp_workspace)
        result = load_cached(cache_path, "")
        assert result is None

    def test_load_cached_no_file(self, temp_workspace):
        """测试不存在的缓存文件返回 None"""
        cache_path = cache_dir(temp_workspace)
        result = load_cached(cache_path, "nonexistent_hash")
        assert result is None

    def test_load_cached_valid_file(self, temp_workspace):
        """测试加载有效缓存"""
        cache_path = cache_dir(temp_workspace)
        test_hash = "abc123"
        test_result = {"key": "value", "items": [1, 2, 3]}

        # 创建缓存文件
        cache_file = cache_path / f"{test_hash}.json"
        cache_file.write_text(
            json.dumps({"hash": test_hash, "result": test_result}), encoding="utf-8"
        )

        result = load_cached(cache_path, test_hash)
        assert result == test_result

    def test_load_cached_hash_mismatch(self, temp_workspace):
        """测试哈希不匹配返回 None"""
        cache_path = cache_dir(temp_workspace)
        stored_hash = "stored_hash"
        query_hash = "different_hash"

        # 创建哈希不匹配的缓存文件
        cache_file = cache_path / f"{stored_hash}.json"
        cache_file.write_text(
            json.dumps({"hash": stored_hash, "result": {"data": "test"}}), encoding="utf-8"
        )

        # 查询时使用不同的哈希
        result = load_cached(cache_path, query_hash)
        assert result is None

    def test_load_cached_invalid_json(self, temp_workspace):
        """测试无效 JSON 返回 None"""
        cache_path = cache_dir(temp_workspace)
        cache_file = cache_path / "invalid.json"
        cache_file.write_text("not valid json", encoding="utf-8")

        result = load_cached(cache_path, "invalid")
        assert result is None


class TestSaveCached:
    """测试保存缓存函数"""

    def test_save_cached_no_hash(self, temp_workspace):
        """测试空哈希返回 None"""
        cache_path = cache_dir(temp_workspace)
        result = save_cached(cache_path, "", {"data": "test"})
        assert result is None

    def test_save_cached_creates_file(self, temp_workspace):
        """测试保存创建缓存文件"""
        cache_path = cache_dir(temp_workspace)
        test_hash = "test_hash_123"
        test_result = {"answer": 42}

        save_cached(cache_path, test_hash, test_result)

        cache_file = cache_path / f"{test_hash}.json"
        assert cache_file.exists()

    def test_save_cached_roundtrip(self, temp_workspace):
        """测试保存后加载可恢复数据"""
        cache_path = cache_dir(temp_workspace)
        test_hash = "roundtrip_hash"
        test_result = {"one_line": "测试摘要", "key_points": ["要点1", "要点2"], "score": 95}

        save_cached(cache_path, test_hash, test_result)
        loaded = load_cached(cache_path, test_hash)

        assert loaded == test_result

    def test_save_cached_includes_timestamp(self, temp_workspace):
        """测试保存包含时间戳"""
        cache_path = cache_dir(temp_workspace)
        test_hash = "timestamp_hash"
        test_result = {"data": "test"}

        save_cached(cache_path, test_hash, test_result)

        cache_file = cache_path / f"{test_hash}.json"
        content = json.loads(cache_file.read_text(encoding="utf-8"))

        assert "timestamp" in content
        assert content["hash"] == test_hash
        assert content["result"] == test_result

    def test_save_cached_overwrites(self, temp_workspace):
        """测试保存覆盖现有缓存"""
        cache_path = cache_dir(temp_workspace)
        test_hash = "overwrite_hash"

        save_cached(cache_path, test_hash, {"version": 1})
        save_cached(cache_path, test_hash, {"version": 2})

        loaded = load_cached(cache_path, test_hash)
        assert loaded == {"version": 2}


class TestClearCache:
    """测试清理缓存函数"""

    def test_clear_cache_empty_directory(self, temp_workspace):
        """测试清理空目录"""
        cache_path = cache_dir(temp_workspace)
        count = clear_cache(cache_path, older_than_days=30)
        assert count == 0

    def test_clear_cache_removes_old_files(self, temp_workspace):
        """测试清理删除旧文件"""
        cache_path = cache_dir(temp_workspace)

        # 创建旧文件
        old_file = cache_path / "old_cache.json"
        old_file.write_text('{"hash": "old", "result": {}}', encoding="utf-8")

        # 修改文件时间为 31 天前
        old_time = datetime.now() - timedelta(days=31)
        import os

        os.utime(old_file, (old_time.timestamp(), old_time.timestamp()))

        count = clear_cache(cache_path, older_than_days=30)
        assert count == 1
        assert not old_file.exists()

    def test_clear_cache_keeps_recent_files(self, temp_workspace):
        """测试清理保留新文件"""
        cache_path = cache_dir(temp_workspace)

        # 创建新文件
        new_file = cache_path / "new_cache.json"
        new_file.write_text('{"hash": "new", "result": {}}', encoding="utf-8")

        count = clear_cache(cache_path, older_than_days=30)
        assert count == 0
        assert new_file.exists()

    def test_clear_cache_mixed_files(self, temp_workspace):
        """测试清理混合文件"""
        cache_path = cache_dir(temp_workspace)
        import os

        # 创建旧文件
        old_file = cache_path / "old.json"
        old_file.write_text('{"hash": "old"}', encoding="utf-8")
        old_time = datetime.now() - timedelta(days=35)
        os.utime(old_file, (old_time.timestamp(), old_time.timestamp()))

        # 创建新文件
        new_file = cache_path / "new.json"
        new_file.write_text('{"hash": "new"}', encoding="utf-8")

        # 创建中等文件
        mid_file = cache_path / "mid.json"
        mid_file.write_text('{"hash": "mid"}', encoding="utf-8")
        mid_time = datetime.now() - timedelta(days=25)
        os.utime(mid_file, (mid_time.timestamp(), mid_time.timestamp()))

        count = clear_cache(cache_path, older_than_days=30)

        assert count == 1  # 只删除旧文件
        assert not old_file.exists()
        assert new_file.exists()
        assert mid_file.exists()

    def test_clear_cache_zero_days_removes_all(self, temp_workspace):
        """测试清理零天删除所有文件"""
        cache_path = cache_dir(temp_workspace)

        # 创建多个文件
        for i in range(3):
            cache_file = cache_path / f"cache_{i}.json"
            cache_file.write_text(f'{{"hash": "{i}"}}', encoding="utf-8")

        count = clear_cache(cache_path, older_than_days=0)

        assert count == 3
        assert len(list(cache_path.glob("*.json"))) == 0
