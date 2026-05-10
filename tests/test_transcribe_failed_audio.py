"""
测试 transcribe_failed_audio_v2.py 模块
"""

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# 阻止 faster_whisper 在导入时加载 GPU 模型
sys.modules["faster_whisper"] = MagicMock()

# 添加 src 目录到路径（如需要）
# sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


@pytest.fixture
def mock_workspace(tmp_path):
    workspace = tmp_path / "kb"
    workspace.mkdir()
    (workspace / "manifests").mkdir()
    (workspace / "manifests" / "sources").mkdir(parents=True)
    return workspace


@pytest.fixture
def sample_audio_manifests(mock_workspace):
    manifests = [
        {
            "id": "SRC-0001",
            "status": "failed",
            "title": "音频文件",
            "source_path": "raw/test.mp3",
            "file_path": "raw/test.mp3",
            "type": "audio",
        },
        {
            "id": "SRC-0002",
            "status": "failed",
            "title": "视频文件",
            "source_path": "raw/test.mp4",
            "file_path": "raw/test.mp4",
            "type": "video",
        },
    ]
    for m in manifests:
        f = mock_workspace / "manifests" / "sources" / f"{m['id']}.json"
        f.write_text(json.dumps(m, ensure_ascii=False), encoding="utf-8")
    return manifests


class TestGetFailedAudioManifests:
    @patch("dochris.admin.transcribe_failed_audio.get_all_manifests")
    @patch("dochris.admin.transcribe_failed_audio.get_default_workspace")
    def test_get_failed_audio_manifests(self, mock_ws, mock_get, sample_audio_manifests):
        from dochris.admin.transcribe_failed_audio import get_failed_audio_manifests

        mock_ws.return_value = mock_workspace
        mock_get.return_value = sample_audio_manifests
        result = get_failed_audio_manifests()
        assert len(result) > 0


class TestFasterWhisperTranscriber:
    @patch("faster_whisper.WhisperModel")
    def test_transcriber_init(self, mock_model):
        from dochris.admin.transcribe_failed_audio import FasterWhisperTranscriber

        mock_model_instance = MagicMock()
        mock_model.return_value = mock_model_instance
        transcriber = FasterWhisperTranscriber()
        assert transcriber.model is not None

    def test_check_duration(self, tmp_path):
        from dochris.admin.transcribe_failed_audio import FasterWhisperTranscriber

        transcriber = FasterWhisperTranscriber()
        # 测试不存在的文件
        result = transcriber.check_duration(tmp_path / "nonexistent.mp3")
        assert result == (False, None)


class TestUpdateManifest:
    @patch("dochris.admin.transcribe_failed_audio.get_manifest")
    @patch("dochris.admin.transcribe_failed_audio.get_default_workspace")
    @patch("dochris.admin.transcribe_failed_audio.update_manifest_status")
    def test_update_manifest_with_transcript(self, mock_update, mock_ws, mock_get):
        from dochris.admin.transcribe_failed_audio import update_manifest_with_transcript

        mock_ws.return_value = Path("/tmp")
        mock_get.return_value = {"id": "SRC-0001"}
        result = update_manifest_with_transcript("SRC-0001", "转录文本")
        assert result is True
