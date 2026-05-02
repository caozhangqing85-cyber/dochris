"""补充测试 phase1_ingestion.py — 覆盖 get_audio_duration exception + resolve max_attempts + scan functions"""

from unittest.mock import MagicMock, patch


class TestGetAudioDurationExceptions:
    """覆盖 get_audio_duration 的异常分支 (lines 169-176)"""

    def test_ffprobe_timeout(self, tmp_path):
        """ffprobe 超时返回 None"""
        import subprocess

        from dochris.phases.phase1_ingestion import get_audio_duration

        audio = tmp_path / "test.mp3"
        audio.write_bytes(b"\xff\xfb" + b"\x00" * 100)

        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="ffprobe", timeout=5)):
            result = get_audio_duration(audio)

        assert result is None

    def test_ffprobe_not_found(self, tmp_path):
        """ffprobe 不存在返回 None"""
        from dochris.phases.phase1_ingestion import get_audio_duration

        audio = tmp_path / "test.mp3"
        audio.write_bytes(b"\xff\xfb" + b"\x00" * 100)

        with patch("subprocess.run", side_effect=FileNotFoundError("no ffprobe")):
            result = get_audio_duration(audio)

        assert result is None

    def test_ffprobe_bad_json(self, tmp_path):
        """ffprobe 返回损坏 JSON 返回 None"""
        from dochris.phases.phase1_ingestion import get_audio_duration

        audio = tmp_path / "test.mp3"
        audio.write_bytes(b"\xff\xfb" + b"\x00" * 100)

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "bad json"

        with patch("subprocess.run", return_value=mock_result):
            result = get_audio_duration(audio)

        assert result is None


class TestResolvePathMaxAttempts:
    """覆盖 resolve_path_conflict max_attempts (lines 299-300)"""

    def test_max_attempts_exceeded(self, tmp_path):
        """超过最大尝试次数返回 None"""
        from dochris.phases.phase1_ingestion import resolve_path_conflict

        # 创建冲突文件
        (tmp_path / "test.pdf").write_bytes(b"a")
        (tmp_path / "test_1.pdf").write_bytes(b"b")

        result = resolve_path_conflict(tmp_path, "test.pdf", MagicMock(), max_attempts=1)
        assert result is None


class TestScanObsidianVault:
    """覆盖 scan_obsidian_vault (lines 190-211)"""

    def test_scan_empty_vault(self, tmp_path):
        """空 vault 返回空列表"""
        from dochris.phases.phase1_ingestion import scan_obsidian_vault

        vault = tmp_path / "vault"
        vault.mkdir()

        result = scan_obsidian_vault(vault, MagicMock())
        assert result == []

    def test_scan_nonexistent_vault(self, tmp_path):
        """不存在的 vault 返回空列表"""
        from dochris.phases.phase1_ingestion import scan_obsidian_vault

        result = scan_obsidian_vault(tmp_path / "nonexistent", MagicMock())
        assert result == []

    def test_scan_with_md_files(self, tmp_path):
        """有 md 文件时返回文件列表"""
        from dochris.phases.phase1_ingestion import scan_obsidian_vault

        vault = tmp_path / "vault"
        vault.mkdir()
        (vault / "test1.md").write_text("# Test1", encoding="utf-8")
        (vault / "sub").mkdir()
        (vault / "sub" / "test2.md").write_text("# Test2", encoding="utf-8")
        # 隐藏文件应被跳过
        (vault / ".obsidian").mkdir()
        (vault / ".obsidian" / "config.md").write_text("config", encoding="utf-8")

        result = scan_obsidian_vault(vault, MagicMock())
        assert len(result) >= 2
        names = [r["name"] for r in result]
        assert "test1.md" in names
        assert "test2.md" in names


class TestScanSourceDir:
    """覆盖 scan_source_dir (lines 224-269)"""

    def test_scan_nonexistent_dir(self, tmp_path):
        """不存在的目录返回空列表"""
        from dochris.phases.phase1_ingestion import scan_source_dir

        result = scan_source_dir(tmp_path / "nonexistent", MagicMock())
        assert result == []

    def test_scan_with_files(self, tmp_path):
        """扫描源目录返回文件列表"""
        from dochris.phases.phase1_ingestion import scan_source_dir

        source = tmp_path / "source"
        source.mkdir()
        (source / "test.pdf").write_bytes(b"%PDF")
        (source / "test.mp3").write_bytes(b"\xff\xfb")
        (source / "test.txt").write_text("text", encoding="utf-8")

        result = scan_source_dir(source, MagicMock())
        assert len(result) >= 2  # 至少 pdf 和 mp3
