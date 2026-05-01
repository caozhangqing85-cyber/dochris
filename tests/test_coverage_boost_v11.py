"""覆盖率提升 v11 — vault/bridge.py + vector/base.py + vector/__init__"""

from unittest.mock import MagicMock, patch

import pytest


# ============================================================
# vault/bridge.py
# ============================================================
class TestCleanInternalReferences:
    """测试 clean_internal_references 函数"""

    def test_src_reference_conversion(self):
        from dochris.vault.bridge import clean_internal_references

        content = "参考 (SRC-0001) 和 (SRC-0042)"
        result = clean_internal_references(content)
        assert "📚 来源: SRC-0001" in result
        assert "📚 来源: SRC-0042" in result
        assert "(SRC-" not in result

    def test_remove_metadata_block_single_line(self):
        """正则只匹配单行元数据块"""
        from dochris.vault.bridge import clean_internal_references

        content = "---\ncreated: 2024-01-01\n---\n正文内容"
        result = clean_internal_references(content)
        assert "created:" not in result
        assert "正文内容" in result

    def test_multi_line_metadata_not_removed(self):
        """多行元数据块不会被移除（正则限制）"""
        from dochris.vault.bridge import clean_internal_references

        content = "---\ncreated: 2024-01-01\nstatus: ok\n---\n正文内容"
        result = clean_internal_references(content)
        assert "created:" in result  # 多行块不会被移除
        assert "正文内容" in result

    def test_remove_compile_timestamp(self):
        from dochris.vault.bridge import clean_internal_references

        content = "> 编译时间：2024-01-01 12:00:00\n正文"
        result = clean_internal_references(content)
        assert "编译时间" not in result
        assert "正文" in result

    def test_collapse_blank_lines(self):
        from dochris.vault.bridge import clean_internal_references

        content = "a\n\n\n\n\nb"
        result = clean_internal_references(content)
        assert "a\n\nb" == result

    def test_strip_whitespace(self):
        from dochris.vault.bridge import clean_internal_references

        content = "  hello  \n\n"
        result = clean_internal_references(content)
        assert result == "hello"

    def test_preserve_wikilinks(self):
        from dochris.vault.bridge import clean_internal_references

        content = "参见 [[concept-name]] 了解更多"
        result = clean_internal_references(content)
        assert "[[concept-name]]" in result


class TestComputeHash:
    def test_hash_deterministic(self):
        from dochris.vault.bridge import _compute_hash

        h1 = _compute_hash("hello")
        h2 = _compute_hash("hello")
        assert h1 == h2
        assert len(h1) == 64  # SHA-256 hex

    def test_hash_different_input(self):
        from dochris.vault.bridge import _compute_hash

        h1 = _compute_hash("hello")
        h2 = _compute_hash("world")
        assert h1 != h2


class TestSearchObsidianNotes:
    @patch("dochris.vault.bridge._get_obsidian_vault")
    def test_no_vault_configured(self, mock_vault):
        from dochris.vault.bridge import _search_obsidian_notes

        mock_vault.return_value = None
        result = _search_obsidian_notes("test")
        assert result == []

    @patch("dochris.vault.bridge._get_obsidian_vault")
    def test_vault_not_exists(self, mock_vault, tmp_path):
        from dochris.vault.bridge import _search_obsidian_notes

        mock_vault.return_value = tmp_path / "nonexistent"
        result = _search_obsidian_notes("test")
        assert result == []

    @patch("dochris.vault.bridge._get_obsidian_vault")
    def test_filename_match(self, mock_vault, tmp_path):
        from dochris.vault.bridge import _search_obsidian_notes

        vault = tmp_path / "vault"
        vault.mkdir()
        (vault / "machine_learning.md").write_text("# ML", encoding="utf-8")
        mock_vault.return_value = vault

        result = _search_obsidian_notes("machine")
        assert len(result) == 1
        assert result[0]["match_type"] == "filename"

    @patch("dochris.vault.bridge._get_obsidian_vault")
    def test_content_match(self, mock_vault, tmp_path):
        from dochris.vault.bridge import _search_obsidian_notes

        vault = tmp_path / "vault"
        vault.mkdir()
        (vault / "notes.md").write_text("深度学习是人工智能的分支", encoding="utf-8")
        mock_vault.return_value = vault

        result = _search_obsidian_notes("深度学习")
        assert len(result) == 1
        assert result[0]["match_type"] == "content"

    @patch("dochris.vault.bridge._get_obsidian_vault")
    def test_skip_hidden_dirs(self, mock_vault, tmp_path):
        from dochris.vault.bridge import _search_obsidian_notes

        vault = tmp_path / "vault"
        vault.mkdir()
        hidden = vault / ".obsidian"
        hidden.mkdir()
        (hidden / "config.md").write_text("test keyword", encoding="utf-8")
        mock_vault.return_value = vault

        result = _search_obsidian_notes("keyword")
        assert len(result) == 0

    @patch("dochris.vault.bridge._get_obsidian_vault")
    def test_filename_priority_over_content(self, mock_vault, tmp_path):
        from dochris.vault.bridge import _search_obsidian_notes

        vault = tmp_path / "vault"
        vault.mkdir()
        (vault / "python_basics.md").write_text("python keyword here", encoding="utf-8")
        (vault / "other.md").write_text("python is great", encoding="utf-8")
        mock_vault.return_value = vault

        result = _search_obsidian_notes("python")
        # filename match should come first
        assert result[0]["match_type"] == "filename"
        assert result[0]["title"] == "python_basics"


