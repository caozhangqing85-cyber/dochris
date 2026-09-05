"""Real ChromaDB persistence checks using deterministic local embeddings."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest


class _DeterministicEmbeddingFunction:
    """Small offline embedding function for testing Chroma itself, not a model."""

    def __init__(self) -> None:
        pass

    def __call__(self, input: list[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for text in input:
            if "量子" in text:
                vectors.append([1.0, 0.0, 0.0])
            elif "烹饪" in text:
                vectors.append([0.0, 1.0, 0.0])
            else:
                vectors.append([0.0, 0.0, 1.0])
        return vectors

    def embed_query(self, input: list[str]) -> list[list[float]]:
        return self(input)

    @staticmethod
    def name() -> str:
        return "dochris_deterministic_test_embedding"

    @staticmethod
    def build_from_config(_config: dict[str, Any]) -> _DeterministicEmbeddingFunction:
        return _DeterministicEmbeddingFunction()

    def get_config(self) -> dict[str, Any]:
        return {}


def _run_isolated_chromadb_child(persist_directory: Path) -> dict[str, Any]:
    """Run the real backend outside pytest's process-wide module mocks."""
    from dochris.vector.chromadb_store import ChromaDBStore

    store = ChromaDBStore(persist_directory=persist_directory)
    store._ef = _DeterministicEmbeddingFunction()
    store.add_documents(
        "knowledge",
        ["量子计算使用量子比特", "烹饪需要控制火候"],
        ["quantum", "cooking"],
        [{"topic": "physics"}, {"topic": "food"}],
    )

    collections = store.list_collections()
    collection_count = store.get_collection_count("knowledge")
    results = store.query("knowledge", "量子原理", n_results=2)
    store.update_metadata("knowledge", ["quantum"], [{"topic": "physics", "reviewed": True}])
    store.close()

    sqlite_exists = (persist_directory / "chroma.sqlite3").is_file()
    reopened = ChromaDBStore(persist_directory=persist_directory)
    reopened._ef = _DeterministicEmbeddingFunction()
    persisted = reopened.query(
        "knowledge",
        "量子原理",
        n_results=1,
        where={"reviewed": True},
    )
    reopened.delete("knowledge", ["quantum"])
    remaining_count = reopened.get_collection_count("knowledge")
    reopened.close()

    return {
        "collections": collections,
        "collection_count": collection_count,
        "results": results,
        "sqlite_exists": sqlite_exists,
        "persisted": persisted,
        "remaining_count": remaining_count,
    }


@pytest.mark.integration
def test_chromadb_persistence_against_real_client(tmp_path: Path) -> None:
    """Exercise the real Chroma client, SQLite persistence, query, and delete path."""
    repo_root = Path(__file__).resolve().parents[1]
    env = os.environ.copy()
    env["ANONYMIZED_TELEMETRY"] = "False"
    env["DOCHRIS_CHROMADB_E2E_ROOT"] = str(tmp_path / "chroma")
    env["PYTHONPATH"] = os.pathsep.join(
        part for part in (str(repo_root / "src"), env.get("PYTHONPATH", "")) if part
    )
    completed = subprocess.run(
        [sys.executable, str(Path(__file__).resolve()), "--child"],
        cwd=repo_root,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )

    assert completed.returncode == 0, f"stdout:\n{completed.stdout}\nstderr:\n{completed.stderr}"
    evidence = json.loads(completed.stdout.strip().splitlines()[-1])
    assert evidence["collections"] == ["knowledge"]
    assert evidence["collection_count"] == 2
    assert [result["id"] for result in evidence["results"]] == ["quantum", "cooking"]
    assert evidence["results"][0]["metadata"] == {"topic": "physics"}
    assert evidence["results"][0]["distance"] == pytest.approx(0.0)
    assert evidence["sqlite_exists"] is True
    assert evidence["persisted"] == [
        {
            "id": "quantum",
            "document": "量子计算使用量子比特",
            "metadata": {"topic": "physics", "reviewed": True},
            "distance": pytest.approx(0.0),
        }
    ]
    assert evidence["remaining_count"] == 1


if __name__ == "__main__" and sys.argv[-1:] == ["--child"]:
    result = _run_isolated_chromadb_child(Path(os.environ["DOCHRIS_CHROMADB_E2E_ROOT"]).resolve())
    print(json.dumps(result, ensure_ascii=False))
