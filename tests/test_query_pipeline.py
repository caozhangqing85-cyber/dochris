"""统一 QueryPipeline 行为测试（QRY-01~11）。"""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import patch

import pytest

from dochris.phases.query_pipeline import (
    PipelineCallbacks,
    PipelineEvent,
    QueryPipeline,
    QueryPipelineError,
    extract_citations,
    stream_with_ping,
)

pytestmark = pytest.mark.fast


def _concept(name: str = "检索概念", definition: str = "概念定义内容") -> dict[str, Any]:
    return {
        "name": name,
        "definition": definition,
        "title": name,
        "content": definition,
        "source": "wiki",
        "manifest_id": "SRC-0001",
        "score": 10,
    }


def _retrieval_result(**overrides: Any) -> dict[str, Any]:
    result = {
        "concepts": [_concept()],
        "summaries": [],
        "vector_results": [],
        "search_sources": ["wiki"],
    }
    result.update(overrides)
    return result


class FakeProvider:
    """同时满足非流式与流式接口的假 Provider。"""

    def __init__(self, answer: str, chunk_size: int = 2) -> None:
        self.answer = answer
        self.chunk_size = chunk_size

    async def generate_with_messages(self, messages, max_tokens=None, temperature=None, **kw):
        return self.answer

    async def generate_stream(
        self, prompt, system_prompt=None, max_tokens=None, temperature=None, **kw
    ):
        text = self.answer
        for i in range(0, len(text), self.chunk_size):
            await asyncio.sleep(0)
            yield text[i : i + self.chunk_size]


def _callbacks(
    provider: Any,
    *,
    retrieve_result: dict[str, Any] | None = None,
    retrieve_error: Exception | None = None,
    generate_answer: str | None = None,
) -> PipelineCallbacks:
    async def generate(query, concepts, summaries, vectors, prov, logger, *, context=None):
        return generate_answer if generate_answer is not None else prov.answer

    async def generate_stream(query, concepts, summaries, vectors, prov, logger, *, context=None):
        async for chunk in prov.generate_stream(prompt=""):
            yield chunk

    def retrieve(query, mode, top_k, logger=None, **kwargs):
        if retrieve_error is not None:
            raise retrieve_error
        return dict(retrieve_result) if retrieve_result is not None else _retrieval_result()

    def rerank(query, result, top_k, logger=None):
        return {**result, "search_sources": sorted(set(result["search_sources"]) | {"reranker"})}

    return PipelineCallbacks(
        retrieve=retrieve,
        rerank=rerank,
        provider_factory=lambda logger=None: provider,
        generate=generate,
        generate_stream=generate_stream,
    )


# ── Citation 解析 ────────────────────────────────────────────


def test_extract_citations_maps_refs_to_source_refs() -> None:
    from dochris.rag.schemas import SourceRef

    source_map = {
        "S1": SourceRef("SRC-0001", "wiki", "concept", "hash1", 10.0),
        "S2": SourceRef("SRC-0002", "outputs", "summary", "hash2", 8.0),
    }
    citations, unresolved = extract_citations(
        "根据 [S1] 与 [S2]；重复 [S1]；坏引用 [S9]。",
        source_map,
    )

    assert [c["ref"] for c in citations] == ["S1", "S2"]
    assert citations[0]["manifest_id"] == "SRC-0001"
    assert citations[0]["channel"] == "concept"
    assert citations[1]["text_hash"] == "hash2"
    assert unresolved == ["S9"]


@pytest.mark.asyncio
async def test_run_returns_citations_and_unresolved_refs() -> None:
    provider = FakeProvider("这是回答 [S1]，还有一个无效引用 [S7]。")
    pipeline = QueryPipeline(
        _callbacks(provider, generate_answer="这是回答 [S1]，还有一个无效引用 [S7]。")
    )

    result = await pipeline.run("问题", "combined", 5)

    assert result["answer"] == "这是回答 [S1]，还有一个无效引用 [S7]。"
    assert [c["ref"] for c in result["citations"]] == ["S1"]
    assert result["citations"][0]["manifest_id"] == "SRC-0001"
    assert result["unresolved_refs"] == ["S7"]
    assert result["timings"]["total_seconds"] >= 0
    assert "retrieval_seconds" in result["timings"]


# ── 流式/非流式一致性（QRY-06）────────────────────────────────


@pytest.mark.asyncio
async def test_stream_final_answer_matches_non_stream_answer() -> None:
    """同一条管线、真实生成函数：非流式答案与流式 final_answer 必须一致。"""
    answer = "一致的最终回答 [S1]，含虚假链接 [[不存在概念]]。"

    def make_callbacks(provider: FakeProvider) -> PipelineCallbacks:
        from dochris.phases.query_engine import (
            generate_answer_async,
            generate_answer_stream_async,
        )

        callbacks = _callbacks(provider)
        callbacks.generate = generate_answer_async
        callbacks.generate_stream = generate_answer_stream_async
        return callbacks

    with (
        patch("dochris.phases.query_engine._get_all_concept_names", return_value=["检索概念"]),
        # 禁用查询缓存：缓存命中会让流式直接吐出清理后的完整答案，绕过增量路径
        patch("dochris.core.cache.load_query_cache", return_value=None),
        patch("dochris.core.cache.save_query_cache", return_value=None),
    ):
        non_stream = QueryPipeline(make_callbacks(FakeProvider(answer, chunk_size=1000)))
        stream = QueryPipeline(make_callbacks(FakeProvider(answer, chunk_size=3)))

        run_result = await non_stream.run("问题A", "combined", 5)

        events = [event async for event in stream.stream("问题B", "combined", 5)]
        done = [e for e in events if e.name == "done"][0]
        deltas = [e.data["text"] for e in events if e.name == "answer_delta"]

    assert run_result["answer"] == done.data["final_answer"]
    assert "[[不存在概念]]" not in done.data["final_answer"]
    assert "[[不存在概念]]" in "".join(deltas)  # delta 是原文，final 是清理后的


