"""数据身份模型测试（DATA-01/DATA-03）。"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from dochris.core.identity import canonical_document_id, canonical_source_path
from dochris.manifest import create_manifest, find_manifest_by_content_hash

pytestmark = pytest.mark.fast


def test_canonical_path_is_stable_across_symlinks(tmp_path: Path) -> None:
    real = tmp_path / "real.txt"
    real.write_text("x", encoding="utf-8")
    link = tmp_path / "link.txt"
    link.symlink_to(real)

    assert canonical_source_path(link) == canonical_source_path(real)


def test_canonical_document_id_is_deterministic_hex16() -> None:
    first = canonical_document_id("/tmp/dochris-sample/doc.pdf")
    second = canonical_document_id("/tmp/dochris-sample/doc.pdf")

    assert first == second
    assert len(first) == 16
    int(first, 16)  # 必须是十六进制


def test_create_manifest_records_canonical_id(tmp_path: Path) -> None:
    source = tmp_path / "raw" / "doc.md"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_text("内容", encoding="utf-8")

    manifest = create_manifest(
        workspace_path=tmp_path,
        src_id="SRC-0001",
        title="doc",
        file_type="other",
        source_path=source.resolve(),
        file_path="raw/doc.md",
        content_hash="abc123",
    )

    assert manifest["canonical_id"] == canonical_document_id(source.resolve())
    stored = json.loads(
        (tmp_path / "manifests" / "sources" / "SRC-0001.json").read_text(encoding="utf-8")
    )
    assert stored["canonical_id"] == manifest["canonical_id"]


def test_find_manifest_by_content_hash_supports_ingest_idempotency(tmp_path: Path) -> None:
    source = tmp_path / "raw" / "doc.md"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_text("内容", encoding="utf-8")
    create_manifest(
        workspace_path=tmp_path,
        src_id="SRC-0001",
        title="doc",
        file_type="other",
        source_path=source.resolve(),
        file_path="raw/doc.md",
        content_hash="deadbeef",
    )

    hit = find_manifest_by_content_hash(tmp_path, "deadbeef")
    assert hit is not None
    assert hit["id"] == "SRC-0001"

    assert find_manifest_by_content_hash(tmp_path, "missing-hash") is None
    # 空哈希直接返回 None，不做全量扫描
    assert find_manifest_by_content_hash(tmp_path, "") is None
