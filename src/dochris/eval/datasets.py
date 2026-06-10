"""评估数据集加载与保存

支持 JSONL 格式的 golden set 文件，每行一个 JSON 对象：
    {"id": "q1", "question": "...", "expected_source_ids": ["SRC-0001"], "ground_truth": "..."}

用法：
    samples = load_dataset("eval/rag_golden.jsonl")
    save_dataset(samples, "eval/rag_golden_v2.jsonl")
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from dochris.eval.schemas import RAGEvalSample

logger = logging.getLogger(__name__)


def load_dataset(path: str | Path) -> list[RAGEvalSample]:
    """从 JSONL 文件加载评估样本。

    Args:
        path: JSONL 文件路径

    Returns:
        RAGEvalSample 列表

    Raises:
        FileNotFoundError: 文件不存在
        ValueError: JSON 行格式错误
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"评估数据集文件不存在: {path}")

    samples: list[RAGEvalSample] = []
    errors: list[str] = []

    with open(path, encoding="utf-8") as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line or line.startswith("#"):
                continue

            try:
                data = json.loads(line)
                sample = _parse_sample(data, line_num)
                samples.append(sample)
            except (json.JSONDecodeError, KeyError, TypeError) as e:
                errors.append(f"第 {line_num} 行解析失败: {e}")
                continue

    if errors:
        logger.warning("数据集加载有 %d 个错误:\n%s", len(errors), "\n".join(errors))

    logger.info("加载评估数据集: %s (%d 条样本)", path, len(samples))
    return samples


def save_dataset(samples: list[RAGEvalSample], path: str | Path) -> None:
    """将评估样本保存为 JSONL 文件。

    Args:
        samples: 评估样本列表
        path: 输出路径
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    with open(path, "w", encoding="utf-8") as f:
        for sample in samples:
            data = {
                "id": sample.id,
                "question": sample.question,
                "expected_source_ids": sample.expected_source_ids,
            }
            if sample.ground_truth:
                data["ground_truth"] = sample.ground_truth
            if sample.tags:
                data["tags"] = sample.tags
            if sample.metadata:
                data["metadata"] = sample.metadata

            f.write(json.dumps(data, ensure_ascii=False) + "\n")

    logger.info("保存评估数据集: %s (%d 条样本)", path, len(samples))


def _parse_sample(data: dict, line_num: int) -> RAGEvalSample:
    """解析单行 JSON 为 RAGEvalSample。

    Args:
        data: JSON 对象
        line_num: 行号（用于错误提示）

    Returns:
        RAGEvalSample 实例

    Raises:
        KeyError: 缺少必要字段
    """
    if "id" not in data:
        raise KeyError(f"第 {line_num} 行缺少 'id' 字段")
    if "question" not in data:
        raise KeyError(f"第 {line_num} 行缺少 'question' 字段")

    return RAGEvalSample(
        id=data["id"],
        question=data["question"],
        expected_source_ids=data.get("expected_source_ids", []),
        ground_truth=data.get("ground_truth"),
        tags=data.get("tags", []),
        metadata=data.get("metadata", {}),
    )


def generate_sample_questions(
    manifest_ids: list[str],
    titles: dict[str, str],
    count: int | None = None,
) -> list[RAGEvalSample]:
    """从 manifest ID 和标题生成基础评估样本。

    这是一个简单的辅助工具，生成的样本只有 id、question 和 expected_source_ids，
    不含 ground_truth。适合快速创建 baseline 测试集。

    Args:
        manifest_ids: manifest ID 列表
        titles: manifest ID → 标题映射
        count: 生成数量上限（默认不限制）

    Returns:
        基础 RAGEvalSample 列表
    """
    samples: list[RAGEvalSample] = []
    for i, mid in enumerate(manifest_ids):
        title = titles.get(mid, f"文档 {mid}")
        samples.append(
            RAGEvalSample(
                id=f"auto_{i:04d}",
                question=f"什么是{title}？",
                expected_source_ids=[mid],
                tags=["auto-generated"],
            )
        )

    if count is not None:
        samples = samples[:count]

    return samples