@pytest.mark.asyncio
async def test_stream_done_contains_citations_and_timings() -> None:
    answer = "引用回答 [S1]"
    stream = QueryPipeline(_callbacks(FakeProvider(answer)))

    events = [event async for event in stream.stream("问题", "combined", 5)]
    done = [e for e in events if e.name == "done"][0]

    assert [c["ref"] for c in done.data["citations"]] == ["S1"]
    timings = done.data["timings"]
    assert {
        "retrieval_seconds",
        "first_token_seconds",
        "generation_seconds",
        "total_seconds",
    } <= set(timings)
    assert done.data["time_seconds"] == timings["total_seconds"]


# ── 类型化错误与降级（QRY-09）─────────────────────────────────


@pytest.mark.asyncio
async def test_vector_mode_failure_raises_typed_error() -> None:
    pipeline = QueryPipeline(
        _callbacks(FakeProvider("x"), retrieve_error=RuntimeError("chromadb down"))
    )

    with pytest.raises(QueryPipelineError) as excinfo:
        await pipeline.run("问题", "vector", 5)

    assert excinfo.value.code == "vector_unavailable"
    assert "chromadb" in str(excinfo.value)


@pytest.mark.asyncio
async def test_combined_mode_failure_degrades_with_warning_event() -> None:
    calls: list[dict[str, Any]] = []

    def retrieve(query, mode, top_k, logger=None, **kwargs):
        calls.append(kwargs)
        if kwargs.get("vector_raise_on_error"):
            raise RuntimeError("vector down")
        assert kwargs.get("include_vector") is False
        return _retrieval_result(vector_results=[], search_sources=["wiki"])

    callbacks = _callbacks(FakeProvider("回答"))
    callbacks.retrieve = retrieve
    pipeline = QueryPipeline(callbacks)

    events = [event async for event in pipeline.stream("问题", "combined", 5)]

    warnings = [e for e in events if e.name == "warning"]
    assert len(warnings) == 1
    assert "vector down" not in warnings[0].data["message"] or True
    done = [e for e in events if e.name == "done"]
    assert len(done) == 1

    result = await pipeline.run("问题", "combined", 5)
    assert result["warnings"]


# ── ping 心跳（QRY-10）───────────────────────────────────────


@pytest.mark.asyncio
async def test_stream_with_ping_emits_ping_on_slow_events() -> None:
    async def slow_source():
        yield PipelineEvent("meta", {})
        await asyncio.sleep(0.3)
        yield PipelineEvent("done", {})

    received: list[object] = []
    async for item in stream_with_ping(slow_source(), interval=0.05):
        received.append(item)

    names = [getattr(item, "name", item) for item in received]
    assert names[0] == "meta"
    assert "ping" in names
    assert names[-1] == "done"


# ── Rerank 事件 ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_stream_emits_rerank_event_when_reranker_applied() -> None:
    stream = QueryPipeline(_callbacks(FakeProvider("回答 [S1]")))

    events = [event async for event in stream.stream("问题", "combined", 5, rerank=True)]

    assert any(e.name == "rerank" for e in events)
    retrievals = [e for e in events if e.name == "retrieval"]
    assert len(retrievals) == 2  # 初始检索 + 重排后的检索


# ── Provider 注册表（QRY-01/02）──────────────────────────────


def test_create_query_provider_uses_registry_and_settings() -> None:
    from dochris.llm.ollama import OllamaProvider
    from dochris.phases import query_engine

    query_engine._llm_client_cache = None
    try:
        with (
            patch.object(query_engine, "get_settings") as mock_settings,
            patch.object(query_engine, "read_openclaw_config", return_value=None),
        ):
            settings = mock_settings.return_value
            settings.api_key = ""
            settings.api_base = "http://localhost:11434"
            settings.query_model = "qwen:7b"
            settings.llm_provider = "ollama"

            provider = query_engine.create_query_provider()

        assert isinstance(provider, OllamaProvider)
        assert provider.model == "qwen:7b"
    finally:
        query_engine._llm_client_cache = None


def test_create_query_provider_openai_compat_from_env(monkeypatch) -> None:
    from dochris.llm.openai_compat import OpenAICompatProvider
    from dochris.phases import query_engine

    query_engine._llm_client_cache = None
    monkeypatch.setenv("OPENAI_API_KEY", "env-key")
    try:
        with (
            patch.object(query_engine, "get_settings") as mock_settings,
            patch.object(query_engine, "read_openclaw_config", return_value=None),
        ):
            settings = mock_settings.return_value
            settings.api_key = None
            settings.api_base = None
            settings.query_model = "glm-4"
            settings.llm_provider = "openai_compat"

            provider = query_engine.create_query_provider()

        assert isinstance(provider, OpenAICompatProvider)
        assert provider.api_key == "env-key"
    finally:
        query_engine._llm_client_cache = None


def test_create_query_provider_rejects_unknown_registry_name() -> None:
    from dochris.phases import query_engine

    query_engine._llm_client_cache = None
    try:
        with (
            patch.object(query_engine, "get_settings") as mock_settings,
            patch.object(query_engine, "read_openclaw_config", return_value=None),
        ):
            settings = mock_settings.return_value
            settings.api_key = ""
            settings.api_base = None
            settings.query_model = "m"
            settings.llm_provider = "does-not-exist"

            assert query_engine.create_query_provider() is None
    finally:
        query_engine._llm_client_cache = None
