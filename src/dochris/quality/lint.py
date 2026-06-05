#!/usr/bin/env python3
"""
Layer 1: 结构化 Lint 校验 (Structural Lint)

对编译产物进行结构完整性检查，类似于编译器的静态分析。
不评判内容"好不好"，而是检查结构"对不对"。

检查项：
  1. concept_dedup     — 概念去重（忽略大小写和空白差异）
  2. completeness      — 必需字段完整性（one_line, key_points, detailed_summary, concepts）
  3. self_reference    — 自引用检测（"本文档"、"该文件"等）
  4. coverage          — 大文件覆盖率检查（摘要是否覆盖源文本的足够段落）
  5. format_consistency — 格式一致性（Markdown 格式、概念 [[双链]] 格式）
  6. concept_quality   — 概念质量基础检查（过短、过长的概念名）

每项检查返回 LintIssue，按严重级别分类：
  - error:   必须修复（阻止晋升）
  - warning: 建议修复（不阻止晋升但记录）
  - info:    信息性提示
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class LintSeverity(StrEnum):
    """Lint 问题严重级别"""

    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


@dataclass
class LintIssue:
    """单个 Lint 检查结果"""

    rule: str
    """检查规则名称"""
    severity: LintSeverity
    message: str
    detail: str = ""
    """详细信息"""


@dataclass
class LintResult:
    """Lint 校验完整结果"""

    passed: bool
    """是否通过（无 error 级别问题）"""
    issues: list[LintIssue] = field(default_factory=list)
    error_count: int = 0
    warning_count: int = 0
    info_count: int = 0
    score: float = 1.0
    """结构完整度评分 (0.0-1.0)，基于 warning/error 扣分"""

    @property
    def has_errors(self) -> bool:
        return self.error_count > 0


def _safe_str(value: Any) -> str:
    if value is None:
        return ""
    return str(value) if value else ""


def _safe_list(value: Any) -> list:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return []


# ── 概念去重检查 ────────────────────────────────────────


def _check_concept_dedup(concepts: list[Any]) -> list[LintIssue]:
    """检查概念列表中的重复项（忽略大小写和空白差异）

    Args:
        concepts: 概念列表（支持 str 和 dict 格式）

    Returns:
        Lint 问题列表
    """
    issues: list[LintIssue] = []
    seen: dict[str, str] = {}  # normalized_name -> original_name

    for concept in concepts:
        if isinstance(concept, dict):
            name = str(concept.get("name", "") or "").strip()
        elif isinstance(concept, str):
            name = concept.strip()
        else:
            continue

        if not name:
            continue

        normalized = name.lower().replace(" ", "").replace("-", "")

        if normalized in seen:
            issues.append(
                LintIssue(
                    rule="concept_dedup",
                    severity=LintSeverity.WARNING,
                    message=f"重复概念: '{name}' 与 '{seen[normalized]}'",
                    detail=f"normalized: {normalized}",
                )
            )
        else:
            seen[normalized] = name

    return issues


# ── 完整性检查 ──────────────────────────────────────────


def _check_completeness(result: dict[str, Any]) -> list[LintIssue]:
    """检查编译结果的必需字段完整性

    必需字段：one_line, key_points, detailed_summary, concepts
    每个字段应有非空内容。

    Args:
        result: 编译结果字典

    Returns:
        Lint 问题列表
    """
    issues: list[LintIssue] = []

    # one_line
    one_line = _safe_str(result.get("one_line"))
    if not one_line:
        issues.append(
            LintIssue(
                rule="completeness",
                severity=LintSeverity.ERROR,
                message="缺少 one_line（单行摘要）",
            )
        )
    elif len(one_line) < 10:
        issues.append(
            LintIssue(
                rule="completeness",
                severity=LintSeverity.WARNING,
                message=f"one_line 过短 ({len(one_line)}字): '{one_line[:30]}'",
            )
        )

    # key_points
    key_points = _safe_list(result.get("key_points"))
    valid_kps = [k for k in key_points if isinstance(k, str) and k.strip()]
    if not valid_kps:
        issues.append(
            LintIssue(
                rule="completeness",
                severity=LintSeverity.ERROR,
                message="缺少 key_points（关键要点）",
            )
        )
    elif len(valid_kps) < 2:
        issues.append(
            LintIssue(
                rule="completeness",
                severity=LintSeverity.WARNING,
                message=f"key_points 过少 ({len(valid_kps)}个)",
            )
        )

    # detailed_summary
    detailed_summary = _safe_str(result.get("detailed_summary"))
    if not detailed_summary:
        issues.append(
            LintIssue(
                rule="completeness",
                severity=LintSeverity.ERROR,
                message="缺少 detailed_summary（详细摘要）",
            )
        )
    elif len(detailed_summary) < 50:
        issues.append(
            LintIssue(
                rule="completeness",
                severity=LintSeverity.WARNING,
                message=f"detailed_summary 过短 ({len(detailed_summary)}字)",
            )
        )

    # concepts
    concepts = _safe_list(result.get("concepts"))
    valid_concepts = []
    for c in concepts:
        if isinstance(c, dict):
            name = str(c.get("name", "") or "").strip()
        elif isinstance(c, str) and c.strip():
            name = c.strip()
        else:
            continue
        if name:
            valid_concepts.append(name)

    if not valid_concepts:
        issues.append(
            LintIssue(
                rule="completeness",
                severity=LintSeverity.WARNING,
                message="缺少有效 concepts（概念列表）",
            )
        )

    return issues


# ── 自引用检测 ──────────────────────────────────────────


_SELF_REF_PATTERNS = [
    re.compile(r"本文(?:档|件|章|节)"),
    re.compile(r"该(?:文档|文件|章节|文章)"),
    re.compile(r"这篇文章"),
    re.compile(r"(?:本|该|此)(?:书|资料|资料|材料)"),
]


def _check_self_reference(result: dict[str, Any]) -> list[LintIssue]:
    """检测摘要中的自引用模式

    编译产物不应包含对自身文档的引用措辞。

    Args:
        result: 编译结果字典

    Returns:
        Lint 问题列表
    """
    issues: list[LintIssue] = []
    text_to_check = _safe_str(result.get("detailed_summary"))
    if not text_to_check:
        return issues

    for pattern in _SELF_REF_PATTERNS:
        matches = pattern.findall(text_to_check)
        if matches:
            issues.append(
                LintIssue(
                    rule="self_reference",
                    severity=LintSeverity.WARNING,
                    message=f"自引用措辞: '{matches[0]}'",
                    detail=f"出现 {len(matches)} 次",
                )
            )
            break  # 只报告一次

    return issues


# ── 覆盖率检查 ──────────────────────────────────────────


def _check_coverage(result: dict[str, Any], source_text: str) -> list[LintIssue]:
    """检查摘要是否覆盖了源文本的足够段落

    仅对大文件（>10K 字符）进行检查。
    将源文本按段落（\n\n）分割，统计有多少段落在摘要中被提及。

    Args:
        result: 编译结果字典
        source_text: 原始源文本

    Returns:
        Lint 问题列表
    """
    issues: list[LintIssue] = []

    if len(source_text) < 10_000:
        return issues  # 小文件不检查覆盖率

    detailed_summary = _safe_str(result.get("detailed_summary"))
    if not detailed_summary:
        return issues

    # 将源文本按段落分割
    source_paragraphs = [
        p.strip() for p in source_text.split("\n\n") if p.strip() and len(p.strip()) > 50
    ]

    if not source_paragraphs:
        return issues

    # 检查每段中的关键词（取前 10 个非停用词字符）是否在摘要中出现
    covered = 0
    for para in source_paragraphs:
        # 从段落中提取关键短语
        key_segment = para[:30].strip()
        if len(key_segment) >= 4 and key_segment[:15] in detailed_summary:
            covered += 1

    coverage_ratio = covered / len(source_paragraphs) if source_paragraphs else 0

    if coverage_ratio < 0.2:
        issues.append(
            LintIssue(
                rule="coverage",
                severity=LintSeverity.WARNING,
                message=f"大文件覆盖率过低 ({coverage_ratio:.0%})",
                detail=f"源文本 {len(source_paragraphs)} 段落，摘要覆盖 {covered} 段",
            )
        )
    elif coverage_ratio < 0.4:
        issues.append(
            LintIssue(
                rule="coverage",
                severity=LintSeverity.INFO,
                message=f"大文件覆盖率一般 ({coverage_ratio:.0%})",
                detail=f"源文本 {len(source_paragraphs)} 段落，摘要覆盖 {covered} 段",
            )
        )

    return issues


# ── 概念质量基础检查 ────────────────────────────────────


def _check_concept_quality(concepts: list[Any]) -> list[LintIssue]:
    """检查概念列表的基础质量

    - 概念名过短（< 2 字符）
    - 概念名过长（> 50 字符）
    - 概念缺少解释（仅对 dict 格式检查）

    Args:
        concepts: 概念列表

    Returns:
        Lint 问题列表
    """
    issues: list[LintIssue] = []

    for concept in concepts:
        if isinstance(concept, dict):
            name = str(concept.get("name", "") or "").strip()
            explanation = str(concept.get("explanation", "") or "").strip()
        elif isinstance(concept, str):
            name = concept.strip()
            explanation = ""
        else:
            continue

        if not name:
            continue

        if len(name) < 2:
            issues.append(
                LintIssue(
                    rule="concept_quality",
                    severity=LintSeverity.WARNING,
                    message=f"概念名过短: '{name}'",
                )
            )
        elif len(name) > 50:
            issues.append(
                LintIssue(
                    rule="concept_quality",
                    severity=LintSeverity.WARNING,
                    message=f"概念名过长 ({len(name)}字): '{name[:30]}...'",
                )
            )

        # 检查解释是否为默认占位文本
        if explanation and "详细解释请参阅原文" in explanation:
            issues.append(
                LintIssue(
                    rule="concept_quality",
                    severity=LintSeverity.WARNING,
                    message=f"概念 '{name}' 使用了默认解释，缺少实际内容",
                    detail="LLM 未生成概念解释，使用了模板兜底文字。应重新编译或手动补充。",
                )
            )

    return issues


# ── 主入口 ──────────────────────────────────────────────


def lint_compile_result(
    compile_result: dict[str, Any],
    source_text: str = "",
) -> LintResult:
    """对编译结果执行完整的结构化 Lint 校验

    Args:
        compile_result: 编译结果字典
        source_text: 原始源文本（可选，用于覆盖率检查）

    Returns:
        LintResult 校验结果
    """
    if not isinstance(compile_result, dict):
        return LintResult(
            passed=False,
            issues=[
                LintIssue(
                    rule="completeness",
                    severity=LintSeverity.ERROR,
                    message="编译结果不是有效字典",
                )
            ],
            error_count=1,
        )

    all_issues: list[LintIssue] = []

    concepts = _safe_list(compile_result.get("concepts"))

    # 执行各项检查
    all_issues.extend(_check_concept_dedup(concepts))
    all_issues.extend(_check_completeness(compile_result))
    all_issues.extend(_check_self_reference(compile_result))
    if source_text:
        all_issues.extend(_check_coverage(compile_result, source_text))
    all_issues.extend(_check_concept_quality(concepts))

    # 统计
    error_count = sum(1 for i in all_issues if i.severity == LintSeverity.ERROR)
    warning_count = sum(1 for i in all_issues if i.severity == LintSeverity.WARNING)
    info_count = sum(1 for i in all_issues if i.severity == LintSeverity.INFO)

    # 计算结构完整度评分
    score = 1.0
    score -= error_count * 0.3
    score -= warning_count * 0.1
    score -= info_count * 0.02
    score = max(0.0, min(1.0, score))

    return LintResult(
        passed=error_count == 0,
        issues=all_issues,
        error_count=error_count,
        warning_count=warning_count,
        info_count=info_count,
        score=score,
    )


def lint_result_to_dict(result: LintResult) -> dict[str, Any]:
    """将 Lint 结果转为可序列化字典

    Args:
        result: Lint 校验结果

    Returns:
        可 JSON 序列化的字典
    """
    return {
        "passed": result.passed,
        "score": round(result.score, 2),
        "error_count": result.error_count,
        "warning_count": result.warning_count,
        "info_count": result.info_count,
        "issues": [
            {
                "rule": i.rule,
                "severity": i.severity,
                "message": i.message,
                "detail": i.detail,
            }
            for i in result.issues
        ],
    }