class TestSeedFromObsidian:
    @patch("dochris.vault.bridge.append_log")
    @patch("dochris.vault.bridge.append_to_index")
    @patch("dochris.vault.bridge.create_manifest")
    @patch("dochris.vault.bridge.get_next_src_id")
    @patch("dochris.vault.bridge.get_all_manifests")
    @patch("dochris.vault.bridge._search_obsidian_notes")
    def test_seed_success(
        self, mock_search, mock_all, mock_next_id, mock_create, mock_append, mock_log, tmp_path
    ):
        from dochris.vault.bridge import seed_from_obsidian

        vault = tmp_path / "vault"
        vault.mkdir()
        note = vault / "test_note.md"
        note.write_text("# Test Note Content", encoding="utf-8")

        mock_search.return_value = [
            {"path": note, "rel_path": "test_note.md", "title": "test_note", "match_type": "filename"}
        ]
        mock_all.return_value = []
        mock_next_id.return_value = "SRC-0001"
        mock_create.return_value = {"id": "SRC-0001", "title": "test_note"}

        result = seed_from_obsidian(tmp_path, "test")
        assert len(result) == 1
        assert result[0]["src_id"] == "SRC-0001"

    @patch("dochris.vault.bridge._search_obsidian_notes")
    def test_seed_no_notes(self, mock_search, tmp_path):
        from dochris.vault.bridge import seed_from_obsidian

        mock_search.return_value = []
        result = seed_from_obsidian(tmp_path, "nothing")
        assert result == []

    @patch("dochris.vault.bridge._search_obsidian_notes")
    def test_seed_duplicate_skipped(self, mock_search, tmp_path):
        from dochris.vault.bridge import seed_from_obsidian
        import hashlib

        vault = tmp_path / "vault"
        vault.mkdir()
        note = vault / "dup.md"
        note.write_text("duplicate content", encoding="utf-8")
        content_hash = hashlib.sha256(b"duplicate content").hexdigest()

        mock_search.return_value = [
            {"path": note, "rel_path": "dup.md", "title": "dup", "match_type": "filename"}
        ]
        mock_all_return = [{"content_hash": content_hash}]

        with patch("dochris.vault.bridge.get_all_manifests", return_value=mock_all_return):
            result = seed_from_obsidian(tmp_path, "dup")
        assert result == []

    @patch("dochris.vault.bridge._search_obsidian_notes")
    def test_seed_read_error(self, mock_search, tmp_path):
        from dochris.vault.bridge import seed_from_obsidian

        mock_search.return_value = [
            {"path": tmp_path / "nonexistent.md", "rel_path": "nonexistent.md", "title": "x", "match_type": "filename"}
        ]
        with patch("dochris.vault.bridge.get_all_manifests", return_value=[]):
            result = seed_from_obsidian(tmp_path, "x")
        assert result == []


