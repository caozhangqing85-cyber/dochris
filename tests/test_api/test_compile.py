"""编译接口测试 — POST /api/v1/compile"""

from __future__ import annotations

import asyncio
import threading
import time
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from dochris.api.app import create_app


@pytest.fixture
def client() -> TestClient:
    return TestClient(create_app())


def _wait_for_job(
    client: TestClient,
    job_id: str,
    expected_status: str,
    timeout: float = 1.0,
) -> dict[str, object]:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        response = client.get(f"/api/v1/compile/jobs/{job_id}")
        if response.status_code == 200 and response.json()["status"] == expected_status:
            return response.json()
        time.sleep(0.01)
    pytest.fail(f"compile job {job_id} did not reach {expected_status}")


class TestCompileEndpoint:
    """编译接口测试"""

    def test_compile_no_work(self, client) -> None:
        """没有待编译文档"""
        with (
            patch("dochris.api.routes.compile.get_default_workspace"),
            patch("dochris.api.routes.compile.get_all_manifests", return_value=[]),
        ):
            resp = client.post("/api/v1/compile", json={"concurrency": 1})

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "no_work"
        assert data["total"] == 0

    def test_compile_dry_run(self, client) -> None:
        """模拟运行"""
        manifests = [{"id": f"SRC-{i:04d}", "status": "ingested"} for i in range(3)]

        with (
            patch("dochris.api.routes.compile.get_default_workspace"),
            patch("dochris.api.routes.compile.get_all_manifests", return_value=manifests),
        ):
            resp = client.post("/api/v1/compile", json={"dry_run": True, "concurrency": 1})

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "dry_run"
        assert data["total"] == 3

    def test_compile_with_limit(self, client) -> None:
        """限制编译数量"""
        manifests = [{"id": f"SRC-{i:04d}", "status": "ingested"} for i in range(10)]

        with (
            patch("dochris.api.routes.compile.get_default_workspace"),
            patch("dochris.api.routes.compile.get_all_manifests", return_value=manifests),
            patch(
                "dochris.api.routes.compile.do_compile_all", new_callable=AsyncMock
            ) as mock_compile,
        ):
            resp = client.post("/api/v1/compile", json={"limit": 5, "concurrency": 2})

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "accepted"
        mock_compile.assert_awaited_once()
        call_kwargs = mock_compile.await_args.kwargs
        assert call_kwargs["max_concurrent"] == 2
        assert call_kwargs["limit"] == 5
        assert call_kwargs["dry_run"] is False
        assert callable(call_kwargs["progress_callback"])

    def test_compile_background_error_is_logged(self, client) -> None:
        """后台编译失败不阻塞 HTTP 响应"""
        manifests = [{"id": "SRC-0001", "status": "ingested"}]

        with (
            patch("dochris.api.routes.compile.get_default_workspace"),
            patch("dochris.api.routes.compile.get_all_manifests", return_value=manifests),
            patch(
                "dochris.api.routes.compile.do_compile_all",
                new_callable=AsyncMock,
                side_effect=RuntimeError("编译失败"),
            ),
        ):
            resp = client.post("/api/v1/compile", json={"concurrency": 1})

        assert resp.status_code == 200
        assert resp.json()["status"] == "accepted"

    def test_compile_default_concurrency(self, client) -> None:
        """默认并发数为 1"""
        manifests = [{"id": "SRC-0001", "status": "ingested"}]

        with (
            patch("dochris.api.routes.compile.get_default_workspace"),
            patch("dochris.api.routes.compile.get_all_manifests", return_value=manifests),
            patch(
                "dochris.api.routes.compile.do_compile_all", new_callable=AsyncMock
            ) as mock_compile,
        ):
            resp = client.post("/api/v1/compile", json={})

        assert resp.status_code == 200
        call_kwargs = mock_compile.call_args
        assert call_kwargs[1]["max_concurrent"] == 1

    def test_compile_returns_job_id_and_exact_completed_status(self) -> None:
        """后台编译必须可按 ID 查询真实完成结果。"""
        manifests = [
            {"id": "SRC-0001", "status": "ingested"},
            {"id": "SRC-0002", "status": "ingested"},
        ]

        async def completed_compile(*, progress_callback, **_kwargs) -> None:
            progress_callback(
                processed=1,
                compiled=1,
                failed=0,
                current_files=["SRC-0002"],
            )
            progress_callback(
                processed=2,
                compiled=1,
                failed=1,
                current_files=[],
            )

        with (
            patch("dochris.api.routes.compile.get_default_workspace"),
            patch("dochris.api.routes.compile.get_all_manifests", return_value=manifests),
            patch("dochris.api.routes.compile.do_compile_all", new=completed_compile),
            TestClient(create_app()) as client,
        ):
            response = client.post("/api/v1/compile", json={"concurrency": 1})
            data = response.json()

            assert "job_id" in data
            job = _wait_for_job(client, data["job_id"], "completed")

        assert job["created_at"]
        assert job["started_at"]
        assert job["finished_at"]
        assert job == {
            "job_id": data["job_id"],
            "status": "completed",
            "message": "编译完成",
            "total": 2,
            "processed": 2,
            "compiled": 1,
            "failed": 1,
            "current_files": [],
            "cancel_requested": False,
            "concurrency": 1,
            "limit": None,
            "attempt": 1,
            "retry_of": None,
            "retryable": False,
            "error": None,
            "created_at": job["created_at"],
            "started_at": job["started_at"],
            "finished_at": job["finished_at"],
        }

    def test_running_compile_is_reused_and_discoverable_after_reload(self) -> None:
        """重复提交复用活动任务，刷新后可查询当前任务。"""
        manifests = [{"id": "SRC-0001", "status": "ingested"}]
        started = threading.Event()
        release = threading.Event()

        async def slow_compile(*, progress_callback, **_kwargs) -> None:
            progress_callback(
                processed=0,
                compiled=0,
                failed=0,
                current_files=["SRC-0001"],
            )
            started.set()
            while not release.is_set():
                await asyncio.sleep(0.01)

        with (
            patch("dochris.api.routes.compile.get_default_workspace"),
            patch("dochris.api.routes.compile.get_all_manifests", return_value=manifests),
            patch("dochris.api.routes.compile.do_compile_all", new=slow_compile),
            TestClient(create_app()) as client,
        ):
            first = client.post("/api/v1/compile", json={}).json()
            assert started.wait(timeout=1.0)

            duplicate = client.post("/api/v1/compile", json={}).json()
            restored = client.get("/api/v1/compile/jobs/current")

            assert duplicate["job_id"] == first["job_id"]
            assert duplicate["status"] == "running"
            assert restored.status_code == 200
            assert restored.json()["job_id"] == first["job_id"]
            assert restored.json()["current_files"] == ["SRC-0001"]

            release.set()
            completed = _wait_for_job(client, first["job_id"], "completed")

        assert completed["processed"] == 0

    def test_running_compile_can_be_cancelled(self) -> None:
        """取消端点必须终止后台协程并保留可查询的取消状态。"""
        manifests = [{"id": "SRC-0001", "status": "ingested"}]
        started = threading.Event()
        runner_cancelled = threading.Event()

        async def slow_compile(*, progress_callback, **_kwargs) -> None:
            progress_callback(
                processed=0,
                compiled=0,
                failed=0,
                current_files=["SRC-0001"],
            )
            started.set()
            try:
                while True:
                    await asyncio.sleep(0.01)
            finally:
                runner_cancelled.set()

        with (
            patch("dochris.api.routes.compile.get_default_workspace"),
            patch("dochris.api.routes.compile.get_all_manifests", return_value=manifests),
            patch("dochris.api.routes.compile.do_compile_all", new=slow_compile),
            TestClient(create_app()) as client,
        ):
            submitted = client.post("/api/v1/compile", json={}).json()
            assert started.wait(timeout=1.0)

            response = client.post(f"/api/v1/compile/jobs/{submitted['job_id']}/cancel")

            assert response.status_code == 200
            assert response.json()["cancel_requested"] is True
            cancelled = _wait_for_job(client, submitted["job_id"], "cancelled")

        assert runner_cancelled.is_set()
        assert cancelled["message"] == "编译已取消"
        assert cancelled["current_files"] == []
        assert cancelled["cancel_requested"] is True

    def test_completed_job_is_available_after_api_restart(self, tmp_path) -> None:
        """同一工作区的新 API 进程必须恢复最近一次编译任务。"""
        manifests = [{"id": "SRC-0001", "status": "ingested"}]

        async def completed_compile(*, progress_callback, **_kwargs) -> None:
            progress_callback(
                processed=1,
                compiled=1,
                failed=0,
                current_files=[],
            )

        with (
            patch(
                "dochris.api.routes.compile.get_default_workspace",
                return_value=tmp_path,
            ),
            patch("dochris.api.routes.compile.get_all_manifests", return_value=manifests),
            patch("dochris.api.routes.compile.do_compile_all", new=completed_compile),
        ):
            with TestClient(create_app()) as first_client:
                submitted = first_client.post("/api/v1/compile", json={}).json()
                completed = _wait_for_job(
                    first_client,
                    submitted["job_id"],
                    "completed",
                )

            with TestClient(create_app()) as restarted_client:
                restored = restarted_client.get("/api/v1/compile/jobs/current")

        assert restored.status_code == 200
        assert restored.json() == completed

    def test_compile_job_history_returns_newest_first(self, tmp_path) -> None:
        """历史接口必须按新到旧返回，并尊重 limit。"""
        manifests = [{"id": "SRC-0001", "status": "ingested"}]

        async def completed_compile(*, progress_callback, **_kwargs) -> None:
            progress_callback(
                processed=1,
                compiled=1,
                failed=0,
                current_files=[],
            )

        with (
            patch(
                "dochris.api.routes.compile.get_default_workspace",
                return_value=tmp_path,
            ),
            patch("dochris.api.routes.compile.get_all_manifests", return_value=manifests),
            patch("dochris.api.routes.compile.do_compile_all", new=completed_compile),
            TestClient(create_app()) as client,
        ):
            first = client.post("/api/v1/compile", json={}).json()
            _wait_for_job(client, first["job_id"], "completed")
            second = client.post("/api/v1/compile", json={}).json()
            _wait_for_job(client, second["job_id"], "completed")

            response = client.get("/api/v1/compile/jobs", params={"limit": 1})

        assert response.status_code == 200
        assert [item["job_id"] for item in response.json()] == [second["job_id"]]

    def test_failed_compile_can_be_retried_with_original_parameters(self, tmp_path) -> None:
        """失败任务应保留诊断信息，并可用原参数创建关联重试。"""
        manifests = [{"id": f"SRC-{index:04d}", "status": "ingested"} for index in range(1, 6)]
        calls: list[dict[str, object]] = []

        async def flaky_compile(*, progress_callback, **kwargs) -> None:
            calls.append(kwargs)
            if len(calls) == 1:
                raise RuntimeError("provider unavailable")
            progress_callback(
                processed=4,
                compiled=4,
                failed=0,
                current_files=[],
            )

        with (
            patch(
                "dochris.api.routes.compile.get_default_workspace",
                return_value=tmp_path,
            ),
            patch("dochris.api.routes.compile.get_all_manifests", return_value=manifests),
            patch("dochris.api.routes.compile.do_compile_all", new=flaky_compile),
            TestClient(create_app()) as client,
        ):
            submitted = client.post(
                "/api/v1/compile",
                json={"concurrency": 3, "limit": 4},
            ).json()
            failed = _wait_for_job(client, submitted["job_id"], "failed")

            retried_response = client.post(f"/api/v1/compile/jobs/{submitted['job_id']}/retry")
            retried = retried_response.json()
            completed = _wait_for_job(client, retried["job_id"], "completed")

        assert failed["error"] == "RuntimeError: provider unavailable"
        assert failed["retryable"] is True
        assert failed["concurrency"] == 3
        assert failed["limit"] == 4
        assert failed["attempt"] == 1
        assert failed["created_at"]
        assert failed["started_at"]
        assert failed["finished_at"]
        assert retried_response.status_code == 200
        assert retried["job_id"] != submitted["job_id"]
        assert completed["retry_of"] == submitted["job_id"]
        assert completed["attempt"] == 2
        assert completed["concurrency"] == 3
        assert completed["limit"] == 4
        assert calls == [
            {"max_concurrent": 3, "limit": 4, "dry_run": False},
            {"max_concurrent": 3, "limit": 4, "dry_run": False},
        ]
