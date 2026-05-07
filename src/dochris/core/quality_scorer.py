#!/usr/bin/env python3
"""
质量评分 (从 phase2_compilation.py 迁移)

评分维度（总分 100）：
1. detailed_summary 长度 (0-25)
2. key_points 完整性 (0-30)
3. 学习价值 (0-15)
4. 信息密度 (0-5)
5. one_line 质量 (0-5)
6. 概念完整性 (0-10)
7. 模板文字检测 (-10)
"""

import logging
import re
from dataclasses import dataclass, field
from typing import Any

from dochris.settings import INFO_KEYWORDS, LEARNING_KEYWORDS, TEMPLATE_DEDUCTION, TEMPLATE_PATTERNS
from dochris.settings.config import get_settings

logger = logging.getLogger(__name__)


# ============================================================
# 数据结构
# ============================================================


@dataclass(frozen=True)
class DimensionScore:
    """单个维度的评分结果"""

    name: str
    points: int
    max_points: int
    detail: str


@dataclass
class QualityReport:
    """质量评分完整报告"""

    total: int
    dimensions: list[DimensionScore] = field(default_factory=list)
    template_detected: bool = False


# ============================================================
# 工具函数
# ============================================================


def _safe_str(value: Any) -> str:
    """防御性字符串提取"""
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    return str(value) if value else ""


def _safe_list(value: Any) -> list:
    """防御性列表提取"""
    if value is None:
        return []
    if isinstance(value, list):
        return value
    logger.warning(f"Expected list, got {type(value).__name__}, converting")
    return []


def _tiered_score(value: int, tiers: list[tuple[int, int]], default: int = 0) -> int:
    """通用阶梯式分段评分。tiers 从高到低排列 [(阈值, 分数), ...]"""
    for threshold, points in tiers:
        if value >= threshold:
            return points
    return default


# 常见构词后缀：当这些字紧跟在关键词后时，关键词可能是更长词的组成部分
# 仅包含明确构成不同概念的后缀（如 "关键"+"词"="关键词"）
_COMPOUND_SUFFIXES = frozenset("词性化者论学")


def _count_keyword_matches(text: str, keywords: list[str]) -> int:
    """计算关键词命中数，避免中文子串误判

    例如 "关键" 不会匹配 "关键词"（"词" 是构词后缀），但会匹配 "关键的方法"。
    """
    count = 0
    for kw in keywords:
        for m in re.finditer(re.escape(kw), text):
            end = m.end()
            # 如果关键词后面紧跟构词后缀字符，视为更长词的组成部分，跳过
            if end < len(text) and text[end] in _COMPOUND_SUFFIXES:
                continue
            count += 1
            break  # 每个关键词只计一次
    return count


# ============================================================
# 维度子函数
# ============================================================


def _score_detail_length(ds: str) -> DimensionScore:
    """detailed_summary 长度评分 (0-25)"""
    ds_len = len(ds)
    tiers = [
        (1500, 25),
        (1200, 22),
        (1000, 19),
        (800, 16),
        (600, 12),
        (400, 8),
        (200, 4),
    ]
    points = _tiered_score(ds_len, tiers)
    return DimensionScore(
        name="detail_length",
        points=points,
        max_points=25,
        detail=f"len={ds_len}",
    )


def _score_key_points(kp: list) -> DimensionScore:
    """key_points 数量评分 (0-30)，过滤空字符串"""
    valid_kps = [k for k in kp if isinstance(k, str) and k.strip()]
    kp_len = len(valid_kps)
    tiers = [
        (5, 30),
        (4, 26),
        (3, 22),
        (2, 14),
        (1, 7),
    ]
    points = _tiered_score(kp_len, tiers)
    return DimensionScore(
        name="key_points",
        points=points,
        max_points=30,
        detail=f"count={kp_len} (valid)",
    )


def _score_learning_value(text: str) -> DimensionScore:
    """学习价值关键词评分 (0-15)，使用精确匹配避免子串误判"""
    count = _count_keyword_matches(text, LEARNING_KEYWORDS)
    tiers = [
        (10, 15),
        (8, 12),
        (6, 9),
        (4, 6),
        (2, 3),
        (1, 1),
    ]
    points = _tiered_score(count, tiers)
    return DimensionScore(
        name="learning_value",
        points=points,
        max_points=15,
        detail=f"keywords={count}",
    )


def _score_info_density(text: str) -> DimensionScore:
    """信息密度关键词评分 (0-5)，使用精确匹配避免子串误判"""
    count = _count_keyword_matches(text, INFO_KEYWORDS)
    tiers = [
        (5, 5),
        (3, 4),
        (1, 2),
    ]
    points = _tiered_score(count, tiers)
    return DimensionScore(
        name="info_density",
        points=points,
        max_points=5,
        detail=f"keywords={count}",
    )


