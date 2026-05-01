"""覆盖率提升 v13 — vector/faiss_store.py + settings/config.py"""

import json
import sys
from unittest.mock import MagicMock, patch

import pytest


# ============================================================
# vector/faiss_store.py — mock FAISS/sentence_transformers
# ============================================================
class TestFAISSStoreInit:
    def test_default_persist_directory(self):
        from dochris.vector.faiss_store import FAISSStore

        with patch.dict("sys.modules", {}):
            store = FAISSStore()
        assert store._persist_directory.name == "faiss_data"
        assert store.name == "faiss"

    def test_custom_persist_directory(self, tmp_path):
        from dochris.vector.faiss_store import FAISSStore

        store = FAISSStore(persist_directory=str(tmp_path / "my_faiss"))
        assert store._persist_directory == tmp_path / "my_faiss"


class TestFAISSStoreListCollections:
    def test_no_persist_directory(self, tmp_path):
        from dochris.vector.faiss_store import FAISSStore

        store = FAISSStore(persist_directory=str(tmp_path / "nonexistent"))
        assert store.list_collections() == []

    def test_list_with_collections(self, tmp_path):
        from dochris.vector.faiss_store import FAISSStore

        persist = tmp_path / "faiss_data"
        col1 = persist / "col1"
        col1.mkdir(parents=True)
        (col1 / "index.faiss").write_bytes(b"fake")
        col2 = persist / "col2"
        col2.mkdir(parents=True)
        # col2 has no index.faiss, should not be listed

        store = FAISSStore(persist_directory=str(persist))
        result = store.list_collections()
        assert "col1" in result
        assert "col2" not in result


class TestFAISSStoreGetCollectionCount:
    def test_empty_collection(self, tmp_path):
        from dochris.vector.faiss_store import FAISSStore

        store = FAISSStore(persist_directory=str(tmp_path))
        count = store.get_collection_count("nonexistent")
        assert count == 0

    def test_with_mock_index(self, tmp_path):
        from dochris.vector.faiss_store import FAISSStore

        store = FAISSStore(persist_directory=str(tmp_path))
        mock_index = MagicMock()
        mock_index.ntotal = 42
        store._indexes["test_col"] = mock_index
        store._documents["test_col"] = {}
        store._metadatas["test_col"] = {}

        count = store.get_collection_count("test_col")
        assert count == 42


class TestFAISSStoreClose:
    def test_close_clears_state(self, tmp_path):
        from dochris.vector.faiss_store import FAISSStore

        store = FAISSStore(persist_directory=str(tmp_path))
        store._indexes["col"] = MagicMock()
        store._documents["col"] = {"id1": "doc1"}
        store._metadatas["col"] = {"id1": {}}
        store._model = MagicMock()

        store.close()
        assert store._indexes == {}
        assert store._documents == {}
        assert store._metadatas == {}
        assert store._model is None


class TestFAISSStoreLoadCollection:
    def test_load_nonexistent_dir(self, tmp_path):
        from dochris.vector.faiss_store import FAISSStore

        store = FAISSStore(persist_directory=str(tmp_path))
        store._load_collection("missing")
        assert store._indexes["missing"] is None
        assert store._documents["missing"] == {}

    def test_load_with_metadata(self, tmp_path):
        from dochris.vector.faiss_store import FAISSStore

        persist = tmp_path / "faiss"
        col_dir = persist / "mycol"
        col_dir.mkdir(parents=True)

        meta = {"documents": {"id1": "hello"}, "metadatas": {"id1": {"tag": "test"}}}
        (col_dir / "metadata.json").write_text(json.dumps(meta), encoding="utf-8")

        store = FAISSStore(persist_directory=str(persist))
        with patch.dict("sys.modules", {"faiss": MagicMock()}):
            store._load_collection("mycol")

        assert store._documents["mycol"]["id1"] == "hello"
        assert store._metadatas["mycol"]["id1"]["tag"] == "test"

    def test_load_already_loaded(self, tmp_path):
        from dochris.vector.faiss_store import FAISSStore

        store = FAISSStore(persist_directory=str(tmp_path))
        store._indexes["already"] = MagicMock()
        # Should not overwrite
        store._load_collection("already")
        assert store._indexes["already"] is not None


