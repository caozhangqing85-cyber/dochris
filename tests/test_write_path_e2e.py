"""Isolated end-to-end proof for Dochris' critical write path.

The child process sets WORKSPACE before importing Dochris, matching a real
server start while guaranteeing that no user workspace or credentials are read.
Only external model/vector boundaries are replaced with deterministic doubles;
API routing, parsing, manifests, compilation persistence, query retrieval,
candidate creation, promotion, and reset all execute their production code.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from httpx import Response


def _assert_response(response: Response, expected_status: int) -> dict[str, object]:
    assert response.status_code == expected_status, response.text
    payload = response.json()
    assert isinstance(payload, dict)
    return payload


def _run_isolated_child(root: Path) -> dict[str, object]:
    workspace = root / "workspace"
    isolated_home = root / "home"
    isolated_home.mkdir(parents=True)
    os.environ.update(
        {
            "HOME": str(isolated_home),
            "WORKSPACE": str(workspace),
            "OPENAI_API_KEY": "e2e-placeholder-key",
            "VECTOR_STORE": "chromadb",
            "DOCHRIS_PRELOAD_EMBEDDING": "false",
        }
    )
    for name in ("BIGMODEL_API_KEY", "ANTHROPIC_AUTH_TOKEN", "DOCHRIS_API_KEY"):
        os.environ.pop(name, None)

    # Import only after the process isolation boundary is established.
    from fastapi.testclient import TestClient

    from dochris.api.app import create_app
    from dochris.cli.cli_init import cmd_init
    from dochris.manifest import get_all_manifests, update_manifest_status
    from dochris.phases import phase3_query, query_engine
    from dochris.settings import reset_settings
    from dochris.workers.compiler_worker import CompilerWorker

    assert (
        cmd_init(
            SimpleNamespace(
                non_interactive=True,
                api_key="e2e-placeholder-key",
                path=str(workspace),
            )
        )
        == 0
    )
    reset_settings()
    query_engine.clear_caches()

    source_text = (
        "可复现知识工作流通过明确输入、确定性处理和可审计输出保证结果可信。"
        "它要求上传、编译、查询、候选审核、晋升与恢复步骤均能重复执行。" * 4
    )
    compiled_detail = (
        "可复现知识工作流是一套学习、理解、应用、实践和优化方法。"
        "它通过 API、框架、数据库、缓存和监控记录输入与结果，并以证据支持审计。" * 18
    )
    compiled_result = {
        "one_line": "可复现知识工作流让知识处理结果可信且可以安全恢复",
        "key_points": [
            "输入必须明确",
            "处理必须确定",
            "输出必须可审计",
            "写入必须可恢复",
            "查询与写入必须分离",
        ],
        "detailed_summary": compiled_detail,
        "concepts": [
            {"name": "可复现知识", "explanation": "能够重复验证并追踪来源的知识。"},
            {"name": "安全写路径", "explanation": "具有审计、幂等和恢复能力的写入流程。"},
        ],
    }
    generated_answer = (
        "## 可复现知识工作流\n\n"
        "- [[可复现知识]] 强调学习、理解、应用、实践与优化。\n"
        "- [[安全写路径]] 使用 API、框架、数据库、缓存和监控保存证据。\n"
        "- 每个步骤都需要明确输入、审计结果和恢复机制。\n"
        + "这套方法能够提升知识系统的可靠性、使用体验和维护能力。"
        * 22
    )

    with (
        patch.object(
            CompilerWorker,
            "_generate_with_fallback",
            new=AsyncMock(return_value=compiled_result),
        ),
        patch.object(CompilerWorker, "_get_vector_store", return_value=None),
        patch.object(phase3_query, "vector_search", return_value=[]),
        patch.object(phase3_query, "create_query_provider", return_value=object()),
        patch.object(
            phase3_query,
            "generate_answer_async",
            new=AsyncMock(return_value=generated_answer),
        ),
        TestClient(create_app()) as client,
    ):
        upload = _assert_response(
            client.post(
                "/api/v1/files/upload",
                files={"files": ("reproducible.md", source_text, "text/markdown")},
            ),
            200,
        )
        assert upload == {"saved": 1, "ingested": 1, "skipped": 0, "failed": 0, "errors": []}

        manifests = get_all_manifests(workspace)
        assert len(manifests) == 1
        src_id = str(manifests[0]["id"])
        assert manifests[0]["status"] == "ingested"

        compile_result = _assert_response(
            client.post("/api/v1/compile", json={"concurrency": 1}),
            200,
        )
        assert compile_result["status"] == "accepted"
        job_id = str(compile_result["job_id"])
        deadline = time.monotonic() + 10
        while True:
            compile_job = _assert_response(
                client.get(f"/api/v1/compile/jobs/{job_id}"),
                200,
            )
            if compile_job["status"] not in {"queued", "running", "cancelling"}:
                break
            assert time.monotonic() < deadline, compile_job
            time.sleep(0.01)
        assert compile_job["status"] == "completed", compile_job
        assert compile_job["processed"] == 1
        assert compile_job["compiled"] == 1
        assert compile_job["failed"] == 0
        compiled_manifest = get_all_manifests(workspace)[0]
        assert compiled_manifest["status"] == "compiled"
        assert (workspace / "outputs" / "summaries" / f"{src_id}.md").is_file()
        assert (workspace / "outputs" / "concepts" / "可复现知识.md").is_file()

        query = _assert_response(
            client.get(
                "/api/v1/query",
                params={"q": "可复现知识", "mode": "combined", "top_k": 5},
            ),
            200,
        )
        assert query["answer"] == generated_answer
        assert query["concepts"] or query["summaries"]
        assert not (workspace / "outputs" / "candidates").exists(), "GET query must stay read-only"

        contribution = _assert_response(
            client.post("/api/v1/query/contribution", json=query),
            201,
        )
        candidate_id = str(contribution["id"])
        assert int(contribution["quality_score"]) >= 85
        candidates = _assert_response(client.get("/api/v1/candidates"), 200)
        assert candidates["total"] == 1

        promotion = _assert_response(
            client.post(f"/api/v1/candidates/{candidate_id}/promote"),
            200,
        )
        assert promotion["success"] is True
        promoted_path = workspace / str(promotion["promoted_to"])
        assert promoted_path.is_file()
        assert (workspace / "wiki" / "concepts" / "可复现知识.md").is_file()

        update_manifest_status(workspace, src_id, "compiled", quality_score=10)
        reset = _assert_response(client.post("/api/v1/quality/reset"), 200)
        assert reset == {"reset_count": 1}
        assert get_all_manifests(workspace)[0]["status"] == "ingested"

    assert workspace.is_relative_to(root)
    assert isolated_home.is_relative_to(root)
    return {
        "workspace": str(workspace),
        "src_id": src_id,
        "candidate_id": candidate_id,
        "uploaded": upload["saved"],
        "compiled": 1,
        "query_results": len(query["concepts"]) + len(query["summaries"]),  # type: ignore[arg-type]
        "promoted": promotion["success"],
        "reset": reset["reset_count"],
    }


@pytest.mark.integration
def test_isolated_upload_compile_query_candidate_promote_reset(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    env = os.environ.copy()
    env["DOCHRIS_WRITE_E2E_ROOT"] = str(tmp_path)
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
    assert evidence["uploaded"] == 1
    assert evidence["compiled"] == 1
    assert evidence["query_results"] >= 1
    assert evidence["promoted"] is True
    assert evidence["reset"] == 1


if __name__ == "__main__" and sys.argv[-1:] == ["--child"]:
    result = _run_isolated_child(Path(os.environ["DOCHRIS_WRITE_E2E_ROOT"]).resolve())
    print(json.dumps(result, ensure_ascii=False))
