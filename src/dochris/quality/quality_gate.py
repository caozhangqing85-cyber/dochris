#!/usr/bin/env python3
"""
质量门禁与污染检测系统（四层信任模型）

信任层级：
  Layer 0: outputs/     — LLM 生成，不可信
  Layer 1: wiki/        — 经 promote 审核进入，半可信
  Layer 2: curated/     — 人工精选，可信
  Layer 3: locked/      — 锁定保护，不可修改

功能：
  1. check_pollution  — 检测 wiki/ 中是否有 outputs/ 的直接写入
  2. quality_gate     — 质量门禁（分数 < 85 拒绝 promote）
  3. auto_downgrade   — 自动降级机制
  4. scan_wiki        — 扫描 wiki/ 中的孤儿文件

用法:
  python scripts/quality_gate.py <workspace> check-pollution
  python scripts/quality_gate.py <workspace> quality-gate <src-id>
  python scripts/quality_gate.py <workspace> auto-downgrade <src-id> [--reason <reason>]
  python scripts/quality_gate.py <workspace> scan-wiki
  python scripts/quality_gate.py <workspace> report
"""

import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

# 确保 scripts 包可导入
from dochris.log import append_log
from dochris.manifest import (
    get_all_manifests,
    get_manifest,
    update_manifest_status,
)
from dochris.settings import get_settings

# ============================================================
# 常量
# ============================================================

TRUST_LAYERS = {
    "outputs": 0,
    "wiki": 1,
    "curated": 2,
    "locked": 3,
}


def _get_min_quality_score() -> int:
    """动态读取 promote 最低质量分数（避免模块级固化，支持测试重置 settings）。"""
    return get_settings().min_quality_score


# ============================================================
# 污染检测
# ============================================================


def check_pollution(workspace_path: Path) -> dict:
    """检测 wiki/ 中是否有 outputs/ 的直接写入（未经 promote）

    检测逻辑：
    1. 遍历 wiki/summaries/ 和 wiki/concepts/ 中的所有文件
    2. 对比 manifests/ 中 status != "promoted_to_wiki" 且 status != "promoted" 的来源
    3. 如果 wiki/ 中的文件无法匹配到已 promote 的 manifest，视为污染

    Returns:
        {
            "polluted": bool,
            "polluted_files": [Path, ...],
            "orphan_count": int,
            "details": str,
        }
    """
    workspace_path = Path(workspace_path)
    wiki_summaries = workspace_path / "wiki" / "summaries"
    wiki_concepts = workspace_path / "wiki" / "concepts"

    # 收集所有已 promote 的文件名（通过 manifest）
    manifests = get_all_manifests(workspace_path)
    # 同时记录每个 title 对应的合法文件名模式（支持任意位数的 _N 重名后缀）
    promoted_title_patterns: list[re.Pattern[str]] = []
    promoted_concept_names: set[str] = set()

    for m in manifests:
        if m["status"] in ("promoted_to_wiki", "promoted"):
            title = m.get("title", "")
            safe_title = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "", title)[:80]
            # 匹配 {title}.md 或 {title}_N.md（N 为任意数字，覆盖 promote 的重名冲突）
            escaped = re.escape(safe_title)
            promoted_title_patterns.append(re.compile(rf"^{escaped}(_\d+)?\.md$"))

            compiled_summary = m.get("compiled_summary")
            if compiled_summary and isinstance(compiled_summary, dict):
                concepts = compiled_summary.get("concepts", [])
                if isinstance(concepts, list):
                    for c in concepts:
                        name = c.get("name", "") if isinstance(c, dict) else c
                        if name:
                            safe_c = re.sub(r'[<>:"/\\|?*]', "", str(name)).strip()[:50]
                            promoted_concept_names.add(f"{safe_c}.md")

    def _is_promoted_summary(filename: str) -> bool:
        return any(p.match(filename) for p in promoted_title_patterns)

    # 扫描 wiki/ 中的文件
    polluted_files = []
    orphan_summaries = []
    orphan_concepts = []

    if wiki_summaries.exists():
        for f in wiki_summaries.glob("*.md"):
            if not _is_promoted_summary(f.name):
                polluted_files.append(f)
                orphan_summaries.append(f)

    if wiki_concepts.exists():
        for f in wiki_concepts.glob("*.md"):
            if f.name not in promoted_concept_names:
                polluted_files.append(f)
                orphan_concepts.append(f)

    is_polluted = len(polluted_files) > 0

    result = {
        "polluted": is_polluted,
        "polluted_count": len(polluted_files),
        "orphan_summaries": len(orphan_summaries),
        "orphan_concepts": len(orphan_concepts),
        "polluted_files": [str(f.relative_to(workspace_path)) for f in polluted_files[:20]],
        "details": (
            f"发现 {len(polluted_files)} 个污染文件 "
            f"(摘要: {len(orphan_summaries)}, 概念: {len(orphan_concepts)})"
            if is_polluted
            else "wiki/ 干净，无污染"
        ),
    }

    # 记录日志
    append_log(
        workspace_path,
        "POLLUTION_CHECK",
        str(result["details"]),
    )

    return result


