"""生成质量指标测试（RAG-03/04/05 启发式指标 + RAG-06 评测元数据）。"""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock, patch

import pytest

from dochris.eval.rag_metrics import compute_generation_metrics
from dochris.eval.runner import RAGEvaluator
from dochris.eval.schemas import QueryEvidence


def _evidence(text: str, manifest_id: str = "SRC-0001") -> QueryEvidence:
    return QueryEvidence(
        text=text,
        source="wiki",
        manifest_id=manifest_id,
        score=1.0,
        rank=1,
        channel="keyword",
    )


def test_faithfulness_measures_evidence_support() -> None:
    evidence = [_evidence("房价软着陆是指价格通过长时间价值回归实现缓慢下跌")]
    answer = "软着陆是价格缓慢下跌的过程。这条句子完全无关凭空编造。"
    metrics = compute_generation_metrics("什么是软着陆", answer, evidence)

    assert 0.0 < metrics["faithfulness"] < 1.0


def test_faithfulness_full_support_scores_one() -> None:
    evidence = [_evidence("软着陆是价格通过价值回归缓慢下跌")]
    answer = "软着陆指价格通过价值回归实现缓慢下跌。"
    metrics = compute_generation_metrics("什么是软着陆", answer, evidence)

    assert metrics["faithfulness"] == 1.0


def test_answer_relevance_covers_question_terms() -> None:
    evidence = [_evidence("软着陆是缓慢下跌")]
    metrics = compute_generation_metrics("什么是软着陆", "软着陆是指缓慢下跌", evidence)

    assert metrics["answer_relevance"] > 0


def test_context_relevance_counts_relevant_evidence() -> None:
    evidence = [
        _evidence("软着陆是价格缓慢下跌"),
        _evidence("完全无关的内容：今天天气不错"),
    ]
    metrics = compute_generation_metrics("软着陆是什么", "", evidence)

    assert metrics["context_relevance"] == 0.5


def test_citation_correctness_validates_refs() -> None:
    evidence = [_evidence("证据一"), _evidence("证据二")]
    good = compute_generation_metrics("q", "回答 [S1] [S2]", evidence)
    bad = compute_generation_metrics("q", "回答 [S1] [S9]", evidence)

    assert good["citation_correctness"] == 1.0
    assert bad["citation_correctness"] == 0.5


def test_citation_correctness_zero_without_refs() -> None:
    metrics = compute_generation_metrics("q", "没有任何引用的回答", [_evidence("证据")])

    assert metrics["citation_correctness"] == 0.0


@pytest.mark.fast
@pytest.mark.asyncio
async def test_eval_report_records_environment_metadata() -> None:
    """每次评测报告必须保存模型/provider/语料/commit 元数据（RAG-06）。"""
    evaluator = RAGEvaluator(k=3, rerank=False, mode="combined", concurrency=2)

    async def fake_query_async(question, **kwargs):
        return {
            "query": question,
            "concepts": [],
            "summaries": [],
            "vector_results": [],
            "search_sources": [],
            "answer": "回答",
            "time_seconds": 0.1,
        }

    sample = MagicMock()
    sample.id = "q1"
    sample.question = "问题"

    with (
        patch("dochris.phases.phase3_query.query_async", new=fake_query_async),
        patch("dochris.settings.get_settings") as mock_settings,
        patch(
            "subprocess.run",
            return_value=MagicMock(returncode=0, stdout="abc123def\n"),
        ),
    ):
        mock_settings.return_value.query_model = "glm-4-flash"
        mock_settings.return_value.llm_provider = "openai_compat"
        mock_settings.return_value.embedding_model = "BAAI/bge-small-zh-v1.5"
        mock_settings.return_value.vector_store = "chromadb"
        mock_settings.return_value.workspace = "/tmp/ws"

        report = await evaluator.evaluate_dataset([sample])

    config = report.config
    assert config["k"] == 3
    assert config["concurrency"] == 2
    assert config["model"] == "glm-4-flash"
    assert config["llm_provider"] == "openai_compat"
    assert config["commit_sha"] == "abc123def"


@pytest.mark.fast
@pytest.mark.asyncio
async def test_eval_runner_bounded_concurrency_preserves_order() -> None:
    """有界并发（RAG-02）不能打乱结果顺序。"""
    evaluator = RAGEvaluator(concurrency=3)

    async def fake_query_async(question, **kwargs):
        await asyncio.sleep(0.01)
        return {
            "query": question,
            "concepts": [],
            "summaries": [],
            "vector_results": [],
            "search_sources": [],
            "answer": "",
            "time_seconds": 0,
        }

    samples = [MagicMock(id=f"q{i}", question=f"问题{i}") for i in range(5)]

    with patch("dochris.phases.phase3_query.query_async", new=fake_query_async):
        report = await evaluator.evaluate_dataset(samples)

    assert [r.sample_id for r in report.results] == [f"q{i}" for i in range(5)]