def _score_one_line(text: str) -> DimensionScore:
    """单行摘要质量评分 (0-5)"""
    text_len = len(text)
    if 20 <= text_len <= 50:
        points = 5
    elif text_len >= 10:
        points = 3
    elif text_len >= 5:
        points = 1
    else:
        points = 0
    return DimensionScore(
        name="one_line",
        points=points,
        max_points=5,
        detail=f"len={text_len}",
    )


def _score_concepts(concepts: list) -> DimensionScore:
    """概念完整性评分 (0-10)，过滤空字符串

    支持 list[str] 和 list[dict] 两种格式：
    - list[str]: 直接计数有效字符串
    - list[dict]: 统计包含 'name' 键的有效字典
    """
    valid = [c for c in concepts if isinstance(c, str) and c.strip()]
    if not valid:
        # LLM 可能返回 list[dict] 格式，如 [{"name": "概念", "description": "..."}]
        valid = [
            c
            for c in concepts
            if isinstance(c, dict) and c.get("name") and str(c.get("name", "")).strip()
        ]
    c_len = len(valid)
    tiers = [
        (5, 10),
        (4, 8),
        (3, 6),
        (2, 4),
        (1, 2),
    ]
    points = _tiered_score(c_len, tiers)
    return DimensionScore(
        name="concepts",
        points=points,
        max_points=10,
        detail=f"count={c_len} (valid)",
    )


def _detect_template(text: str) -> DimensionScore:
    """模板文字检测 (-10)

    使用词边界匹配避免误报。例如正文中的"播客总结了..."不应被判定为模板。
    只匹配出现在文本开头 200 字符内的模板模式，因为模板文字通常出现在
    摘要的开头而非正文中间。
    """
    # 只在文本前 200 字符内检测模板模式
    header = text[:200]
    detected = any(pattern in header for pattern in TEMPLATE_PATTERNS)
    points = -TEMPLATE_DEDUCTION if detected else 0
    return DimensionScore(
        name="template",
        points=points,
        max_points=0,
        detail=f"detected={detected}",
    )


# ============================================================
# 日志辅助
# ============================================================


def _log_quality_result(
    summary: dict[str, Any],
    total: int,
    dimensions: list[DimensionScore],
) -> None:
    """记录评分详情"""
    dims_str = ", ".join(f"{d.name}={d.points}" for d in dimensions)
    logger.debug(f"Quality score={total}/100: {dims_str}")

    if total < 30:
        ds = _safe_str(summary.get("detailed_summary"))
        logger.warning(
            f"Low quality score detected: {total}. "
            f"Summary keys: {list(summary.keys())}. "
            f"Values: ds_type={type(summary.get('detailed_summary')).__name__}, "
            f"kp_type={type(summary.get('key_points')).__name__}, "
            f"concepts_type={type(summary.get('concepts')).__name__}, "
            f"ds_preview={ds[:50] if ds else 'empty'}"
        )


# ============================================================
# 公共 API
# ============================================================


def _compute_dimensions(summary: dict[str, Any]) -> tuple[list[DimensionScore], int]:
    """计算各维度评分（内部共享函数）

    Returns:
        (dimensions, total) 评分维度列表和总分
    """
    ds = _safe_str(summary.get("detailed_summary"))
    ds_lower = ds.lower()

    # 超长文本惩罚
    overflow = len(ds) - 3000
    penalty = min(10, overflow // 500) if overflow > 0 else 0

    dimensions = [
        _score_detail_length(ds),
        _score_key_points(_safe_list(summary.get("key_points"))),
        _score_learning_value(ds_lower),
        _score_info_density(ds_lower),
        _score_one_line(_safe_str(summary.get("one_line"))),
        _score_concepts(_safe_list(summary.get("concepts"))),
        _detect_template(ds_lower),
    ]

    total = max(0, min(sum(d.points for d in dimensions) - penalty, 100))
    return dimensions, total


def score_summary_quality_v4(summary: dict[str, Any] | None) -> int:
    """全面优化版质量评分（v4）- 返回总分

    签名完全不变，调用者零改动。

    Args:
        summary: 包含 detailed_summary, key_points, one_line, concepts 的字典

    Returns:
        质量评分 (0-100)
    """
    if not isinstance(summary, dict):
        logger.debug("summary is not dict, returning 0")
        return 0

    dimensions, total = _compute_dimensions(summary)
    _log_quality_result(summary, total, dimensions)
    return total


def score_summary_quality_v4_report(
    summary: dict[str, Any] | None,
) -> QualityReport:
    """返回评分明细报告，供 API/Web UI 使用

    Args:
        summary: 包含 detailed_summary, key_points, one_line, concepts 的字典

    Returns:
        QualityReport 对象，含各维度评分明细
    """
    if not isinstance(summary, dict):
        return QualityReport(total=0)

    dimensions, total = _compute_dimensions(summary)
    template_detected = any(d.name == "template" and d.points < 0 for d in dimensions)
    _log_quality_result(summary, total, dimensions)

    return QualityReport(
        total=total,
        dimensions=dimensions,
        template_detected=template_detected,
    )


def get_quality_threshold() -> int:
    """获取质量阈值（从 settings 统一读取）"""
    return get_settings().min_quality_score
