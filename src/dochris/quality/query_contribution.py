#!/usr/bin/env python3
"""
Query-as-Contribution：查询结果回写知识库

Karpathy 理论核心：每次查询的结果应作为新知识写回知识库，使知识库随使用增值。
安全机制：查询结果先写入 candidates/（Layer 0），经质量评分 ≥ 85 后才可晋升到 wiki/。

数据流：
  用户查询 → LLM 回答 → 写入 candidates/ → 质量评分 → promote 到 wiki/
                                                 ↘ 评分不足 → 标记 needs_review

新增目录：
  outputs/candidates/       — 查询衍生知识暂存区
  outputs/candidates/meta/  — 候选知识元数据（溯源、关联 manifest）

用法：
  from dochris.quality.query_contribution import (
      contribute_query_result,
      list_candidates,
      promote_candidate,
      discard_candidate,
  )
"""

import hashlib
import json
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from dochris.log import append_log
from dochris.quality.quality_gate import _get_min_quality_score

logger = logging.getLogger(__name__)

# 候选知识来源类型
SOURCE_TYPE_QUERY = "query_derived"
SOURCE_TYPE_COMPILE = "compile_derived"
SOURCE_TYPE_MANUAL = "manual"


def _candidates_dir(workspace_path: Path) -> Path:
    """获取候选知识目录"""
    d = workspace_path / "outputs" / "candidates"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _candidates_meta_dir(workspace_path: Path) -> Path:
    """获取候选知识元数据目录"""
    d = workspace_path / "outputs" / "candidates" / "meta"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _content_hash(text: str) -> str:
    """计算内容哈希"""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def _safe_filename(title: str) -> str:
    """将标题转为安全文件名"""
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "", title).strip()
    name = name.replace(" ", "-")
    name = re.sub(r"-{2,}", "-", name)
    return name[:80] or "untitled"


def _extract_concepts_from_answer(answer: str) -> list[str]:
    """从回答中提取 [[概念名]] 格式的概念引用"""
    return list(set(re.findall(r"\[\[([^\]]+)\]\]", answer)))


def _check_contradiction(
    answer: str, workspace_path: Path, threshold: float = 0.7
) -> dict[str, Any]:
    """与现有知识交叉验证，检测潜在矛盾

    通过关键词搜索 wiki/ 中的现有内容，检查是否存在语义冲突。

    Args:
        answer: 查询回答文本
        workspace_path: 工作区路径
        threshold: 矛盾判定阈值（0-1）

    Returns:
        {"has_contradiction": bool, "conflicting_sources": list, "details": str}
    """
    wiki_concepts = workspace_path / "wiki" / "concepts"

    # 提取回答中的关键陈述（简单策略：按句子拆分）
    _sentences = [s.strip() for s in re.split(r"[。！？\n]", answer) if len(s.strip()) > 10]

    conflicting = []
    # 检查回答中引用的概念是否在 wiki 中有不同定义
    concepts_in_answer = _extract_concepts_from_answer(answer)
    for concept_name in concepts_in_answer:
        concept_file = wiki_concepts / f"{_safe_filename(concept_name)}.md"
        if concept_file.exists():
            existing = concept_file.read_text(encoding="utf-8", errors="ignore")
            # 简单关键词重叠检测（更高级可用向量相似度）
            answer_words = set(re.findall(r"[一-鿿]{2,}", answer))
            existing_words = set(re.findall(r"[一-鿿]{2,}", existing))
            overlap = len(answer_words & existing_words) / max(
                len(answer_words | existing_words), 1
            )
            if overlap > threshold:
                conflicting.append(
                    {
                        "concept": concept_name,
                        "file": str(concept_file),
                        "overlap": round(overlap, 3),
                    }
                )

    return {
        "has_contradiction": len(conflicting) > 0,
        "conflicting_sources": conflicting,
        "details": f"发现 {len(conflicting)} 个潜在冲突概念" if conflicting else "无冲突",
    }