class TestFAISSStoreAddDocuments:
    def test_length_mismatch(self, tmp_path):
        from dochris.vector.faiss_store import FAISSStore

        mock_faiss = MagicMock()
        store = FAISSStore(persist_directory=str(tmp_path))
        with patch.dict("sys.modules", {"faiss": mock_faiss}):
            with pytest.raises(ValueError, match="length mismatch"):
                store.add_documents("col", ["doc1"], ["id1", "id2"])

    def test_metadata_length_mismatch(self, tmp_path):
        from dochris.vector.faiss_store import FAISSStore

        mock_faiss = MagicMock()
        mock_model = MagicMock()
        mock_model.encode.return_value.astype.return_value = MagicMock(shape=(1, 10))

        store = FAISSStore(persist_directory=str(tmp_path))
        store._model = mock_model
        mock_index = MagicMock()
        mock_index.ntotal = 0
        store._indexes["col"] = mock_index
        store._documents["col"] = {}
        store._metadatas["col"] = {}

        with patch.dict("sys.modules", {"faiss": mock_faiss}):
            with pytest.raises(ValueError, match="metadatas"):
                store.add_documents("col", ["doc1"], ["id1"], [{}, {}])

    def test_faiss_not_installed(self, tmp_path):
        from dochris.vector.faiss_store import FAISSStore

        store = FAISSStore(persist_directory=str(tmp_path))
        # Remove faiss from sys.modules to trigger ImportError
        saved = sys.modules.pop("faiss", None)
        try:
            with pytest.raises(ImportError, match="faiss not installed"):
                store.add_documents("col", ["doc"], ["id1"])
        finally:
            if saved is not None:
                sys.modules["faiss"] = saved


class TestFAISSStoreQuery:
    def test_query_empty_index(self, tmp_path):
        from dochris.vector.faiss_store import FAISSStore

        store = FAISSStore(persist_directory=str(tmp_path))
        store._indexes["col"] = None
        store._documents["col"] = {}
        store._metadatas["col"] = {}

        mock_faiss = MagicMock()
        mock_model = MagicMock()
        store._model = mock_model

        with patch.dict("sys.modules", {"faiss": mock_faiss}):
            results = store.query("col", "search text")
        assert results == []

    def test_query_with_results(self, tmp_path):
        from dochris.vector.faiss_store import FAISSStore

        mock_index = MagicMock()
        mock_index.ntotal = 2
        mock_index.search.return_value = ([[0.1, 0.5]], [[0, 1]])

        store = FAISSStore(persist_directory=str(tmp_path))
        store._indexes["col"] = mock_index
        store._documents["col"] = {"id1": "doc1", "id2": "doc2"}
        store._metadatas["col"] = {"id1": {"tag": "a"}, "id2": {"tag": "b"}}

        mock_model = MagicMock()
        mock_embedding = MagicMock()
        mock_model.encode.return_value.astype.return_value = mock_embedding
        store._model = mock_model

        mock_faiss = MagicMock()
        with patch.dict("sys.modules", {"faiss": mock_faiss}):
            results = store.query("col", "search text")

        assert len(results) == 2
        assert results[0]["id"] == "id1"
        assert results[0]["distance"] == 0.1

    def test_query_with_where_filter(self, tmp_path):
        from dochris.vector.faiss_store import FAISSStore

        mock_index = MagicMock()
        mock_index.ntotal = 2
        mock_index.search.return_value = ([[0.1, 0.5]], [[0, 1]])

        store = FAISSStore(persist_directory=str(tmp_path))
        store._indexes["col"] = mock_index
        store._documents["col"] = {"id1": "doc1", "id2": "doc2"}
        store._metadatas["col"] = {"id1": {"tag": "a"}, "id2": {"tag": "b"}}

        mock_model = MagicMock()
        mock_embedding = MagicMock()
        mock_model.encode.return_value.astype.return_value = mock_embedding
        store._model = mock_model

        mock_faiss = MagicMock()
        with patch.dict("sys.modules", {"faiss": mock_faiss}):
            results = store.query("col", "search text", where={"tag": "b"})

        assert len(results) == 1
        assert results[0]["id"] == "id2"

    def test_query_with_negative_index(self, tmp_path):
        """FAISS may return negative indices for missing results"""
        from dochris.vector.faiss_store import FAISSStore

        mock_index = MagicMock()
        mock_index.ntotal = 1
        mock_index.search.return_value = ([[0.1, 0.5]], [[0, -1]])

        store = FAISSStore(persist_directory=str(tmp_path))
        store._indexes["col"] = mock_index
        store._documents["col"] = {"id1": "doc1"}
        store._metadatas["col"] = {"id1": {}}

        mock_model = MagicMock()
        mock_model.encode.return_value.astype.return_value = MagicMock()
        store._model = mock_model

        mock_faiss = MagicMock()
        with patch.dict("sys.modules", {"faiss": mock_faiss}):
            results = store.query("col", "search text")

        assert len(results) == 1
        assert results[0]["id"] == "id1"

    def test_query_index_out_of_range(self, tmp_path):
        """Index returned by FAISS exceeds doc keys"""
        from dochris.vector.faiss_store import FAISSStore

        mock_index = MagicMock()
        mock_index.ntotal = 1
        mock_index.search.return_value = ([[0.1]], [[5]])  # idx 5 > len(docs)

        store = FAISSStore(persist_directory=str(tmp_path))
        store._indexes["col"] = mock_index
        store._documents["col"] = {"id1": "doc1"}
        store._metadatas["col"] = {"id1": {}}

        mock_model = MagicMock()
        mock_model.encode.return_value.astype.return_value = MagicMock()
        store._model = mock_model

        mock_faiss = MagicMock()
        with patch.dict("sys.modules", {"faiss": mock_faiss}):
            results = store.query("col", "search text")

        assert results == []


