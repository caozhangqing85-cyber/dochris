"""流式查询接口契约测试。"""

from __future__ import annotations

import asyncio
import json
from unittest.mock import MagicMock, patch

import pytest

from dochris.api.routes.query import query_stream

pytestmark = pytest.mark.fast


async def _collect_stream(**kwargs: object) -> str:
    response = await query_stream(q="测试", **kwargs)
    chunks: list[str] = []
    async for chunk in response.body_iterator:
        chunks.append(chunk.decode() if isinstance(chunk, bytes) else chunk)
    return "".join(chunks)


async def _collect_stream_until_cancelled(**kwargs: object) -> str:
    response = await query_stream(q="测试", **kwargs)
    chunks: list[str] = []
    with pytest.raises(asyncio.CancelledError):
        async for chunk in response.body_iterator:
            chunks.append(chunk.decode() if isinstance(chunk, bytes) else chunk)
    return "".join(chunks)


def _concept(title: str = "统一检索结果") -> dict[str, object]:
    return {
        "title": title,
        "definition": "来自统一检索管线的概念定义",
        "source": "wiki",
        "manifest_id": "SRC-0001",
        "score": 0.9,
    }


def _events(payload: str, event_name: str) -> list[dict[str, object] | str]:
    events: list[dict[str, object] | str] = []
    for block in payload.split("\n\n"):
        if not block.startswith(f"event: {event_name}"):
            continue
        data_lines = [
            line.removeprefix("data: ") for line in block.splitlines() if line.startswith("data: ")
        ]
        data = "\n".join(data_lines)
        try:
            events.append(json.loads(data))
        except json.JSONDecodeError:
            events.append(data)
    return events


def _assert_success_terminal_once(payload: str) -> None:
    assert len(_events(payload, "done")) == 1
    assert len(_events(payload, "error")) == 0


def _assert_failure_terminal_once(payload: str) -> None:
    assert len(_events(payload, "error")) == 1
    assert len(_events(payload, "done")) == 0


@pytest.mark.asyncio
async def test_all_mode_streams_retrieval_results() -> None:
    """all 模式必须返回检索结果，不能被误判为空库。"""
    with (
        patch("dochris.phases.phase3_query.search_all") as mock_search_all,
        patch("dochris.api.routes.query.query_engine.create_query_provider", return_value=None),
    ):
        mock_search_all.return_value = {
            "concepts": [_concept()],
            "summaries": [],
            "vector_results": [],
            "search_sources": ["wiki"],
        }
        payload = await _collect_stream(mode="all", top_k=5, rerank=False, contribute=False)

    assert "event: retrieval" in payload
    assert "统一检索结果" in payload
    assert "未找到相关内容" not in payload
    _assert_success_terminal_once(payload)


@pytest.mark.asyncio
async def test_stream_uses_shared_retrieval_core() -> None:
    """SSE 与普通查询必须复用同一个检索核心。"""
    from dochris.phases import phase3_query

    with (
        patch.object(
            phase3_query,
            "retrieve_query_context",
            return_value={
                "concepts": [_concept("共享检索结果")],
                "summaries": [],
                "vector_results": [],
                "search_sources": ["wiki"],
            },
            create=True,
        ) as mock_retrieve,
        patch("dochris.phases.phase3_query.search_concepts", return_value=[]),
        patch("dochris.phases.phase3_query.search_summaries", return_value=[]),
        patch("dochris.api.routes.query.query_engine.create_query_provider", return_value=None),
    ):
        payload = await _collect_stream(
            mode="concept",
            top_k=5,
            rerank=False,
            contribute=False,
        )

    mock_retrieve.assert_called_once()
    assert "共享检索结果" in payload
    _assert_success_terminal_once(payload)


@pytest.mark.asyncio
async def test_stream_applies_reranker_and_reports_rerank_timing() -> None:
    """rerank=true 必须真正重排序，而不是只把参数吞掉。"""
    from dochris.phases import phase3_query

    with (
        patch("dochris.phases.phase3_query.search_concepts", return_value=[_concept("原始结果")]),
        patch("dochris.phases.phase3_query.search_summaries", return_value=[]),
        patch.object(
            phase3_query,
            "rerank_query_context",
            return_value={
                "concepts": [_concept("重排序结果")],
                "summaries": [],
                "vector_results": [],
                "search_sources": ["wiki", "reranker"],
            },
            create=True,
        ) as mock_rerank,
        patch("dochris.api.routes.query.query_engine.create_query_provider", return_value=None),
    ):
        payload = await _collect_stream(
            mode="concept",
            top_k=5,
            rerank=True,
            contribute=False,
        )

    mock_rerank.assert_called_once()
    assert len(_events(payload, "rerank")) == 1
    assert "重排序结果" in payload
    [done_data] = _events(payload, "done")
    assert isinstance(done_data, dict)
    timings = done_data["timings"]
    assert isinstance(timings, dict)
    assert timings["rerank_seconds"] >= 0
    _assert_success_terminal_once(payload)