# ============================================================
# 质量门禁
# ============================================================


def quality_gate(
    workspace_path: Path,
    src_id: str,
    min_score: int | None = None,
) -> dict[str, Any]:
    """质量门禁检查

    质量分数作为信号展示，不作为硬门禁。真正的门禁条件：
    1. status 必须是 "compiled"
    2. error_message 必须为空
    3. summary 必须存在
    4. lint 必须通过（无 error 级别问题）

    质量分数 < min_score 时标记为 warning，但不阻止晋升。

    Returns:
        {
            "passed": bool,
            "src_id": str,
            "reason": str,
            "quality_score": int,
            "quality_level": "high" | "medium" | "low",
            "checks": { "status": bool, "error": bool, "summary": bool, "lint": bool },
        }
    """
    # 延迟读取 settings，支持运行时/测试重置（min_score 默认 None 表示动态读）
    if min_score is None:
        min_score = _get_min_quality_score()
    workspace_path = Path(workspace_path)
    manifest = get_manifest(workspace_path, src_id)

    if manifest is None:
        return {
            "passed": False,
            "src_id": src_id,
            "reason": f"未找到 manifest: {src_id}",
            "checks": {},
        }

    # Phase A: Lint 检查（从 compiled_summary 中读取）
    compiled_summary = manifest.get("compiled_summary", {}) or {}
    lint_data = compiled_summary.get("lint")
    lint_passed = True
    lint_errors: list[str] = []
    concept_quality_warnings = 0
    if lint_data and isinstance(lint_data, dict):
        lint_passed = lint_data.get("passed", True)
        for issue in lint_data.get("issues", []):
            severity = issue.get("severity", "")
            if severity == "error":
                lint_errors.append(issue.get("message", ""))
            if issue.get("rule") == "concept_quality" and severity == "warning":
                concept_quality_warnings += 1
    # 概念质量问题阻止晋升
    if concept_quality_warnings > 0:
        lint_passed = False
        lint_errors.append(f"存在 {concept_quality_warnings} 个概念使用了默认解释")

    # Provenance 检查（信息性，不阻止晋升）
    provenance_data = compiled_summary.get("provenance")
    provenance_label = None
    if provenance_data and isinstance(provenance_data, dict):
        provenance_label = provenance_data.get("overall_label")

    # 质量分数 → 信号灯级别（信息性，不阻止晋升）
    quality_score = manifest.get("quality_score", 0)
    if quality_score >= 80:
        quality_level = "high"
    elif quality_score >= 50:
        quality_level = "medium"
    else:
        quality_level = "low"
    score_warning = quality_score < min_score

    # 真正的门禁条件（不含分数）
    checks = {
        "status": manifest["status"] == "compiled",
        "error": manifest.get("error_message") is None,
        "summary": manifest.get("summary") is not None,
        "lint": lint_passed,
    }

    all_passed = all(checks.values())

    reasons = []
    if not checks["status"]:
        reasons.append(f"状态为 '{manifest['status']}'，需要 'compiled'")
    if not checks["error"]:
        reasons.append(f"存在错误: {manifest.get('error_message', 'unknown')}")
    if not checks["summary"]:
        reasons.append("缺少 summary 数据")
    if not checks["lint"]:
        reasons.append(f"Lint 未通过: {'; '.join(lint_errors[:3])}")

    result = {
        "passed": all_passed,
        "src_id": src_id,
        "title": manifest.get("title", ""),
        "quality_score": quality_score,
        "quality_level": quality_level,
        "score_warning": score_warning,
        "provenance": provenance_label,
        "reason": "通过" if all_passed else "; ".join(reasons),
        "checks": checks,
    }

    # 记录日志
    append_log(
        workspace_path,
        "QUALITY_GATE",
        f"{src_id} | {'PASS' if all_passed else 'REJECT'} | {result['reason']}",
    )

    return result


# ============================================================
# 自动降级
# ============================================================