def contribute_query_result(
    workspace_path: Path,
    query: str,
    answer: str,
    source_manifest_ids: list[str] | None = None,
    concepts: list[dict] | None = None,
    mode: str = "combined",
    quality_score: int | None = None,
) -> dict[str, Any]:
    """将查询结果作为候选知识写回知识库

    流程：
    1. 内容去重（与已有候选比较）
    2. 矛盾检测（与 wiki/ 现有内容交叉验证）
    3. 质量评分（如果未提供）
    4. 写入 candidates/ 目录
    5. 创建元数据文件

    Args:
        workspace_path: 工作区路径
        query: 原始查询
        answer: LLM 生成的回答
        source_manifest_ids: 引用的 manifest ID 列表
        concepts: 提取的概念列表 [{"name": str, "explanation": str}]
        mode: 查询模式
        quality_score: 预计算的质量分数（None 则自动评分）

    Returns:
        候选知识元数据 dict
    """
    workspace_path = Path(workspace_path)
    candidates_dir = _candidates_dir(workspace_path)
    meta_dir = _candidates_meta_dir(workspace_path)

    content_hash = _content_hash(query + answer)

    # 1. 去重：检查是否已有相同内容的候选
    for meta_file in meta_dir.glob("*.json"):
        try:
            existing = json.loads(meta_file.read_text(encoding="utf-8"))
            if existing.get("content_hash") == content_hash:
                logger.info(f"候选知识已存在: {meta_file.stem}")
                return {**existing, "status": "duplicate"}
        except (json.JSONDecodeError, OSError):
            continue

    # 2. 矛盾检测
    contradiction = _check_contradiction(answer, workspace_path)

    # 3. 质量评分（简单启发式）
    if quality_score is None:
        quality_score = _score_candidate(query, answer, concepts)

    # 4. 生成候选 ID
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    candidate_id = f"QRY-{timestamp}-{content_hash[:6]}"

    # 5. 提取概念引用
    referenced_concepts = _extract_concepts_from_answer(answer)

    # 6. 构建候选知识内容（Markdown）
    title = f"查询衍生: {query[:30]}{'...' if len(query) > 30 else ''}"
    md_content = _build_candidate_markdown(
        title=title,
        query=query,
        answer=answer,
        concepts=concepts or [],
        referenced_concepts=referenced_concepts,
        source_manifest_ids=source_manifest_ids or [],
        mode=mode,
    )

    # 7. 写入候选文件
    safe_title = _safe_filename(title)
    candidate_file = candidates_dir / f"{safe_title}.md"
    if candidate_file.exists():
        candidate_file = candidates_dir / f"{safe_title}_{content_hash[:4]}.md"
    candidate_file.write_text(md_content, encoding="utf-8")

    # 8. 写入元数据
    meta = {
        "id": candidate_id,
        "title": title,
        "source_type": SOURCE_TYPE_QUERY,
        "query": query,
        "query_mode": mode,
        "content_hash": content_hash,
        "quality_score": quality_score,
        "status": "candidate",
        "needs_review": quality_score < _get_min_quality_score() or contradiction["has_contradiction"],
        "contradiction": contradiction,
        "source_manifest_ids": source_manifest_ids or [],
        "concepts_extracted": concepts or [],
        "concepts_referenced": referenced_concepts,
        "created_at": datetime.now().isoformat(),
        "file": str(candidate_file.relative_to(workspace_path)),
    }
    meta_file = meta_dir / f"{candidate_id}.json"
    meta_file.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    # 9. 记录日志
    append_log(
        workspace_path,
        "QUERY_CONTRIBUTION",
        f"{candidate_id} | score={quality_score} | needs_review={meta['needs_review']} | "
        f"concepts={len(referenced_concepts)} | contradiction={contradiction['has_contradiction']}",
    )

    logger.info(
        f"查询结果已写入候选区: {candidate_id} (score={quality_score}, "
        f"needs_review={meta['needs_review']})"
    )

    return meta


def _score_candidate(query: str, answer: str, concepts: list[dict] | None = None) -> int:
    """对候选知识进行启发式质量评分

    评分维度：
    - 完整性（回答长度和结构）
    - 信息密度（关键术语覆盖）
    - 概念引用（[[概念名]] 数量）
    - 结构性（分段、列表等）

    Returns:
        0-100 质量分数
    """
    from dochris.settings.constants import INFO_KEYWORDS, LEARNING_KEYWORDS

    score = 50  # 基础分

    # 完整性（回答长度）
    answer_len = len(answer)
    if answer_len >= 200:
        score += 10
    if answer_len >= 500:
        score += 5
    if answer_len >= 1000:
        score += 5

    # 信息密度
    answer_text = answer.lower()
    learning_hits = sum(1 for kw in LEARNING_KEYWORDS if kw in answer_text)
    info_hits = sum(1 for kw in INFO_KEYWORDS if kw.lower() in answer_text)
    score += min(learning_hits * 2, 10)
    score += min(info_hits * 2, 5)

    # 概念引用
    concept_refs = len(re.findall(r"\[\[[^\]]+\]\]", answer))
    score += min(concept_refs * 3, 10)

    # 结构性
    has_structure = bool(re.search(r"(\n[-*•]|\n\d+\.|\n#{1,3} )", answer))
    if has_structure:
        score += 5

    # 提供了概念
    if concepts and len(concepts) > 0:
        score += 5

    return min(score, 100)