class TestFAISSStoreDelete:
    def test_delete_and_rebuild(self, tmp_path):
        from dochris.vector.faiss_store import FAISSStore

        mock_faiss = MagicMock()
        # IndexFlatL2 returns a mock index with numeric ntotal
        new_index = MagicMock()
        new_index.ntotal = 1
        mock_faiss.IndexFlatL2.return_value = new_index

        mock_model = MagicMock()
        mock_embedding = MagicMock()
        mock_embedding.shape = (1, 10)
        mock_model.encode.return_value.astype.return_value = mock_embedding

        store = FAISSStore(persist_directory=str(tmp_path))
        store._model = mock_model
        store._indexes["col"] = None  # Will trigger IndexFlatL2 creation
        store._documents["col"] = {"id1": "doc1", "id2": "doc2"}
        store._metadatas["col"] = {"id1": {}, "id2": {}}

        with patch.dict("sys.modules", {"faiss": mock_faiss}):
            store.delete("col", ["id1"])

        assert "id1" not in store._documents["col"]

    def test_delete_all_docs(self, tmp_path):
        from dochris.vector.faiss_store import FAISSStore

        store = FAISSStore(persist_directory=str(tmp_path))
        store._indexes["col"] = None
        store._documents["col"] = {"id1": "doc1"}
        store._metadatas["col"] = {"id1": {}}

        store.delete("col", ["id1"])
        assert store._documents["col"] == {}
        assert store._indexes["col"] is None


