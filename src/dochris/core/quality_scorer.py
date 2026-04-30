#!/usr/bin/env python3
"""
质量评分 (从 phase2_compilation.py 迁移)
"""

import logging
from typing import Any

from dochris.settings import INFO_KEYWORDS, LEARNING_KEYWORDS, TEMPLATE_PATTERNS

logger = logging.getLogger(__name__)


def score_summary_quality_v4(summary: dict[str, Any] | None) -> int:
    """
    全面优化版质量评分（v4）- 聚焦学习价值和内容质量

    评分维度：
    1. detailed_summary 长度 (0-35) - 提高权重
    2. key_points 完整性 (0-40) - 降低要求
    3. 学习价值 (0-25) - 新增，最重要的！
    4. 信息密度 (0-10) - 新增
    5. one_line 质量 (0-10) - 新增
    6. 概念完整性 (0-20) - 保持不变
    7. 模板文字检测 - 扣分制（扣20分）

    总分: 100 分
    及格线: 85 分
    """
    score = 0

    # 防御性检查：处理 None 和非 dict 类型
    if summary is None:
        logger.debug("summary is None, returning 0")
        return 0
    if not isinstance(summary, dict):
        logger.warning(f"summary is not dict (type={type(summary).__name__}), returning 0")
        return 0

    # 1. detailed_summary 长度 (0-35)
    ds = summary.get("detailed_summary", "")
    # 处理 None/null 值
    if ds is None:
        ds = ""
    elif not isinstance(ds, str):
        ds = str(ds) if ds else ""
    ds_len = len(ds)
    if ds_len >= 1500:
        score += 35
    elif ds_len >= 1200:
        score += 30
    elif ds_len >= 1000:
        score += 25
    elif ds_len >= 800:
        score += 20
    elif ds_len >= 600:
        score += 15
    elif ds_len >= 400:
        score += 10
    elif ds_len >= 200:
        score += 5

    # 2. key_points 完整性 (0-40) - 降低要求
    kp = summary.get("key_points", [])
    # 处理 None/null 值，确保是列表
    if kp is None:
        kp = []
    elif not isinstance(kp, list):
        logger.warning(f"key_points is not list (type={type(kp).__name__}), converting")
        kp = []
    kp_len = len(kp)

    if kp_len >= 5:
        score += 40
    elif kp_len >= 4:
        score += 35
    elif kp_len >= 3:
        score += 30
    elif kp_len >= 2:
        score += 20
    elif kp_len >= 1:
        score += 10
    # 空数组：0 分

    # 3. 学习价值 (0-25) - 新增，最重要的！
    ds_lower = ds.lower()
    learning_count = sum(1 for kw in LEARNING_KEYWORDS if kw in ds_lower)

    if learning_count >= 10:
        score += 25
    elif learning_count >= 8:
        score += 20
    elif learning_count >= 6:
        score += 15
    elif learning_count >= 4:
        score += 10
    elif learning_count >= 2:
        score += 5
    elif learning_count >= 1:
        score += 2
    # 0 个：0 分

    # 4. 信息密度 (0-10) - 新增
    info_count = sum(1 for kw in INFO_KEYWORDS if kw in ds_lower)

    if info_count >= 5:
        score += 10
    elif info_count >= 3:
        score += 7
    elif info_count >= 1:
        score += 3
    # 0 个：0 分

    # 5. one_line 质量 (0-10) - 新增
    one_line = summary.get("one_line", "")
    # 处理 None/null 值
    if one_line is None:
        one_line = ""
    elif not isinstance(one_line, str):
        one_line = str(one_line) if one_line else ""

    if len(one_line) >= 20 and len(one_line) <= 50:
        score += 10
    elif len(one_line) >= 10:
        score += 5
    elif len(one_line) >= 5:
        score += 2
    # 太短或太长：0 分

    # 6. 概念完整性 (0-20) - 保持不变
    concepts = summary.get("concepts", [])
    # 处理 None/null 值，确保是列表
    if concepts is None:
        concepts = []
    elif not isinstance(concepts, list):
        logger.warning(f"concepts is not list (type={type(concepts).__name__}), converting")
        concepts = []
    concepts_len = len(concepts)

    if concepts_len >= 5:
        score += 20
    elif concepts_len >= 4:
        score += 15
    elif concepts_len >= 3:
        score += 10
    elif concepts_len >= 2:
        score += 5
    elif concepts_len >= 1:
        score += 2
    # 空数组：0 分

    # 7. 模板文字检测 - 扣分制（扣20分）
    template_detected = any(pattern in ds_lower for pattern in TEMPLATE_PATTERNS)

    if template_detected:
        score = max(0, score - 20)  # 扣20分，不低于0
        logger.warning("Template text detected, -20 points applied")

    # 详细的调试日志 - 帮助诊断"首次总是10分"问题
    logger.debug(
        f"Quality score={score}/100: "
        f"ds_len={ds_len}({ds[:50] if ds else 'empty'}...), "
        f"kp_len={kp_len}, "
        f"learning={learning_count}, "
        f"info={info_count}, "
        f"one_line_len={len(one_line)}({one_line[:30] if one_line else 'empty'}...), "
        f"concepts={concepts_len}, "
        f"template={template_detected}"
    )

    # 如果得分异常低（<30），记录警告以便排查
    if score < 30:
        logger.warning(
            f"Low quality score detected: {score}. "
            f"Summary keys: {list(summary.keys())}. "
            f"Values: ds_type={type(summary.get('detailed_summary')).__name__}, "
            f"kp_type={type(summary.get('key_points')).__name__}, "
            f"concepts_type={type(summary.get('concepts')).__name__}"
        )

    # 限制最高分为 100
    return min(score, 100)


def get_quality_threshold() -> int:
    """获取质量阈值"""
    return 85
