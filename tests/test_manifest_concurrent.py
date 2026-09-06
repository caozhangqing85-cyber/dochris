"""manifest SRC-ID 跨进程原子分配 + delete 死锁回归测试。"""

from __future__ import annotations

import subprocess
import sys
import threading
from pathlib import Path

import pytest

from dochris.manifest import create_manifest, delete_manifest, get_all_manifests

pytestmark = pytest.mark.fast

_WORKER_SNIPPET = """
import sys
from pathlib import Path

sys.path.insert(0, {src!r})
from dochris.manifest import create_manifest

workspace, count = sys.argv[1], int(sys.argv[2])
for i in range(count):
    create_manifest(
        workspace,
        src_id=None,  # 并发安全路径：锁内自动分配
        title=f"doc-{{i}}.md",
        file_type="other",
        source_path=Path(workspace) / f"virtual-{{i}}.md",
        file_path=f"raw/virtual-{{i}}.md",
        content_hash=f"hash-{{i}}",
        size_bytes=10,
    )
"""


def test_concurrent_processes_allocate_unique_src_ids(tmp_path: Path) -> None:
    """两个真实进程并发创建 manifest：ID 必须唯一、无覆盖（P1 回归）。"""
    src_root = Path(__file__).resolve().parent.parent / "src"
    workers = 2
    per_worker = 8

    procs = [
        subprocess.Popen(
            [
                sys.executable,
                "-c",
                _WORKER_SNIPPET.format(src=str(src_root), count=per_worker),
                str(tmp_path),
                str(per_worker),
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        for _ in range(workers)
    ]
    errors = []
    for proc in procs:
        _, err = proc.communicate(timeout=60)
        if proc.returncode != 0:
            errors.append(err.decode())

    assert not errors, f"worker 失败: {errors}"

    manifests = get_all_manifests(tmp_path)
    ids = [m["id"] for m in manifests]

    assert len(ids) == workers * per_worker, "manifest 数量必须等于创建次数（无覆盖）"
    assert len(set(ids)) == len(ids), f"SRC-ID 出现重复: {sorted(ids)}"

    on_disk = sorted((tmp_path / "manifests" / "sources").glob("SRC-*.json"))
    assert len(on_disk) == len(ids)
    rows = (tmp_path / "manifests" / "source_index.csv").read_text(encoding="utf-8")
    for sid in ids:
        assert sid in rows


def test_same_process_threads_allocate_unique_src_ids(tmp_path: Path) -> None:
    """进程内多线程并发（上传路由的线程池场景）。"""
    barrier = threading.Barrier(6)
    created: list[str] = []
    lock = threading.Lock()

    def worker(i: int) -> None:
        barrier.wait()
        manifest = create_manifest(
            tmp_path,
            src_id=None,
            title=f"t{i}.md",
            file_type="other",
            source_path=tmp_path / f"t{i}.md",
            file_path=f"raw/t{i}.md",
            content_hash=f"h{i}",
            size_bytes=1,
        )
        with lock:
            created.append(manifest["id"])

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(6)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(created) == 6
    assert len(set(created)) == 6


def test_create_manifest_with_explicit_id_still_works(tmp_path: Path) -> None:
    """显式 src_id 的既有调用方保持兼容。"""
    manifest = create_manifest(
        tmp_path,
        src_id="SRC-0042",
        title="doc",
        file_type="other",
        source_path=tmp_path / "doc.md",
        file_path="raw/doc.md",
        content_hash="h",
        size_bytes=1,
    )
    assert manifest["id"] == "SRC-0042"
    assert (tmp_path / "manifests" / "sources" / "SRC-0042.json").exists()


def test_delete_manifest_does_not_deadlock_and_updates_index(tmp_path: Path) -> None:
    """P1 回归：delete 在持锁状态下重建索引曾自死锁；必须能在超时内完成且 CSV 同步。"""
    manifest = create_manifest(
        tmp_path,
        src_id=None,
        title="待删除.md",
        file_type="other",
        source_path=tmp_path / "待删除.md",
        file_path="raw/待删除.md",
        content_hash="deadbeef",
        size_bytes=1,
    )
    result: dict[str, object] = {}

    def try_delete() -> None:
        result["ok"] = delete_manifest(tmp_path, manifest["id"])

    thread = threading.Thread(target=try_delete, daemon=True)
    thread.start()
    thread.join(timeout=4)
    assert not thread.is_alive(), "delete_manifest 死锁（4s 未完成）"
    assert result.get("ok") is True

    assert not (tmp_path / "manifests" / "sources" / f"{manifest['id']}.json").exists()
    rows = (tmp_path / "manifests" / "source_index.csv").read_text(encoding="utf-8")
    assert manifest["id"] not in rows, "CSV 必须同步移除该条目"


def test_delete_manifest_returns_false_when_index_rebuild_fails(tmp_path: Path) -> None:
    """索引重建失败不得谎报删除成功。"""
    from unittest.mock import patch

    manifest = create_manifest(
        tmp_path,
        src_id=None,
        title="x.md",
        file_type="other",
        source_path=tmp_path / "x.md",
        file_path="raw/x.md",
        content_hash="h",
        size_bytes=1,
    )

    with patch("dochris.manifest._rebuild_index_unlocked", side_effect=OSError("disk full")):
        ok = delete_manifest(tmp_path, manifest["id"])

    assert ok is False