def auto_downgrade(
    workspace_path: Path,
    src_id: str,
    reason: str = "auto_downgrade",
) -> dict[str, Any]:
    """自动降级 manifest

    将 manifest 降级到 outputs/ 层级：
    - 如果 status 是 "promoted"，降为 "promoted_to_wiki"
    - 如果 status 是 "promoted_to_wiki"，降为 "compiled"
    - 如果 status 是 "compiled"，降为 "ingested"

    同时从 wiki/ 和 curated/ 中移除对应文件。

    Args:
        workspace_path: 工作区路径
        src_id: 来源 ID
        reason: 降级原因

    Returns:
        操作结果 dict
    """
    workspace_path = Path(workspace_path)
    manifest = get_manifest(workspace_path, src_id)

    if manifest is None:
        return {"success": False, "reason": f"未找到 manifest: {src_id}"}

    current_status = manifest["status"]
    title = manifest.get("title", "")
    removed_files = []

    # 降级状态映射
    downgrade_map = {
        "promoted": "promoted_to_wiki",
        "promoted_to_wiki": "compiled",
        "compiled": "ingested",
    }

    if current_status not in downgrade_map:
        return {
            "success": False,
            "reason": f"无法从 '{current_status}' 降级",
            "current_status": current_status,
        }

    new_status = downgrade_map[current_status]

    # 移除 wiki/ 中的文件（从 promoted_to_wiki 降级时）
    if current_status in ("promoted", "promoted_to_wiki"):
        safe_title = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "", title)[:80]

        for target_dir in ["wiki/summaries", "wiki/concepts", "curated/promoted"]:
            target_path = workspace_path / target_dir
            if not target_path.exists():
                continue
            # 精确匹配 {title}.md 和重名变体 {title}_N.md，
            # 避免前缀匹配误删（如 "AI" 误删 "AI 应用.md"）
            for f in target_path.glob("*.md"):
                stem = f.stem
                if stem == safe_title or re.match(rf"^{re.escape(safe_title)}_\d+$", stem):
                    f.unlink()
                    removed_files.append(str(f.relative_to(workspace_path)))

    # 更新 manifest
    update_manifest_status(
        workspace_path,
        src_id,
        status=new_status,
        error_message=f"downgraded: {reason}",
        # 空字符串哨兵表示显式清空 promoted_to（降级回 compiled 时）
        promoted_to="" if new_status == "compiled" else manifest.get("promoted_to"),
    )

    # 记录日志
    append_log(
        workspace_path,
        "AUTO_DOWNGRADE",
        f"{src_id} | {current_status} → {new_status} | 原因: {reason} | 移除文件: {len(removed_files)}",
    )

    return {
        "success": True,
        "src_id": src_id,
        "from_status": current_status,
        "to_status": new_status,
        "reason": reason,
        "removed_files": removed_files,
    }


# ============================================================
# 批量质量扫描
# ============================================================


def scan_wiki(workspace_path: Path) -> dict:
    """扫描 wiki/ 中的所有文件，检查信任层级一致性

    Returns:
        扫描报告 dict
    """
    workspace_path = Path(workspace_path)

    # 污染检测
    pollution = check_pollution(workspace_path)

    # 统计 wiki/ 文件
    wiki_summaries = workspace_path / "wiki" / "summaries"
    wiki_concepts = workspace_path / "wiki" / "concepts"

    summary_count = len(list(wiki_summaries.glob("*.md"))) if wiki_summaries.exists() else 0
    concept_count = len(list(wiki_concepts.glob("*.md"))) if wiki_concepts.exists() else 0

    # 统计 manifest 状态
    manifests = get_all_manifests(workspace_path)
    status_counts: dict[str, int] = {}
    for m in manifests:
        s = m["status"]
        status_counts[s] = status_counts.get(s, 0) + 1

    report = {
        "wiki_summaries": summary_count,
        "wiki_concepts": concept_count,
        "wiki_total": summary_count + concept_count,
        "pollution": pollution,
        "manifest_status_counts": status_counts,
        "manifest_total": len(manifests),
        "scan_time": datetime.now().isoformat(),
    }

    return report


# ============================================================
# 报告生成
# ============================================================


