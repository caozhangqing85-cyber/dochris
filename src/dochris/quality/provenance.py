#!/usr/bin/env python3
"""
Layer 0: 溯源标签系统 (Provenance Labeling)

为每个编译产物标注内容来源可信度，遵循 Karpathy LLM-Wiki 理论：
"内容可信度来源于可追溯性"。

四种溯源标签：
  extracted  — 内容直接来自源文档，高置信度
  merged     — 多段内容合并/重组成，中置信度
  inferred   — LLM 推断/补充的内容，需人工确认
  ambiguous  — 无法确认来源或低质量，需人工审核

判定策略：
  1. 编译模式：直接编译 (text < 20K) → extracted 倾向；Map-Reduce (text > 20K) → merged 倾向
  2. 概念溯源：概念名/解释在源文本中有精确匹配 → extracted；仅有模糊匹配 → inferred
  3. 摘要溯源：one_line 和 key_points 中的短语能在源文本中找到 → extracted
  4. 异常信号：模板文字、自引用、概念缺解释 → 降级为 ambiguous
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class ProvenanceLabel(StrEnum):
    """溯源标签枚举"""

    EXTRACTED = "extracted"
    MERGED = "merged"
    INFERRED = "inferred"
    AMBIGUOUS = "ambiguous"


# 置信度映射（用于前端展示和晋升决策）
PROVENANCE_CONFIDENCE: dict[ProvenanceLabel, float] = {
    ProvenanceLabel.EXTRACTED: 0.9,
    ProvenanceLabel.MERGED: 0.7,
    ProvenanceLabel.INFERRED: 0.5,
    ProvenanceLabel.AMBIGUOUS: 0.2,
}

# 模板文字模式（出现在摘要开头则为可疑信号）
_TEMPLATE_PATTERNS = [
    "该文档",
    "本文档",
    "这份文件",
    "the document",
    "this document",
    "以下是对",
    "以下是关于",
    "以下是总结",
]

# 自引用检测模式
_SELF_REF_PATTERNS = [
    r"本文(?:档|件|章|节)",
    r"该(?:文档|文件|章节|文章)",
    r"这篇文章",
    r"我们(?:将|可以|会)",
]


@dataclass
class ConceptProvenance:
    """单个概念的溯源结果"""

    name: str
    label: ProvenanceLabel
    source_match: str | None = None
    """源文本中匹配到的原文片段"""


@dataclass
class ProvenanceResult:
    """完整编译产物的溯源结果"""

    overall_label: ProvenanceLabel
    confidence: float
    summary_label: ProvenanceLabel
    concepts: list[ConceptProvenance] = field(default_factory=list)
    signals: list[str] = field(default_factory=list)
    """溯源判定中检测到的信号列表"""


def _find_in_source(text: str, source: str, window: int = 60) -> str | None:
    """在源文本中查找 text 的精确匹配，返回匹配上下文

    支持模糊匹配：去掉标点后进行子串搜索。

    Args:
        text: 待查找的文本片段
        source: 源文本
        window: 匹配时截取的上下文长度

    Returns:
        匹配到的上下文片段，或 None
    """
    if not text or not source:
        return None

    # 精确匹配
    if text in source:
        idx = source.index(text)
        start = max(0, idx - 10)
        end = min(len(source), idx + len(text) + 10)
        return source[start:end]

    # 去标点模糊匹配（中文场景）
    _punct_re = re.compile(r"[，。！？、；：\"\"''（）\{\}【】\s]+")
    clean = _punct_re.sub("", text)
    clean_source = _punct_re.sub("", source)
    if len(clean) >= 4 and clean in clean_source:
        idx = clean_source.index(clean)
        context_start = max(0, idx - 20)
        context_end = min(len(clean_source), idx + len(clean) + 20)
        return clean_source[context_start:context_end]

    return None


def _count_key_phrases_in_source(phrases: list[str], source: str) -> int:
    """统计 key_points 中有多少短语能在源文本中找到

    Args:
        phrases: 关键要点列表
        source: 源文本

    Returns:
        匹配到的短语数量
    """
    count = 0
    for phrase in phrases:
        if not phrase or not isinstance(phrase, str):
            continue
        # 取短语的前 20 个字符进行匹配（避免过长导致匹配失败）
        segment = phrase.strip()[:20]
        if segment and _find_in_source(segment, source):
            count += 1
    return count


def _detect_template_or_selfref(text: str) -> list[str]:
    """检测模板文字和自引用模式

    Args:
        text: 待检测文本

    Returns:
        检测到的信号列表
    """
    signals: list[str] = []
    header = text[:500]

    for pattern in _TEMPLATE_PATTERNS:
        if pattern in header:
            signals.append(f"模板文字: '{pattern}'")
            break

    for pattern in _SELF_REF_PATTERNS:
        if re.search(pattern, text):
            signals.append(f"自引用: '{pattern}'")
            break

    return signals


def _determine_compilation_mode(source_text: str) -> str:
    """推断编译模式

    根据 source_text 长度推断使用的编译策略：
    - < 20K chars: 直接编译（single-pass）
    - 20K-60K chars: Map-Reduce
    - > 60K chars: 分层摘要

    Args:
        source_text: 源文本

    Returns:
        编译模式标识
    """
    length = len(source_text)
    if length < 20_000:
        return "direct"
    elif length < 60_000:
        return "map_reduce"
    else:
        return "hierarchical"


def _classify_concept(
    concept_name: str,
    concept_explanation: str,
    source_text: str,
) -> ConceptProvenance:
    """为单个概念判定溯源标签

    判定逻辑：
    1. 概念名在源文本中精确出现 → extracted
    2. 概念解释中有内容在源文本中找到 → extracted
    3. 概念名部分匹配或模糊匹配 → inferred
    4. 完全无法匹配 → ambiguous

    Args:
        concept_name: 概念名称
        concept_explanation: 概念解释
        source_text: 源文本

    Returns:
        概念溯源结果
    """
    # 精确匹配概念名
    match = _find_in_source(concept_name, source_text)
    if match:
        return ConceptProvenance(
            name=concept_name,
            label=ProvenanceLabel.EXTRACTED,
            source_match=match,
        )

    # 匹配概念解释中的关键片段
    if concept_explanation:
        # 取解释的前 15 个字符尝试匹配
        seg = concept_explanation.strip()[:15]
        if seg and len(seg) >= 4:
            match = _find_in_source(seg, source_text)
            if match:
                return ConceptProvenance(
                    name=concept_name,
                    label=ProvenanceLabel.EXTRACTED,
                    source_match=match,
                )

    # 模糊匹配：概念名中的关键词
    keywords = re.split(r"[的与和及/\\s]+", concept_name)
    keywords = [kw for kw in keywords if len(kw) >= 2]
    if keywords:
        matched_keywords = sum(1 for kw in keywords if _find_in_source(kw, source_text))
        if matched_keywords >= len(keywords) * 0.5:
            return ConceptProvenance(
                name=concept_name,
                label=ProvenanceLabel.INFERRED,
            )

    # 无任何匹配
    return ConceptProvenance(
        name=concept_name,
        label=ProvenanceLabel.AMBIGUOUS,
    )


def compute_provenance(
    compile_result: dict[str, Any],
    source_text: str,
) -> ProvenanceResult:
    """计算编译产物的完整溯源标签

    综合分析摘要、概念、编译模式等信号，为编译结果分配溯源标签。

    Args:
        compile_result: 编译结果字典，包含 one_line, key_points, detailed_summary, concepts
        source_text: 原始源文本（用于交叉验证）

    Returns:
        ProvenanceResult 溯源结果
    """
    signals: list[str] = []

    # 1. 编译模式判定
    mode = _determine_compilation_mode(source_text)
    signals.append(f"编译模式: {mode}")

    # 2. 摘要溯源
    one_line = str(compile_result.get("one_line", "") or "")
    detailed_summary = str(compile_result.get("detailed_summary", "") or "")
    key_points = compile_result.get("key_points", [])
    if not isinstance(key_points, list):
        key_points = []

    # one_line 溯源
    one_line_match = _find_in_source(one_line[:30], source_text) if one_line else None
    # key_points 溯源
    kp_match_count = _count_key_phrases_in_source(key_points, source_text)
    kp_total = len([k for k in key_points if isinstance(k, str) and k.strip()])
    kp_match_ratio = kp_match_count / kp_total if kp_total > 0 else 0.0

    # 模板/自引用检测
    template_signals = _detect_template_or_selfref(detailed_summary)
    signals.extend(template_signals)

    # 综合摘要溯源标签
    if template_signals:
        summary_label = ProvenanceLabel.AMBIGUOUS
        signals.append("摘要标签: ambiguous (模板/自引用)")
    elif (one_line_match or kp_match_ratio >= 0.6) and mode == "direct":
        summary_label = ProvenanceLabel.EXTRACTED
        signals.append(f"摘要标签: extracted (kp匹配率={kp_match_ratio:.0%})")
    elif mode == "map_reduce" or mode == "hierarchical":
        summary_label = ProvenanceLabel.MERGED
        signals.append(f"摘要标签: merged (编译模式={mode})")
    elif kp_match_ratio >= 0.3:
        summary_label = ProvenanceLabel.INFERRED
        signals.append(f"摘要标签: inferred (kp匹配率={kp_match_ratio:.0%})")
    else:
        summary_label = ProvenanceLabel.INFERRED
        signals.append("摘要标签: inferred (低匹配率)")

    # 3. 概念溯源
    raw_concepts = compile_result.get("concepts", [])
    if not isinstance(raw_concepts, list):
        raw_concepts = []

    concept_results: list[ConceptProvenance] = []
    for concept in raw_concepts:
        if isinstance(concept, dict):
            name = str(concept.get("name", "") or "").strip()
            explanation = str(concept.get("explanation", "") or "").strip()
        elif isinstance(concept, str) and concept.strip():
            name = concept.strip()
            explanation = ""
        else:
            continue

        if not name:
            continue

        cp = _classify_concept(name, explanation, source_text)
        concept_results.append(cp)

    # 4. 综合总体标签
    concept_labels = [cp.label for cp in concept_results]
    has_template = len(template_signals) > 0

    # 无概念时降级
    if not concept_labels:
        overall = ProvenanceLabel.AMBIGUOUS
        signals.append("总体标签: ambiguous (无有效概念)")
    elif has_template:
        overall = ProvenanceLabel.AMBIGUOUS
        signals.append("总体标签: ambiguous (模板检测)")
    else:
        # 统计各标签数量
        extracted_count = concept_labels.count(ProvenanceLabel.EXTRACTED)
        inferred_count = concept_labels.count(ProvenanceLabel.INFERRED)
        ambiguous_count = concept_labels.count(ProvenanceLabel.AMBIGUOUS)
        total_concepts = len(concept_labels)

        extracted_ratio = extracted_count / total_concepts
        ambiguous_ratio = ambiguous_count / total_concepts

        if (
            extracted_ratio >= 0.6
            and mode == "direct"
            or extracted_ratio >= 0.6
            and summary_label == ProvenanceLabel.EXTRACTED
        ):
            overall = ProvenanceLabel.EXTRACTED
        elif ambiguous_ratio >= 0.5:
            overall = ProvenanceLabel.AMBIGUOUS
        elif mode in ("map_reduce", "hierarchical") and extracted_ratio >= 0.3:
            overall = ProvenanceLabel.MERGED
        elif inferred_count > extracted_count:
            overall = ProvenanceLabel.INFERRED
        else:
            overall = ProvenanceLabel.MERGED

        signals.append(
            f"总体标签: {overall} "
            f"(extracted={extracted_count}, inferred={inferred_count}, "
            f"ambiguous={ambiguous_count}/{total_concepts})"
        )

    confidence = PROVENANCE_CONFIDENCE[overall]

    return ProvenanceResult(
        overall_label=overall,
        confidence=confidence,
        summary_label=summary_label,
        concepts=concept_results,
        signals=signals,
    )


def provenance_to_dict(result: ProvenanceResult) -> dict[str, Any]:
    """将溯源结果转为可序列化字典（用于写入 manifest）

    Args:
        result: 溯源结果

    Returns:
        可 JSON 序列化的字典
    """
    return {
        "overall_label": result.overall_label,
        "confidence": result.confidence,
        "summary_label": result.summary_label,
        "concepts": [
            {
                "name": c.name,
                "label": c.label,
                "source_match": c.source_match,
            }
            for c in result.concepts
        ],
        "signals": result.signals,
    }