@pytest.mark.asyncio
async def test_all_mode_streams_coherent_retrieval_payload_with_vector_results() -> None:
    """all 模式统一检索结果必须在一个 retrieval payload 中保留三类结果。"""
    with (
        patch("dochris.phases.phase3_query.search_all") as mock_search_all,
        patch("dochris.api.routes.query.query_engine.create_query_provider", return_value=None),
    ):
        mock_search_all.return_value = {
            "concepts": [_concept("概念结果")],
            "summaries": [
                {
                    "title": "摘要结果",
                    "content": "摘要正文",
                    "source": "summary",
                    "manifest_id": "SRC-0002",
                    "score": 0.8,
                }
            ],
            "vector_results": [
                {
                    "title": "向量结果",
                    "content": "向量正文",
                    "source": "vector",
                    "manifest_id": "SRC-0003",
                    "score": 0.2,
                }
            ],
            "search_sources": ["wiki", "summary", "vector"],
        }
        payload = await _collect_stream(mode="all", top_k=5, rerank=False, contribute=False)

    retrieval_events = _events(payload, "retrieval")
    assert len(retrieval_events) == 1
    retrieval = retrieval_events[0]
    assert isinstance(retrieval, dict)
    assert retrieval["concepts"][0]["title"] == "概念结果"
    assert retrieval["summaries"][0]["title"] == "摘要结果"
    assert retrieval["vector_results"][0]["title"] == "向量结果"
    _assert_success_terminal_once(payload)


@pytest.mark.asyncio
async def test_legacy_contribute_flag_never_writes_during_get_stream() -> None:
    """兼容旧参数，但 GET SSE 查询必须始终保持只读。"""

    async def fake_answer_stream(*_args: object, **_kwargs: object):
        yield "知识回答" * 30

    with (
        patch("dochris.phases.phase3_query.search_concepts", return_value=[_concept()]),
        patch("dochris.phases.phase3_query.search_summaries", return_value=[]),
        patch(
            "dochris.api.routes.query.query_engine.create_query_provider", return_value=MagicMock()
        ),
        patch(
            "dochris.api.routes.query.query_engine.generate_answer_stream_async",
            new=fake_answer_stream,
        ),
        patch(
            "dochris.quality.query_contribution.auto_contribute_from_query",
            return_value={
                "id": "should-not-be-created",
                "quality_score": 88,
                "needs_review": True,
                "auto_promoted": False,
            },
        ) as mock_contribute,
    ):
        payload = await _collect_stream(
            mode="concept",
            top_k=5,
            rerank=False,
            contribute=True,
        )

    mock_contribute.assert_not_called()
    [done_data] = _events(payload, "done")
    assert isinstance(done_data, dict)
    assert "contribution" not in done_data
    _assert_success_terminal_once(payload)


@pytest.mark.asyncio
async def test_stream_done_includes_measurable_phase_timings() -> None:
    """成功流必须暴露可度量的阶段耗时，而不是只有总耗时。"""

    async def fake_answer_stream(*_args: object, **_kwargs: object):
        yield "第一段"
        yield "第二段"

    with (
        patch("dochris.phases.phase3_query.search_concepts", return_value=[_concept()]),
        patch("dochris.phases.phase3_query.search_summaries", return_value=[]),
        patch(
            "dochris.api.routes.query.query_engine.create_query_provider", return_value=MagicMock()
        ),
        patch(
            "dochris.api.routes.query.query_engine.generate_answer_stream_async",
            new=fake_answer_stream,
        ),
    ):
        payload = await _collect_stream(
            mode="concept",
            top_k=5,
            rerank=False,
            contribute=False,
        )

    [done_data] = _events(payload, "done")
    assert isinstance(done_data, dict)
    timings = done_data["timings"]
    assert isinstance(timings, dict)
    assert set(timings) >= {
        "retrieval_seconds",
        "first_token_seconds",
        "generation_seconds",
        "total_seconds",
    }
    assert done_data["time_seconds"] == timings["total_seconds"]
    _assert_success_terminal_once(payload)


@pytest.mark.asyncio
async def test_meta_time_seconds_is_monotonic_with_done_total() -> None:
    """meta 耗时必须使用同一个单调时钟，不能混用 wall clock 和 perf counter。"""

    async def fake_answer_stream(*_args: object, **_kwargs: object):
        yield "答案"

    with (
        patch("dochris.phases.phase3_query.search_concepts", return_value=[_concept()]),
        patch("dochris.phases.phase3_query.search_summaries", return_value=[]),
        patch(
            "dochris.api.routes.query.query_engine.create_query_provider", return_value=MagicMock()
        ),
        patch(
            "dochris.api.routes.query.query_engine.generate_answer_stream_async",
            new=fake_answer_stream,
        ),
    ):
        payload = await _collect_stream(
            mode="concept",
            top_k=5,
            rerank=False,
            contribute=False,
        )

    [meta_data] = _events(payload, "meta")
    [done_data] = _events(payload, "done")
    assert isinstance(meta_data, dict)
    assert isinstance(done_data, dict)
    assert 0 <= meta_data["time_seconds"] <= done_data["timings"]["total_seconds"]
    _assert_success_terminal_once(payload)


