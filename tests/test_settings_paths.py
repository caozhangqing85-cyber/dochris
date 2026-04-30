"""测试 settings/paths.py 和 settings/file_category.py"""

from unittest.mock import MagicMock, patch


class TestPathsModule:
    """测试 paths.py 所有路径函数"""

    def _mock_settings(self, tmp_path):
        """构造 mock Settings 对象"""
        settings = MagicMock()
        settings.workspace = tmp_path / "ws"
        settings.logs_dir = tmp_path / "ws" / "logs"
        settings.cache_dir = tmp_path / "ws" / "cache"
        settings.outputs_dir = tmp_path / "ws" / "outputs"
        settings.raw_dir = tmp_path / "ws" / "raw"
        settings.wiki_dir = tmp_path / "ws" / "wiki"
        settings.wiki_summaries_dir = tmp_path / "ws" / "wiki" / "summaries"
        settings.wiki_concepts_dir = tmp_path / "ws" / "wiki" / "concepts"
        settings.curated_dir = tmp_path / "ws" / "curated"
        settings.curated_promoted_dir = tmp_path / "ws" / "curated" / "promoted"
        settings.manifests_dir = tmp_path / "ws" / "manifests" / "sources"
        settings.data_dir = tmp_path / "ws" / "data"
        settings.progress_file = tmp_path / "ws" / "progress.json"
        settings.phase2_lock_file = tmp_path / "ws" / "phase2.lock"
        settings.query_model = "test-model"
        settings.embedding_model = "test-embedding"
        return settings

    def test_get_workspace(self, tmp_path):
        with patch("dochris.settings.paths.get_settings", return_value=self._mock_settings(tmp_path)):
            from dochris.settings.paths import get_workspace
            assert get_workspace() == tmp_path / "ws"

    def test_get_logs_dir(self, tmp_path):
        with patch("dochris.settings.paths.get_settings", return_value=self._mock_settings(tmp_path)):
            from dochris.settings.paths import get_logs_dir
            assert get_logs_dir() == tmp_path / "ws" / "logs"

    def test_get_cache_dir(self, tmp_path):
        with patch("dochris.settings.paths.get_settings", return_value=self._mock_settings(tmp_path)):
            from dochris.settings.paths import get_cache_dir
            assert get_cache_dir() == tmp_path / "ws" / "cache"

    def test_get_outputs_dir(self, tmp_path):
        with patch("dochris.settings.paths.get_settings", return_value=self._mock_settings(tmp_path)):
            from dochris.settings.paths import get_outputs_dir
            assert get_outputs_dir() == tmp_path / "ws" / "outputs"

    def test_get_raw_dir(self, tmp_path):
        with patch("dochris.settings.paths.get_settings", return_value=self._mock_settings(tmp_path)):
            from dochris.settings.paths import get_raw_dir
            assert get_raw_dir() == tmp_path / "ws" / "raw"

    def test_get_wiki_dir(self, tmp_path):
        with patch("dochris.settings.paths.get_settings", return_value=self._mock_settings(tmp_path)):
            from dochris.settings.paths import get_wiki_dir
            assert get_wiki_dir() == tmp_path / "ws" / "wiki"

    def test_get_wiki_summaries_dir(self, tmp_path):
        with patch("dochris.settings.paths.get_settings", return_value=self._mock_settings(tmp_path)):
            from dochris.settings.paths import get_wiki_summaries_dir
            assert get_wiki_summaries_dir() == tmp_path / "ws" / "wiki" / "summaries"

    def test_get_wiki_concepts_dir(self, tmp_path):
        with patch("dochris.settings.paths.get_settings", return_value=self._mock_settings(tmp_path)):
            from dochris.settings.paths import get_wiki_concepts_dir
            assert get_wiki_concepts_dir() == tmp_path / "ws" / "wiki" / "concepts"

    def test_get_curated_dir(self, tmp_path):
        with patch("dochris.settings.paths.get_settings", return_value=self._mock_settings(tmp_path)):
            from dochris.settings.paths import get_curated_dir
            assert get_curated_dir() == tmp_path / "ws" / "curated"

    def test_get_curated_promoted_dir(self, tmp_path):
        with patch("dochris.settings.paths.get_settings", return_value=self._mock_settings(tmp_path)):
            from dochris.settings.paths import get_curated_promoted_dir
            assert get_curated_promoted_dir() == tmp_path / "ws" / "curated" / "promoted"

    def test_get_manifests_dir(self, tmp_path):
        with patch("dochris.settings.paths.get_settings", return_value=self._mock_settings(tmp_path)):
            from dochris.settings.paths import get_manifests_dir
            assert get_manifests_dir() == tmp_path / "ws" / "manifests" / "sources"

    def test_get_data_dir(self, tmp_path):
        with patch("dochris.settings.paths.get_settings", return_value=self._mock_settings(tmp_path)):
            from dochris.settings.paths import get_data_dir
            assert get_data_dir() == tmp_path / "ws" / "data"

    def test_get_progress_file(self, tmp_path):
        with patch("dochris.settings.paths.get_settings", return_value=self._mock_settings(tmp_path)):
            from dochris.settings.paths import get_progress_file
            assert get_progress_file() == tmp_path / "ws" / "progress.json"

    def test_get_phase2_lock_file(self, tmp_path):
        with patch("dochris.settings.paths.get_settings", return_value=self._mock_settings(tmp_path)):
            from dochris.settings.paths import get_phase2_lock_file
            assert get_phase2_lock_file() == tmp_path / "ws" / "phase2.lock"

    def test_get_query_model(self, tmp_path):
        with patch("dochris.settings.paths.get_settings", return_value=self._mock_settings(tmp_path)):
            from dochris.settings.paths import get_query_model
            assert get_query_model() == "test-model"

    def test_get_embedding_model(self, tmp_path):
        with patch("dochris.settings.paths.get_settings", return_value=self._mock_settings(tmp_path)):
            from dochris.settings.paths import get_embedding_model
            assert get_embedding_model() == "test-embedding"

    def test_get_default_workspace(self, tmp_path):
        with patch("dochris.settings.paths.get_settings", return_value=self._mock_settings(tmp_path)):
            from dochris.settings.paths import get_default_workspace
            assert get_default_workspace() == tmp_path / "ws"


