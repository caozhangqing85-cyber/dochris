"""RAG-01 golden dataset 测试：题目集规模/结构与解析器行为。"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from dochris.eval.build_golden import (
    DEFAULT_QUESTIONS_PATH,
    build_golden_set,
    load_questions,
    resolve_questions,
)

pytestmark = pytest.mark.fast


def _questions() -> list[dict[str, object]]:
    return load_questions(DEFAULT_QUESTIONS_PATH)


def test_golden_question_set_has_at_least_50_unique_entries() -> None:
    """RAG-01 验收：至少 50 条、id 唯一、字段完整。"""
    questions = _questions()

    assert len(questions) >= 50
    ids = [str(q["id"]) for q in questions]
    assert len(ids) == len(set(ids))
    for question in questions:
        assert str(question["question"]).strip()
        assert str(question["source_title"]).strip()
        assert str(question["ground_truth"]).strip()


def test_golden_questions_cover_major_domains() -> None:
    questions = _questions()
    titles = {str(q["source_title"]).lower() for q in questions}

    expected_domains = {
        "readme",  # 总览
        "installation",  # 安装
        "configuration",  # 配置
        "query",  # 查询
        "docker",  # 部署
        "quality",  # 质量
        "promote",  # 晋升
        "graph",  # 图谱
        "plugins",  # 插件
        "vector-stores",  # 向量
        "release",  # 发布
    }
    assert expected_domains <= titles


def test_load_questions_rejects_missing_fields(tmp_path: Path) -> None:
    bad = tmp_path / "bad.jsonl"
    bad.write_text('{"id": "q1", "question": "?", "source_title": "README"}\n', encoding="utf-8")
    with pytest.raises(ValueError, match="缺少字段"):
        load_questions(bad)


def test_resolve_questions_matches_titles_and_stems() -> None:
    manifests = [
        {"id": "SRC-0001", "title": "README.md", "file_path": "raw/README.md"},
        {"id": "SRC-0002", "title": "QUICKSTART", "file_path": "raw/docs/QUICKSTART.md"},
    ]
    wanted = {"gq-001", "gq-002", "gq-005", "gq-008"}
    questions = [q for q in _questions() if str(q["id"]) in wanted]
    assert len(questions) == 4
    resolved, unresolved = resolve_questions(questions, manifests)

    by_id = {item["id"]: item for item in resolved}
    assert by_id["gq-001"]["expected_source_ids"] == ["SRC-0001"]
    assert by_id["gq-002"]["expected_source_ids"] == ["SRC-0001"]
    assert by_id["gq-008"]["expected_source_ids"] == ["SRC-0002"]
    assert "installation" in [title.lower() for title in unresolved]


def test_build_golden_set_writes_jsonl_and_reports_unresolved(tmp_path: Path) -> None:
    manifests = [{"id": "SRC-0001", "title": "README.md", "file_path": "raw/README.md"}]

    class _Workspace:
        """get_all_manifests 以 Path 为参数，这里用 monkeypatch 替代。"""

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(
            "dochris.eval.build_golden.get_all_manifests",
            lambda _workspace: manifests,
        )
        resolved, unresolved = build_golden_set(
            workspace=tmp_path,
            output_path=tmp_path / "rag_golden.jsonl",
        )

    assert resolved, "至少 README 条目应被解析"
    assert unresolved, "其余来源应被报告为未解析"
    lines = (tmp_path / "rag_golden.jsonl").read_text(encoding="utf-8").strip().splitlines()
    parsed = [json.loads(line) for line in lines]
    assert parsed == resolved
    assert set(parsed[0]) == {"id", "question", "expected_source_ids", "ground_truth"}


def test_build_golden_set_strict_fails_on_unresolved(tmp_path: Path) -> None:
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr("dochris.eval.build_golden.get_all_manifests", lambda _workspace: [])
        with pytest.raises(ValueError, match="未解析到 manifest"):
            build_golden_set(workspace=tmp_path, strict=True)