# ============================================================
# settings/config.py
# ============================================================
class TestSettingsFromEnv:
    def test_default_values(self, tmp_path, monkeypatch):
        """Settings with no env vars should use defaults"""
        from dochris.settings.config import Settings

        # Clear relevant env vars
        for var in ["WORKSPACE", "OPENAI_API_KEY", "OPENAI_API_BASE", "MODEL",
                     "SOURCE_PATH", "OBSIDIAN_VAULTS", "OBSIDIAN_VAULT"]:
            monkeypatch.delenv(var, raising=False)

        s = Settings.from_env(env_file=tmp_path / "nonexistent.env")
        assert s.model == "glm-5.1"
        assert s.api_key is None
        assert s.max_concurrency == 3
        assert s.min_quality_score == 85

    def test_from_env_with_workspace(self, tmp_path, monkeypatch):
        from dochris.settings.config import Settings

        monkeypatch.setenv("WORKSPACE", str(tmp_path))
        monkeypatch.delenv("SOURCE_PATH", raising=False)
        monkeypatch.delenv("OBSIDIAN_VAULTS", raising=False)
        monkeypatch.delenv("OBSIDIAN_VAULT", raising=False)
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("PLUGIN_DIRS", raising=False)
        monkeypatch.delenv("PLUGINS_ENABLED", raising=False)
        monkeypatch.delenv("PLUGINS_DISABLED", raising=False)

        s = Settings.from_env(env_file=tmp_path / "nonexistent.env")
        assert s.workspace == tmp_path

    def test_from_env_obsidian_vaults(self, tmp_path, monkeypatch):
        from dochris.settings.config import Settings

        monkeypatch.setenv("OBSIDIAN_VAULTS", f"{tmp_path}/vault1:{tmp_path}/vault2")
        monkeypatch.delenv("WORKSPACE", raising=False)
        monkeypatch.delenv("SOURCE_PATH", raising=False)
        monkeypatch.delenv("OBSIDIAN_VAULT", raising=False)
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("PLUGIN_DIRS", raising=False)
        monkeypatch.delenv("PLUGINS_ENABLED", raising=False)
        monkeypatch.delenv("PLUGINS_DISABLED", raising=False)

        s = Settings.from_env(env_file=tmp_path / "nonexistent.env")
        assert len(s.obsidian_vaults) == 2

    def test_from_env_single_obsidian_vault(self, tmp_path, monkeypatch):
        from dochris.settings.config import Settings

        monkeypatch.setenv("OBSIDIAN_VAULT", str(tmp_path / "single_vault"))
        monkeypatch.delenv("OBSIDIAN_VAULTS", raising=False)
        monkeypatch.delenv("WORKSPACE", raising=False)
        monkeypatch.delenv("SOURCE_PATH", raising=False)
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("PLUGIN_DIRS", raising=False)
        monkeypatch.delenv("PLUGINS_ENABLED", raising=False)
        monkeypatch.delenv("PLUGINS_DISABLED", raising=False)

        s = Settings.from_env(env_file=tmp_path / "nonexistent.env")
        assert len(s.obsidian_vaults) == 1

    def test_from_env_source_path(self, tmp_path, monkeypatch):
        from dochris.settings.config import Settings

        monkeypatch.setenv("SOURCE_PATH", str(tmp_path / "sources"))
        monkeypatch.delenv("WORKSPACE", raising=False)
        monkeypatch.delenv("OBSIDIAN_VAULTS", raising=False)
        monkeypatch.delenv("OBSIDIAN_VAULT", raising=False)
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("PLUGIN_DIRS", raising=False)
        monkeypatch.delenv("PLUGINS_ENABLED", raising=False)
        monkeypatch.delenv("PLUGINS_DISABLED", raising=False)

        s = Settings.from_env(env_file=tmp_path / "nonexistent.env")
        assert s.source_path == tmp_path / "sources"

    def test_from_env_plugins(self, monkeypatch, tmp_path):
        from dochris.settings.config import Settings

        monkeypatch.setenv("PLUGIN_DIRS", "/a:/b")
        monkeypatch.setenv("PLUGINS_ENABLED", "p1,p2")
        monkeypatch.setenv("PLUGINS_DISABLED", "p3")
        monkeypatch.delenv("WORKSPACE", raising=False)
        monkeypatch.delenv("SOURCE_PATH", raising=False)
        monkeypatch.delenv("OBSIDIAN_VAULTS", raising=False)
        monkeypatch.delenv("OBSIDIAN_VAULT", raising=False)
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)

        s = Settings.from_env(env_file=tmp_path / "nonexistent.env")
        assert len(s.plugin_dirs) == 2
        assert s.plugins_enabled == ["p1", "p2"]
        assert s.plugins_disabled == ["p3"]