class TestPromoteToObsidian:
    @patch("dochris.vault.bridge.get_manifest")
    def test_manifest_not_found(self, mock_get, tmp_path):
        from dochris.vault.bridge import promote_to_obsidian

        mock_get.return_value = None
        assert promote_to_obsidian(tmp_path, "SRC-0001") is False

    @patch("dochris.vault.bridge.get_manifest")
    def test_wrong_status(self, mock_get, tmp_path):
        from dochris.vault.bridge import promote_to_obsidian

        mock_get.return_value = {"status": "compiled", "title": "test"}
        assert promote_to_obsidian(tmp_path, "SRC-0001") is False

    @patch("dochris.vault.bridge.get_manifest")
    def test_no_title(self, mock_get, tmp_path):
        from dochris.vault.bridge import promote_to_obsidian

        mock_get.return_value = {"status": "promoted", "title": ""}
        assert promote_to_obsidian(tmp_path, "SRC-0001") is False

    @patch("dochris.vault.bridge.get_manifest")
    def test_source_file_not_found(self, mock_get, tmp_path):
        from dochris.vault.bridge import promote_to_obsidian

        mock_get.return_value = {"status": "promoted", "title": "nonexistent_test"}
        assert promote_to_obsidian(tmp_path, "SRC-0001") is False

    @patch("dochris.vault.bridge._get_obsidian_vault")
    @patch("dochris.vault.bridge.get_manifest")
    def test_vault_not_configured(self, mock_get, mock_vault, tmp_path):
        from dochris.vault.bridge import promote_to_obsidian

        mock_get.return_value = {"status": "promoted", "title": "test_title"}
        mock_vault.return_value = None

        # Create the source file
        wiki_summ = tmp_path / "wiki" / "summaries"
        wiki_summ.mkdir(parents=True)
        (wiki_summ / "test_title.md").write_text("content", encoding="utf-8")

        assert promote_to_obsidian(tmp_path, "SRC-0001") is False

    @patch("dochris.vault.bridge.append_log")
    @patch("dochris.manifest.update_manifest_status")
    @patch("dochris.vault.bridge._get_obsidian_vault")
    @patch("dochris.vault.bridge.get_manifest")
    def test_promote_success(self, mock_get, mock_vault, mock_update, mock_log, tmp_path):
        from dochris.vault.bridge import promote_to_obsidian

        mock_get.return_value = {"status": "promoted", "title": "good_title"}
        obsidian = tmp_path / "obsidian_vault"
        obsidian.mkdir()
        mock_vault.return_value = obsidian

        # Create source file
        curated = tmp_path / "curated" / "promoted"
        curated.mkdir(parents=True)
        (curated / "good_title.md").write_text("# Good content", encoding="utf-8")

        result = promote_to_obsidian(tmp_path, "SRC-0001")
        assert result is True
        target = obsidian / "06-知识库" / "good_title.md"
        assert target.exists()

    @patch("dochris.vault.bridge._get_obsidian_vault")
    @patch("dochris.vault.bridge.get_manifest")
    def test_promote_to_wiki_status(self, mock_get, mock_vault, tmp_path):
        from dochris.vault.bridge import promote_to_obsidian

        mock_get.return_value = {"status": "promoted_to_wiki", "title": "wiki_test"}
        obsidian = tmp_path / "obsidian_vault"
        obsidian.mkdir()
        mock_vault.return_value = obsidian

        wiki = tmp_path / "wiki" / "summaries"
        wiki.mkdir(parents=True)
        (wiki / "wiki_test.md").write_text("wiki content", encoding="utf-8")

        with patch("dochris.manifest.update_manifest_status"), \
             patch("dochris.vault.bridge.append_log"):
            result = promote_to_obsidian(tmp_path, "SRC-0001")
        assert result is True


