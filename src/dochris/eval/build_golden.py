"""Golden dataset 构建器（RAG-01）。

把 ``eval/golden_questions.jsonl``（题目 ↔ 文档标题）解析为可执行的
``rag_golden.jsonl``（题目 ↔ SRC-NNNN），使 golden set 与具体工作区的
manifest 编号解耦：换工作区/重排编号后重新运行本模块即可。

用法：
    python -m dochris.eval.build_golden \
        --workspace ~/.dochris/knowledge-base \
        --output eval/rag_golden.jsonl

未解析到 manifest 的题目默认跳过并在 stderr 列出；``--strict`` 时报错退出。
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Any

from dochris.manifest import get_all_manifests

logger = logging.getLogger(__name__)

DEFAULT_QUESTIONS_PATH = Path(__file__).resolve().parents[3] / "eval" / "golden_questions.jsonl"


def load_questions(path: Path) -> list[dict[str, Any]]:
    """加载题目文件并校验必需字段。"""
    questions: list[dict[str, Any]] = []
    for line_num, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        data = json.loads(line)
        missing = [
            key for key in ("id", "question", "source_title", "ground_truth") if not data.get(key)
        ]
        if missing:
            raise ValueError(f"{path.name} 第 {line_num} 行缺少字段: {missing}")
        questions.append(data)
    return questions


def _normalize_title(value: str) -> str:
    stem = Path(value).stem
    return stem.strip().lower()


def resolve_questions(
    questions: list[dict[str, Any]],
    manifests: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[str]]:
    """把 source_title 解析为 manifest id。

    匹配规则（不区分大小写）：manifest title 精确等于标题、等于文件名、
    或文件路径的 stem 与标题一致。

    Returns:
        (resolved, unresolved_titles)
    """
    by_title: dict[str, str] = {}
    for manifest in manifests:
        manifest_id = manifest.get("id")
        if not manifest_id:
            continue
        for candidate in (
            manifest.get("title", ""),
            Path(str(manifest.get("file_path", ""))).name,
            Path(str(manifest.get("file_path", ""))).stem,
        ):
            key = _normalize_title(str(candidate))
            if key and key not in by_title:
                by_title[key] = str(manifest_id)

    resolved: list[dict[str, Any]] = []
    unresolved: list[str] = []
    for question in questions:
        key = _normalize_title(str(question["source_title"]))
        manifest_id = by_title.get(key)
        if manifest_id is None:
            unresolved.append(str(question["source_title"]))
            continue
        resolved.append(
            {
                "id": question["id"],
                "question": question["question"],
                "expected_source_ids": [manifest_id],
                "ground_truth": question["ground_truth"],
            }
        )
    return resolved, unresolved


def build_golden_set(
    workspace: Path,
    questions_path: Path = DEFAULT_QUESTIONS_PATH,
    output_path: Path | None = None,
    *,
    strict: bool = False,
) -> tuple[list[dict[str, Any]], list[str]]:
    """构建 golden set；``output_path`` 给出时写入 JSONL 文件。"""
    questions = load_questions(questions_path)
    manifests = get_all_manifests(workspace)
    resolved, unresolved = resolve_questions(questions, manifests)

    if strict and unresolved:
        raise ValueError(f"未解析到 manifest 的题目来源: {sorted(set(unresolved))}")

    if output_path is not None:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as handle:
            for item in resolved:
                handle.write(json.dumps(item, ensure_ascii=False) + "\n")
        logger.info("已写入 %d 条 golden set 到 %s", len(resolved), output_path)
    return resolved, unresolved


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="从题目集构建 RAG golden set")
    parser.add_argument("--workspace", required=True, help="知识库工作区路径")
    parser.add_argument("--questions", default=str(DEFAULT_QUESTIONS_PATH), help="题目 JSONL 路径")
    parser.add_argument("--output", default="eval/rag_golden.jsonl", help="输出 JSONL 路径")
    parser.add_argument(
        "--strict", action="store_true", help="存在未解析题目时报错退出（默认仅跳过）"
    )
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO)
    resolved, unresolved = build_golden_set(
        workspace=Path(args.workspace),
        questions_path=Path(args.questions),
        output_path=Path(args.output),
        strict=args.strict,
    )
    if unresolved:
        print(
            f"未解析的来源（跳过 {len(unresolved)} 条）: {sorted(set(unresolved))}", file=sys.stderr
        )
    print(f"已解析 {len(resolved)} 条 → {args.output}")
    return 0 if resolved else 1


if __name__ == "__main__":
    raise SystemExit(main())
