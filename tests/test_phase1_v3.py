"""补充测试 phase1_ingestion.py — 覆盖 file_hash + get_audio_duration + resolve_path_conflict"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


class TestFileHash:
    """覆盖 file_hash 函数"""

    def test_file_hash_success(self, tmp_path):
        """成功计算文件哈希"""
        from dochris.phases.phase1_ingestion import file_hash

        test_file = tmp_path / "test.txt"
        test_file.write_text("hello world", encoding="utf-8")

        result = file_hash(test_file)
        assert result is not None
        assert len(result) == 64  # SHA256 hex

    def test_file_hash_nonexistent(self, tmp_path):
        """不存在的文件返回 None"""
        from dochris.phases.phase1_ingestion import file_hash

        result = file_hash(tmp_path / "nonexistent.txt")
        assert result is None

    def test_file_hash_permission_denied(self, tmp_path):
        """权限被拒返回 None"""
        from dochris.phases.phase1_ingestion import file_hash

        test_file = tmp_path / "test.txt"
        test_file.write_text("data", encoding="utf-8")

        with patch("builtins.open", side_effect=OSError("permission denied")):
            result = file_hash(test_file)

        assert result is None


class TestGetAudioDuration:
    """覆盖 get_audio_duration 函数"""

    def test_nonexistent_file(self, tmp_path):
        """不存在的文件返回 None"""
        from dochris.phases.phase1_ingestion import get_audio_duration

        result = get_audio_duration(tmp_path / "nonexistent.mp3")
        assert result is None

    def test_path_validation_error(self, tmp_path):
        """路径验证失败返回 None"""
        from dochris.phases.phase1_ingestion import get_audio_duration

        mock_path = MagicMock(spec=Path)
        mock_path.exists.side_effect = OSError("validation failed")
        mock_path.suffix = ".mp3"

        result = get_audio_duration(mock_path)
        assert result is None


class TestResolvePathConflict:
    """覆盖 resolve_path_conflict 函数"""

    def test_no_conflict(self, tmp_path):
        """无冲突直接使用原路径"""
        from dochris.phases.phase1_ingestion import resolve_path_conflict

        result = resolve_path_conflict(tmp_path, "test.pdf", MagicMock())
        assert result == tmp_path / "test.pdf"

    def test_conflict_resolves(self, tmp_path):
        """冲突时添加序号"""
        from dochris.phases.phase1_ingestion import resolve_path_conflict

        (tmp_path / "test.pdf").write_bytes(b"existing")

        result = resolve_path_conflict(tmp_path, "test.pdf", MagicMock())
        assert result.name == "test_1.pdf"

    def test_multiple_conflicts(self, tmp_path):
        """多次冲突递增序号"""
        from dochris.phases.phase1_ingestion import resolve_path_conflict

        (tmp_path / "test.pdf").write_bytes(b"first")
        (tmp_path / "test_1.pdf").write_bytes(b"second")

        result = resolve_path_conflict(tmp_path, "test.pdf", MagicMock())
        assert result.name == "test_2.pdf"