def generate_report(workspace_path: Path) -> dict:
    """生成完整的信任模型报告

    Returns:
        报告 dict
    """
    workspace_path = Path(workspace_path)
    pollution = check_pollution(workspace_path)
    wiki_scan = scan_wiki(workspace_path)

    manifests = get_all_manifests(workspace_path)

    # 质量分数分布
    score_distribution = {"0-40": 0, "41-60": 0, "61-84": 0, "85-100": 0}
    for m in manifests:
        score = m.get("quality_score", 0)
        if score < 41:
            score_distribution["0-40"] += 1
        elif score < 61:
            score_distribution["41-60"] += 1
        elif score < 85:
            score_distribution["61-84"] += 1
        else:
            score_distribution["85-100"] += 1

    # 满足 promote 条件的 manifest
    min_score = _get_min_quality_score()
    promotable = [
        m
        for m in manifests
        if m["status"] == "compiled" and m.get("quality_score", 0) >= min_score
    ]

    report = {
        "trust_model": "四层信任模型",
        "layers": {
            "Layer 0 (outputs/)": "LLM 生成，不可信",
            "Layer 1 (wiki/)": "经 promote 审核，半可信",
            "Layer 2 (curated/)": "人工精选，可信",
            "Layer 3 (locked/)": "锁定保护，不可修改",
        },
        "pollution": pollution["polluted"],
        "pollution_details": pollution["details"],
        "wiki_files": wiki_scan["wiki_total"],
        "manifest_total": wiki_scan["manifest_total"],
        "manifest_statuses": wiki_scan["manifest_status_counts"],
        "score_distribution": score_distribution,
        "promotable_count": len(promotable),
        "min_quality_score": min_score,
        "scan_time": datetime.now().isoformat(),
    }

    return report


# ============================================================
# CLI
# ============================================================


def main() -> None:
    if len(sys.argv) < 3:
        print(__doc__)
        print("用法:")
        print(f"  python {sys.argv[0]} <workspace> check-pollution")
        print(f"  python {sys.argv[0]} <workspace> quality-gate <src-id>")
        print(f"  python {sys.argv[0]} <workspace> auto-downgrade <src-id> [--reason <reason>]")
        print(f"  python {sys.argv[0]} <workspace> scan-wiki")
        print(f"  python {sys.argv[0]} <workspace> report")
        sys.exit(1)

    workspace = Path(sys.argv[1])
    command = sys.argv[2].lower()

    if command == "check-pollution":
        result = check_pollution(workspace)
        print(f"污染检测: {'发现污染!' if result['polluted'] else '干净'}")
        print(f"  {result['details']}")
        if result["polluted_files"]:
            print("\n  污染文件（前 20 个）:")
            for f in result["polluted_files"]:
                print(f"    {f}")
        sys.exit(1 if result["polluted"] else 0)

    elif command == "quality-gate":
        if len(sys.argv) < 4:
            print("用法: quality-gate <src-id>")
            sys.exit(1)
        src_id = sys.argv[3]
        result = quality_gate(workspace, src_id)
        status = "PASS" if result["passed"] else "REJECT"
        print(f"[{status}] {src_id} | {result.get('title', '')[:50]}")
        print(f"  质量分数: {result.get('quality_score', 0)}/100")
        print(f"  结果: {result['reason']}")
        sys.exit(0 if result["passed"] else 1)

    elif command == "auto-downgrade":
        if len(sys.argv) < 4:
            print("用法: auto-downgrade <src-id> [--reason <reason>]")
            sys.exit(1)
        src_id = sys.argv[3]
        reason = "manual"
        if "--reason" in sys.argv:
            idx = sys.argv.index("--reason")
            if idx + 1 < len(sys.argv):
                reason = sys.argv[idx + 1]
        result = auto_downgrade(workspace, src_id, reason)
        if result["success"]:
            print(f"降级成功: {src_id} {result['from_status']} → {result['to_status']}")
            if result["removed_files"]:
                print(f"  移除文件: {len(result['removed_files'])} 个")
                for f in result["removed_files"][:5]:
                    print(f"    {f}")
        else:
            print(f"降级失败: {result['reason']}")
        sys.exit(0 if result["success"] else 1)

    elif command == "scan-wiki":
        result = scan_wiki(workspace)
        print("wiki/ 扫描结果:")
        print(f"  摘要文件: {result['wiki_summaries']}")
        print(f"  概念文件: {result['wiki_concepts']}")
        print(f"  总计: {result['wiki_total']}")
        print(f"\n污染检测: {'发现!' if result['pollution']['polluted'] else '干净'}")
        print(f"  {result['pollution']['details']}")
        print("\nManifest 状态分布:")
        for status, count in sorted(result["manifest_status_counts"].items()):
            print(f"  {status}: {count}")

    elif command == "report":
        report = generate_report(workspace)
        print(json.dumps(report, ensure_ascii=False, indent=2))

    else:
        print(f"未知命令: {command}")
        print("支持: check-pollution / quality-gate / auto-downgrade / scan-wiki / report")
        sys.exit(1)


if __name__ == "__main__":
    main()