class TestSettingsProperties:
    def test_path_properties(self, tmp_path):
        from dochris.settings.config import Settings

        s = Settings(workspace=tmp_path)
        assert s.logs_dir == tmp_path / "logs"
        assert s.cache_dir == tmp_path / "cache"
        assert s.outputs_dir == tmp_path / "outputs"
        assert s.raw_dir == tmp_path / "raw"
        assert s.wiki_dir == tmp_path / "wiki"
        assert s.wiki_summaries_dir == tmp_path / "wiki" / "summaries"
        assert s.wiki_concepts_dir == tmp_path / "wiki" / "concepts"
        assert s.curated_dir == tmp_path / "curated"
        assert s.curated_promoted_dir == tmp_path / "curated" / "promoted"
        assert s.manifests_dir == tmp_path / "manifests" / "sources"
        assert s.data_dir == tmp_path / "data"
        assert s.progress_file == tmp_path / "progress.json"
        assert s.phase2_lock_file == tmp_path / "phase2.lock"


class TestSettingsValidate:
    def test_validate_api_key_missing_with_openclaw_config(self, tmp_path, monkeypatch):
        from dochris.settings.config import Settings

        config_path = tmp_path / "openclaw.json"
        config_path.write_text("{}", encoding="utf-8")
        s = Settings(workspace=tmp_path, api_key=None, openclaw_config_path=config_path)
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)

        warnings = s.validate()
        assert any("OpenClaw" in w for w in warnings)

    def test_validate_api_key_missing_no_config(self, tmp_path, monkeypatch):
        from dochris.settings.config import Settings

        s = Settings(workspace=tmp_path, api_key=None, openclaw_config_path=tmp_path / "nonexistent.json")
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)

        warnings = s.validate()
        assert any("OPENAI_API_KEY" in w for w in warnings)

    def test_validate_empty_api_base(self, tmp_path, monkeypatch):
        from dochris.settings.config import Settings

        s = Settings(workspace=tmp_path, api_key="test", api_base="  ")
        monkeypatch.setenv("OPENAI_API_KEY", "test")

        with pytest.raises(ValueError, match="api_base"):
            s.validate()

    def test_validate_empty_model(self, tmp_path, monkeypatch):
        from dochris.settings.config import Settings

        s = Settings(workspace=tmp_path, api_key="test", api_base="http://x", model="  ")
        monkeypatch.setenv("OPENAI_API_KEY", "test")

        with pytest.raises(ValueError, match="model"):
            s.validate()

    def test_validate_success(self, tmp_path, monkeypatch):
        from dochris.settings.config import Settings

        s = Settings(workspace=tmp_path, api_key="sk-test", api_base="http://api.test.com")
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")

        warnings = s.validate()
        assert warnings == []

    def test_validate_api_key_method(self, tmp_path, monkeypatch):
        from dochris.settings.config import Settings

        s = Settings(workspace=tmp_path, api_key="sk-mykey")
        assert s.validate_api_key() == "sk-mykey"

    def test_validate_api_key_missing_raises(self, tmp_path, monkeypatch):
        from dochris.settings.config import Settings

        s = Settings(workspace=tmp_path, api_key=None)
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)

        with pytest.raises(ValueError, match="OPENAI_API_KEY"):
            s.validate_api_key()


class TestGetResetSettings:
    def test_get_settings_returns_instance(self, tmp_path, monkeypatch):
        from dochris.settings.config import get_settings, reset_settings

        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        try:
            s = get_settings(reload=True)
            assert s is not None
            assert hasattr(s, "workspace")
        finally:
            reset_settings()

    def test_reset_settings(self, monkeypatch):
        from dochris.settings import config as cfg_module

        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        cfg_module.reset_settings()
        assert cfg_module._global_settings is None