class TestFileCategory:
    """测试 settings/file_category.py"""

    def test_pdf_category(self):
        from dochris.settings.file_category import get_file_category
        assert get_file_category(".pdf") == "pdfs"

    def test_docx_category(self):
        from dochris.settings.file_category import get_file_category
        assert get_file_category(".docx") == "pdfs"

    def test_txt_category(self):
        from dochris.settings.file_category import get_file_category
        assert get_file_category(".txt") == "articles"

    def test_md_category(self):
        from dochris.settings.file_category import get_file_category
        assert get_file_category(".md") == "articles"

    def test_mobi_category(self):
        from dochris.settings.file_category import get_file_category
        assert get_file_category(".mobi") == "ebooks"

    def test_epub_category(self):
        from dochris.settings.file_category import get_file_category
        assert get_file_category(".epub") == "ebooks"

    def test_mp3_category(self):
        from dochris.settings.file_category import get_file_category
        assert get_file_category(".mp3") == "audio"

    def test_mp4_category(self):
        from dochris.settings.file_category import get_file_category
        assert get_file_category(".mp4") == "videos"

    def test_skip_extension_returns_none(self):
        from dochris.settings.file_category import get_file_category
        assert get_file_category(".exe") is None
        assert get_file_category(".zip") is None
        assert get_file_category(".jpg") is None
        assert get_file_category(".py") is None

    def test_unknown_extension_returns_other(self):
        from dochris.settings.file_category import get_file_category
        assert get_file_category(".xyz") == "other"
        assert get_file_category(".abc") == "other"

    def test_case_insensitive(self):
        from dochris.settings.file_category import get_file_category
        assert get_file_category(".PDF") == "pdfs"
        assert get_file_category(".Mp3") == "audio"
        assert get_file_category(".EPUB") == "ebooks"

    def test_all_skip_extensions(self):
        from dochris.settings.constants import SKIP_EXTENSIONS
        from dochris.settings.file_category import get_file_category

        for ext in SKIP_EXTENSIONS:
            assert get_file_category(ext) is None

    def test_all_mapped_extensions(self):
        from dochris.settings.constants import FILE_TYPE_MAP
        from dochris.settings.file_category import get_file_category

        for ext, category in FILE_TYPE_MAP.items():
            assert get_file_category(ext) == category
