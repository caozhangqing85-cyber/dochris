"""API 测试公共 fixture"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from dochris.api.app import create_app


@pytest.fixture
def client() -> TestClient:
    """创建测试客户端"""
    app = create_app()
    return TestClient(app)


@pytest.fixture
def tmp_workspace(tmp_path: Path) -> Path:
    """创建临时工作区"""
    manifests_dir = tmp_path / "manifests" / "sources"
    manifests_dir.mkdir(parents=True)
    (tmp_path / "raw").mkdir()
    (tmp_path / "outputs" / "summaries").mkdir(parents=True)
    (tmp_path / "outputs" / "concepts").mkdir(parents=True)
    (tmp_path / "wiki" / "summaries").mkdir(parents=True)
    (tmp_path / "wiki" / "concepts").mkdir(parents=True)
    (tmp_path / "curated" / "promoted").mkdir(parents=True)
    return tmp_path


def _make_manifest(
    src_id: str = "SRC-0001",
    title: str = "测试文档",
    file_type: str = "pdf",
    status: str = "compiled",
    quality_score: int = 90,
) -> dict:
    """创建测试用 manifest"""
    return {
        "id": src_id,
        "title": title,
        "type": file_type,
        "source_path": f"/fake/{title}.pdf",
        "file_path": f"raw/pdfs/{title}.pdf",
        "content_hash": f"hash_{src_id}",
        "date_ingested": "2026-01-01",
        "status": status,
        "quality_score": quality_score,
        "error_message": None,
        "promoted_to": None,
        "tags": [],
    }


def _write_manifest(workspace: Path, manifest: dict) -> Path:
    """写入 manifest 文件"""
    manifests_dir = workspace / "manifests" / "sources"
    path = manifests_dir / f"{manifest['id']}.json"
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return path