@pytest.mark.asyncio
async def test_stream_timings_exclude_mutation_phase() -> None:
    """只读 GET 流不得混入贡献写入阶段耗时。"""

    async def fake_answer_stream(*_args: object, **_kwargs: object):
        yield "知识回答" * 30

    with (
        patch("dochris.phases.phase3_query.search_concepts", return_value=[_concept()]),
        patch("dochris.phases.phase3_query.search_summaries", return_value=[]),
        patch(
            "dochris.api.routes.query.query_engine.create_query_provider", return_value=MagicMock()
        ),
        patch(
            "dochris.api.routes.query.query_engine.generate_answer_stream_async",
            new=fake_answer_stream,
        ),
    ):
        payload = await _collect_stream(
            mode="concept",
            top_k=5,
            rerank=False,
            contribute=True,
        )

    [done_data] = _events(payload, "done")
    assert isinstance(done_data, dict)
    timings = done_data["timings"]
    assert isinstance(timings, dict)
    assert "contribution_seconds" not in timings
    assert timings["generation_seconds"] >= 0
    _assert_success_terminal_once(payload)


@pytest.mark.asyncio
async def test_stream_timeout_emits_terminal_error_without_done() -> None:
    """生成超时时不能同时发 error 和 done。"""

    async def timeout_answer_stream(*_args: object, **_kwargs: object):
        raise TimeoutError("llm timed out")
        yield "unreachable"

    with (
        patch("dochris.phases.phase3_query.search_concepts", return_value=[_concept()]),
        patch("dochris.phases.phase3_query.search_summaries", return_value=[]),
        patch(
            "dochris.api.routes.query.query_engine.create_query_provider", return_value=MagicMock()
        ),
        patch(
            "dochris.api.routes.query.query_engine.generate_answer_stream_async",
            new=timeout_answer_stream,
        ),
    ):
        payload = await _collect_stream(
            mode="concept",
            top_k=5,
            rerank=False,
            contribute=False,
        )

    [error_data] = _events(payload, "error")
    assert isinstance(error_data, dict)
    assert error_data["code"] == "timeout"
    assert error_data["terminal"] is True
    _assert_failure_terminal_once(payload)


@pytest.mark.asyncio
async def test_stream_cancellation_propagates_without_terminal_frame() -> None:
    """ASGI 取消必须向上传播，不能尝试在关闭 transport 上补 error/done。"""

    async def cancelled_answer_stream(*_args: object, **_kwargs: object):
        raise asyncio.CancelledError("client cancelled")
        yield "unreachable"

    with (
        patch("dochris.phases.phase3_query.search_concepts", return_value=[_concept()]),
        patch("dochris.phases.phase3_query.search_summaries", return_value=[]),
        patch(
            "dochris.api.routes.query.query_engine.create_query_provider", return_value=MagicMock()
        ),
        patch(
            "dochris.api.routes.query.query_engine.generate_answer_stream_async",
            new=cancelled_answer_stream,
        ),
    ):
        payload = await _collect_stream_until_cancelled(
            mode="concept",
            top_k=5,
            rerank=False,
            contribute=False,
        )

    assert "event: error" not in payload
    assert "event: done" not in payload


@pytest.mark.asyncio
async def test_stream_errors_are_sanitized_and_traceable() -> None:
    """SSE error 不能把原始异常、绝对路径或本地敏感文本发给客户端。"""

    async def failing_answer_stream(*_args: object, **_kwargs: object):
        raise RuntimeError("failed at /Users/changqing/private/token.txt")
        yield "unreachable"

    with (
        patch("dochris.api.routes.query.get_current_trace_id", return_value="trace-sec-1"),
        patch("dochris.phases.phase3_query.search_concepts", return_value=[_concept()]),
        patch("dochris.phases.phase3_query.search_summaries", return_value=[]),
        patch(
            "dochris.api.routes.query.query_engine.create_query_provider", return_value=MagicMock()
        ),
        patch(
            "dochris.api.routes.query.query_engine.generate_answer_stream_async",
            new=failing_answer_stream,
        ),
    ):
        payload = await _collect_stream(
            mode="concept",
            top_k=5,
            rerank=False,
            contribute=False,
        )

    [error_data] = _events(payload, "error")
    assert isinstance(error_data, dict)
    assert error_data["code"] == "stream_error"
    assert error_data["trace_id"] == "trace-sec-1"
    assert error_data["terminal"] is True
    assert "/Users/" not in error_data["message"]
    assert "private" not in error_data["message"]
    assert "token.txt" not in error_data["message"]
    _assert_failure_terminal_once(payload)