class TestListAssociatedNotes:
    @patch("dochris.vault.bridge.get_manifest")
    def test_manifest_not_found(self, mock_get, tmp_path):
        from dochris.vault.bridge import list_associated_notes

        mock_get.return_value = None
        result = list_associated_notes(tmp_path, "SRC-0001")
        assert result == []

    @patch("dochris.vault.bridge.get_manifest")
    def test_no_title(self, mock_get, tmp_path):
        from dochris.vault.bridge import list_associated_notes

        mock_get.return_value = {"title": ""}
        result = list_associated_notes(tmp_path, "SRC-0001")
        assert result == []

    @patch("dochris.vault.bridge._search_obsidian_notes")
    @patch("dochris.vault.bridge.get_manifest")
    def test_list_success(self, mock_get, mock_search, tmp_path):
        from dochris.vault.bridge import list_associated_notes

        mock_get.return_value = {"title": "机器学习入门"}
        mock_search.return_value = [
            {"path": "/some/path.md", "rel_path": "path.md", "title": "path", "match_type": "filename"}
        ]
        result = list_associated_notes(tmp_path, "SRC-0001")
        assert len(result) == 1

    @patch("dochris.vault.bridge._search_obsidian_notes")
    @patch("dochris.vault.bridge.get_manifest")
    def test_no_associated_notes(self, mock_get, mock_search, tmp_path):
        from dochris.vault.bridge import list_associated_notes

        mock_get.return_value = {"title": "test query"}
        mock_search.return_value = []
        result = list_associated_notes(tmp_path, "SRC-0001")
        assert result == []


class TestBridgeMain:
    def test_main_too_few_args(self):
        from dochris.vault.bridge import main

        with patch("sys.argv", ["bridge.py"]), \
             pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 1

    @patch("dochris.vault.bridge.seed_from_obsidian")
    def test_main_seed(self, mock_seed):
        from dochris.vault.bridge import main

        mock_seed.return_value = [{"src_id": "SRC-0001"}]
        with patch("sys.argv", ["bridge.py", "/tmp/ws", "seed", "topic"]), \
             pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 0

    @patch("dochris.vault.bridge.promote_to_obsidian")
    def test_main_promote(self, mock_promote):
        from dochris.vault.bridge import main

        mock_promote.return_value = True
        with patch("sys.argv", ["bridge.py", "/tmp/ws", "promote", "SRC-0001"]), \
             pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 0

    @patch("dochris.vault.bridge.list_associated_notes")
    def test_main_list(self, mock_list):
        from dochris.vault.bridge import main

        mock_list.return_value = [{"title": "note"}]
        with patch("sys.argv", ["bridge.py", "/tmp/ws", "list", "SRC-0001"]), \
             pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 0

    def test_main_unknown_action(self):
        from dochris.vault.bridge import main

        with patch("sys.argv", ["bridge.py", "/tmp/ws", "unknown", "arg"]), \
             pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 1


# ============================================================
# vector/base.py
# ============================================================
class TestBaseVectorStore:
    def test_cannot_instantiate_abstract(self):
        from dochris.vector.base import BaseVectorStore

        with pytest.raises(TypeError):
            BaseVectorStore()

    def test_collection_exists_true(self):
        from dochris.vector.base import BaseVectorStore

        class ConcreteStore(BaseVectorStore):
            name = "test"

            def add_documents(self, collection, documents, ids, metadatas=None):
                pass

            def query(self, collection, query_text, n_results=5, where=None, **kwargs):
                return []

            def delete(self, collection, ids):
                pass

            def list_collections(self):
                return ["col_a", "col_b"]

            def get_collection_count(self, collection):
                return 0

        store = ConcreteStore()
        assert store.collection_exists("col_a") is True
        assert store.collection_exists("col_missing") is False

    def test_repr(self):
        from dochris.vector.base import BaseVectorStore

        class ConcreteStore(BaseVectorStore):
            name = "my_store"

            def add_documents(self, collection, documents, ids, metadatas=None):
                pass

            def query(self, collection, query_text, n_results=5, where=None, **kwargs):
                return []

            def delete(self, collection, ids):
                pass

            def list_collections(self):
                return []

            def get_collection_count(self, collection):
                return 0

        store = ConcreteStore()
        assert repr(store) == "ConcreteStore(name='my_store')"


# ============================================================
# vector/__init__.py
# ============================================================
class TestVectorInit:
    def test_get_store_chromadb(self):
        from dochris.vector import get_store

        store_cls = get_store("chromadb")
        assert store_cls.name == "chromadb"

    def test_get_store_unknown(self):
        from dochris.vector import get_store

        with pytest.raises(ValueError, match="Unknown vector store"):
            get_store("nonexistent")

    def test_stores_registry(self):
        from dochris.vector import STORES

        assert "chromadb" in STORES