def _build_candidate_markdown(
    title: str,
    query: str,
    answer: str,
    concepts: list[dict],
    referenced_concepts: list[str],
    source_manifest_ids: list[str],
    mode: str,
) -> str:
    """构建候选知识的 Markdown 内容"""
    parts = [
        f"# {title}\n",
        f"> **来源**: 查询衍生 (mode: {mode})",
        f"> **查询**: {query}",
        f"> **生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "",
        "---\n",
        "## AI 回答\n",
        answer,
        "",
    ]

    if concepts:
        parts.append("## 提取的概念\n")
        for c in concepts:
            name = c.get("name", "")
            explanation = c.get("explanation", c.get("description", ""))
            parts.append(f"- **{name}**: {explanation}")
        parts.append("")

    if referenced_concepts:
        parts.append("## 关联概念\n")
        parts.append(" ".join(f"[[{c}]]" for c in referenced_concepts))
        parts.append("")

    if source_manifest_ids:
        parts.append("## 来源文件\n")
        for mid in source_manifest_ids:
            parts.append(f"- 📚 来源: {mid}")
        parts.append("")

    parts.append("---")
    parts.append("*此内容由查询衍生生成，需经质量审核后晋升到 wiki 层。*")

    return "\n".join(parts)


def list_candidates(
    workspace_path: Path,
    status: str | None = None,
    needs_review_only: bool = False,
) -> list[dict]:
    """列出所有候选知识

    Args:
        workspace_path: 工作区路径
        status: 过滤状态 ("candidate" | "promoted" | "discarded")
        needs_review_only: 只显示需要审核的

    Returns:
        候选知识元数据列表
    """
    workspace_path = Path(workspace_path)
    meta_dir = _candidates_meta_dir(workspace_path)

    candidates = []
    for meta_file in sorted(meta_dir.glob("QRY-*.json")):
        try:
            meta = json.loads(meta_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue

        if status and meta.get("status") != status:
            continue
        if needs_review_only and not meta.get("needs_review"):
            continue
        candidates.append(meta)

    return candidates


def promote_candidate(
    workspace_path: Path,
    candidate_id: str,
    target: str = "wiki",
) -> dict[str, Any]:
    """将候选知识晋升到 wiki 层

    前置条件：
    1. 候选状态为 "candidate"
    2. 质量分数 ≥ MIN_QUALITY_SCORE（85）
    3. 无未解决的矛盾（或已人工确认）

    Args:
        workspace_path: 工作区路径
        candidate_id: 候选 ID (QRY-XXXXXXXX-XXXXXXXX)
        target: 晋升目标 ("wiki")

    Returns:
        晋升结果 dict
    """
    workspace_path = Path(workspace_path)
    meta_dir = _candidates_meta_dir(workspace_path)
    meta_file = meta_dir / f"{candidate_id}.json"

    if not meta_file.exists():
        return {"success": False, "reason": f"候选不存在: {candidate_id}"}

    meta = json.loads(meta_file.read_text(encoding="utf-8"))

    if meta["status"] != "candidate":
        return {"success": False, "reason": f"状态不是 candidate: {meta['status']}"}

    # 质量门禁
    min_score = _get_min_quality_score()
    if meta["quality_score"] < min_score:
        return {
            "success": False,
            "reason": f"质量分数 {meta['quality_score']} < {min_score}，需要人工审核",
        }

    # 读取候选内容
    candidate_file = workspace_path / meta["file"]
    if not candidate_file.exists():
        return {"success": False, "reason": "候选文件不存在"}

    content = candidate_file.read_text(encoding="utf-8")

    # 写入 wiki
    if target == "wiki":
        wiki_dir = workspace_path / "wiki" / "summaries"
        wiki_dir.mkdir(parents=True, exist_ok=True)

        safe_title = _safe_filename(meta["title"])
        wiki_file = wiki_dir / f"{safe_title}.md"
        if wiki_file.exists():
            wiki_file = wiki_dir / f"{safe_title}_{meta['content_hash'][:4]}.md"

        wiki_file.write_text(content, encoding="utf-8")

        # 更新元数据
        meta["status"] = "promoted"
        meta["promoted_to"] = str(wiki_file.relative_to(workspace_path))
        meta["promoted_at"] = datetime.now().isoformat()
        meta_file.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

        # 为提取的概念创建概念文件
        concepts_dir = workspace_path / "wiki" / "concepts"
        concepts_dir.mkdir(parents=True, exist_ok=True)
        for concept in meta.get("concepts_extracted", []):
            name = concept.get("name", "")
            explanation = concept.get("explanation", concept.get("description", ""))
            if not name:
                continue
            concept_file = concepts_dir / f"{_safe_filename(name)}.md"
            if not concept_file.exists():
                concept_file.write_text(
                    f"# {name}\n\n{explanation}\n\n> 来源: 查询衍生 ({candidate_id})\n",
                    encoding="utf-8",
                )

        # 记录日志
        append_log(
            workspace_path,
            "CANDIDATE_PROMOTED",
            f"{candidate_id} → wiki | score={meta['quality_score']}",
        )

        return {
            "success": True,
            "candidate_id": candidate_id,
            "promoted_to": str(wiki_file.relative_to(workspace_path)),
            "quality_score": meta["quality_score"],
        }

    return {"success": False, "reason": f"不支持的目标: {target}"}


def discard_candidate(
    workspace_path: Path,
    candidate_id: str,
    reason: str = "manual_discard",
) -> dict[str, Any]:
    """丢弃候选知识

    Args:
        workspace_path: 工作区路径
        candidate_id: 候选 ID
        reason: 丢弃原因

    Returns:
        操作结果 dict
    """
    workspace_path = Path(workspace_path)
    meta_dir = _candidates_meta_dir(workspace_path)
    meta_file = meta_dir / f"{candidate_id}.json"

    if not meta_file.exists():
        return {"success": False, "reason": f"候选不存在: {candidate_id}"}

    meta = json.loads(meta_file.read_text(encoding="utf-8"))

    # 删除候选文件
    candidate_file = workspace_path / meta["file"]
    if candidate_file.exists():
        candidate_file.unlink()

    # 更新元数据状态
    meta["status"] = "discarded"
    meta["discarded_at"] = datetime.now().isoformat()
    meta["discard_reason"] = reason
    meta_file.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    append_log(workspace_path, "CANDIDATE_DISCARDED", f"{candidate_id} | reason={reason}")

    return {"success": True, "candidate_id": candidate_id}


def auto_contribute_from_query(
    workspace_path: Path,
    query_result: dict[str, Any],
    auto_promote: bool = False,
) -> dict[str, Any] | None:
    """从查询结果自动提取并贡献候选知识

    在 phase3_query.query() 返回结果后调用此函数。
    仅当回答质量较高时才写入候选区。

    Args:
        workspace_path: 工作区路径
        query_result: query() 返回的完整结果 dict
        auto_promote: 是否自动晋升（分数 ≥ 90 时自动晋升）

    Returns:
        候选知识元数据，如果质量不足则返回 None
    """
    answer = query_result.get("answer")
    if not answer or len(answer) < 100:
        return None

    query_str = query_result.get("query", "")
    concepts = query_result.get("concepts", [])
    mode = query_result.get("mode", "combined")

    # 提取引用的 manifest IDs
    source_ids = []
    for c in concepts:
        mid = c.get("manifest_id")
        if mid and mid not in source_ids:
            source_ids.append(mid)
    for s in query_result.get("summaries", []):
        mid = s.get("manifest_id")
        if mid and mid not in source_ids:
            source_ids.append(mid)

    # 贡献到候选区
    result = contribute_query_result(
        workspace_path=workspace_path,
        query=query_str,
        answer=answer,
        source_manifest_ids=source_ids,
        concepts=concepts,
        mode=mode,
    )

    # 自动晋升（高分 + 无矛盾）
    if (
        auto_promote
        and result.get("status") != "duplicate"
        and result.get("quality_score", 0) >= 90
        and not result.get("needs_review", True)
    ):
        promote_result = promote_candidate(
            workspace_path=workspace_path,
            candidate_id=result["id"],
            target="wiki",
        )
        result["auto_promoted"] = promote_result.get("success", False)

    return result
