"""Contracts for the optional LEANN vector-store adapter."""

from __future__ import annotations

import json
import sys
from types import ModuleType, SimpleNamespace
from unittest.mock import MagicMock, call, patch

import pytest

from dochris.vector.leann_store import LeannStore


def _fake_leann() -> tuple[ModuleType, MagicMock, MagicMock]:
    module = ModuleType("leann")
    builder_class = MagicMock(name="LeannBuilder")
    searcher_class = MagicMock(name="LeannSearcher")
    module.LeannBuilder = builder_class  # type: ignore[attr-defined]
    module.LeannSearcher = searcher_class  # type: ignore[attr-defined]
    return module, builder_class, searcher_class


@pytest.mark.fast
def test_add_documents_uses_current_leann_builder_api_and_preserves_metadata(tmp_path) -> None:
    module, builder_class, _ = _fake_leann()
    builder = builder_class.return_value
    store = LeannStore(index_dir=tmp_path)

    with patch.dict(sys.modules, {"leann": module}):
        store.add_documents(
            "articles",
            ["first", "second"],
            ["doc-1", "doc-2"],
            [{"topic": "alpha"}, {"topic": "beta"}],
        )

    builder_class.assert_called_once_with(
        backend_name="hnsw",
        embedding_mode="sentence-transformers",
        embedding_model="BAAI/bge-small-zh-v1.5",
        graph_degree=32,
        build_complexity=64,
    )
    assert builder.add_text.call_args_list == [
        call("first", metadata={"topic": "alpha", "id": "doc-1"}),
        call("second", metadata={"topic": "beta", "id": "doc-2"}),
    ]
    builder.build_index.assert_called_once_with(str(tmp_path / "articles" / "index"))


@pytest.mark.fast
def test_add_documents_validates_metadata_length(tmp_path) -> None:
    store = LeannStore(index_dir=tmp_path)

    with pytest.raises(ValueError, match="metadatas.*documents.*length mismatch"):
        store.add_documents("articles", ["first", "second"], ["doc-1", "doc-2"], [{}])


@pytest.mark.fast
def test_add_documents_reports_installable_extra_when_leann_is_missing(tmp_path) -> None:
    store = LeannStore(index_dir=tmp_path)

    with patch.dict(sys.modules, {"leann": None}):
        with pytest.raises(ImportError, match=r"pip install 'dochris\[leann\]'"):
            store.add_documents("articles", ["first"], ["doc-1"])


@pytest.mark.fast
def test_query_uses_current_search_api_and_maps_search_result_objects(tmp_path) -> None:
    module, _, searcher_class = _fake_leann()
    index_path = tmp_path / "articles" / "index"
    index_path.parent.mkdir(parents=True)
    index_path.with_suffix(".meta.json").write_text("{}", encoding="utf-8")
    searcher_class.return_value.search.return_value = [
        SimpleNamespace(
            id="doc-1",
            score=0.125,
            text="first",
            metadata={"id": "doc-1", "topic": "alpha"},
        )
    ]
    store = LeannStore(index_dir=tmp_path, search_complexity=17, recompute=False)

    with patch.dict(sys.modules, {"leann": module}):
        results = store.query("articles", "needle", n_results=2, where={"topic": "alpha"})

    # PyPI's leann-core 0.3.4 accepts recompute_embeddings on search(), while
    # newer 0.3.x releases also support it there as a deprecated compatibility
    # override. Keep construction backend-agnostic across both API shapes.
    searcher_class.assert_called_once_with(str(index_path))
    searcher_class.return_value.search.assert_called_once_with(
        "needle",
        top_k=2,
        complexity=17,
        recompute_embeddings=False,
        metadata_filters={"topic": "alpha"},
    )
    assert results == [
        {
            "id": "doc-1",
            "document": "first",
            "metadata": {"topic": "alpha"},
            "distance": 0.125,
        }
    ]


@pytest.mark.fast
def test_registry_migrates_old_text_only_shape_and_delete_rebuilds_current_api(tmp_path) -> None:
    module, builder_class, _ = _fake_leann()
    collection_dir = tmp_path / "articles"
    collection_dir.mkdir(parents=True)
    (collection_dir / "_registry.json").write_text(
        json.dumps({"doc-1": "first", "doc-2": "second"}),
        encoding="utf-8",
    )
    store = LeannStore(index_dir=tmp_path)

    with patch.dict(sys.modules, {"leann": module}):
        store.delete("articles", ["doc-1"])

    builder = builder_class.return_value
    builder.add_text.assert_called_once_with("second", metadata={"id": "doc-2"})
    builder.build_index.assert_called_once_with(str(collection_dir / "index"))
    assert json.loads((collection_dir / "_registry.json").read_text(encoding="utf-8")) == {
        "doc-2": {"text": "second", "metadata": {}}
    }


@pytest.mark.fast
def test_delete_last_document_removes_index_files_and_collection(tmp_path) -> None:
    collection_dir = tmp_path / "articles"
    collection_dir.mkdir(parents=True)
    (collection_dir / "_registry.json").write_text(
        json.dumps({"doc-1": {"text": "first", "metadata": {}}}),
        encoding="utf-8",
    )
    for name in ("index.meta.json", "index.passages.jsonl", "index.passages.idx"):
        (collection_dir / name).write_text("data", encoding="utf-8")
    store = LeannStore(index_dir=tmp_path)

    store.delete("articles", ["doc-1"])

    assert not list(collection_dir.glob("index*"))
    assert store.list_collections() == []
    assert store.get_collection_count("articles") == 0


@pytest.mark.fast
def test_list_collections_recognizes_current_leann_metadata_path(tmp_path) -> None:
    collection_dir = tmp_path / "articles"
    collection_dir.mkdir(parents=True)
    (collection_dir / "index.meta.json").write_text("{}", encoding="utf-8")
    store = LeannStore(index_dir=tmp_path)

    assert store.list_collections() == ["articles"]
