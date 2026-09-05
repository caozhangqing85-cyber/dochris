"""晋升路由 — POST /api/v1/promote/{src_id}, POST /api/v1/promote/{src_id}/preview"""

from __future__ import annotations

import logging
import re
from pathlib import Path as FsPath
from typing import Any

from fastapi import APIRouter, HTTPException, Path

from dochris.api.preview import file_change, preview_envelope
from dochris.api.schemas import ErrorResponse, PromoteRequest, PromoteResponse
from dochris.manifest import get_manifest
from dochris.quality.quality_gate import quality_gate
from dochris.settings import get_settings

logger = logging.getLogger(__name__)
router = APIRouter(tags=["promote"])


def _promote_preview(
    workspace: str | FsPath,
    src_id: str,
    target_layer: str,
) -> dict[str, Any]:
    """计算晋升 preview：目标文件清单（create/overwrite/identical）与阻塞项。

    文件匹配逻辑与 dochris.promote 的实际晋升实现保持一致
    （直接复用其查找函数，避免两套规则漂移）。
    """
    from dochris.core.utils import sanitize_filename
    from dochris.promote import _find_concept_file, _find_output_file

    ws_path = FsPath(workspace)
    manifest = get_manifest(ws_path, src_id)
    if manifest is None:
        raise HTTPException(status_code=404, detail=f"未找到 manifest: {src_id}")

    blockers: list[str] = []
    changes: list[dict[str, Any]] = []

    status = manifest.get("status")
    required = "compiled" if target_layer == "wiki" else "promoted_to_wiki"
    if status != required:
        blockers.append(f"manifest 状态为 {status!r}，需要 {required!r}")

    title = str(manifest.get("title", ""))
    safe_title = sanitize_filename(title, max_length=80)
    pattern = re.sub(r'[<>:"/\\|?*]', "", title)[:80]

    if target_layer == "wiki":
        if blockers:
            gate = quality_gate(ws_path, src_id)
            if not gate.get("passed"):
                blockers.append(f"质量门禁未通过: {gate.get('reason')}")
            return preview_envelope(
                "promote",
                f"{src_id} → wiki（存在阻塞项，未执行）",
                [],
                blockers,
            )

        gate = quality_gate(ws_path, src_id)
        if not gate.get("passed"):
            return preview_envelope(
                "promote",
                f"{src_id} → wiki（质量门禁未通过，未执行）",
                [],
                [f"质量门禁未通过: {gate.get('reason')}"],
            )

        outputs_summaries = ws_path / "outputs" / "summaries"
        wiki_summaries = ws_path / "wiki" / "summaries"
        outputs_concepts = ws_path / "outputs" / "concepts"
        wiki_concepts = ws_path / "wiki" / "concepts"

        summary_src = _find_output_file(outputs_summaries, src_id, ".md")
        if summary_src is None:
            summary_src = outputs_summaries / f"{safe_title}.md"
        if summary_src is not None and not summary_src.exists():
            summary_src = outputs_summaries / f"{pattern}.md"
        if summary_src is None or not summary_src.exists():
            blockers.append(f"未找到摘要文件 outputs/summaries/{safe_title}.md")
        else:
            changes.append(file_change(wiki_summaries, summary_src, workspace=ws_path))

        compiled_summary = manifest.get("compiled_summary")
        concepts = (
            compiled_summary.get("concepts", []) if isinstance(compiled_summary, dict) else []
        )
        for concept in concepts if isinstance(concepts, list) else []:
            concept_name = (
                concept.get("name", "") if isinstance(concept, dict) else str(concept)
            ).strip()
            if not concept_name:
                continue
            concept_src = _find_concept_file(outputs_concepts, src_id, concept_name)
            if concept_src is not None and concept_src.exists():
                changes.append(file_change(wiki_concepts, concept_src, workspace=ws_path))

        return preview_envelope(
            "promote",
            f"{src_id} → wiki：{len(changes)} 个文件将被写入",
            changes,
            blockers,
        )

    # curated：wiki 中匹配 safe_title/pattern 摘要 + 安全化概念名
    if blockers:
        return preview_envelope(
            "promote",
            f"{src_id} → curated（存在阻塞项，未执行）",
            [],
            blockers,
        )

    curated_dir = ws_path / "curated" / "promoted"
    wiki_summaries = ws_path / "wiki" / "summaries"
    wiki_concepts = ws_path / "wiki" / "concepts"

    curated_summary_src: FsPath | None = None
    for candidate_name in (f"{safe_title}.md", f"{pattern}.md"):
        candidate = wiki_summaries / candidate_name
        if candidate.exists():
            curated_summary_src = candidate
            break
    if curated_summary_src is None:
        blockers.append(f"wiki/summaries 中未找到 {safe_title}.md")
    else:
        changes.append(file_change(curated_dir, curated_summary_src, workspace=ws_path))

    compiled_summary = manifest.get("compiled_summary")
    concepts = compiled_summary.get("concepts", []) if isinstance(compiled_summary, dict) else []
    for concept in concepts if isinstance(concepts, list) else []:
        concept_name = (
            concept.get("name", "") if isinstance(concept, dict) else str(concept)
        ).strip()
        if not concept_name:
            continue
        safe_concept = re.sub(r'[<>:"/\\|?*]', "", concept_name).strip()[:50]
        concept_src = wiki_concepts / f"{safe_concept}.md"
        if concept_src.exists():
            changes.append(file_change(curated_dir, concept_src, workspace=ws_path))

    return preview_envelope(
        "promote",
        f"{src_id} → curated：{len(changes)} 个文件将被写入",
        changes,
        blockers,
    )


@router.post(
    "/promote/{src_id}/preview",
    responses={
        404: {"model": ErrorResponse},
        400: {"model": ErrorResponse},
    },
)
async def preview_promote_artifact(
    src_id: str = Path(..., description="来源 ID，如 SRC-0001"),
    req: PromoteRequest | None = None,
    target: str | None = None,
) -> dict[str, Any]:
    """晋升预览（SEC-05）：返回将创建/覆盖的文件清单与阻塞项，不执行任何写入。"""
    target_layer = (req.target if req else target) or "wiki"
    if target_layer not in ("wiki", "curated"):
        raise HTTPException(status_code=400, detail=f"不支持的目标层级: {target_layer}")
    workspace = get_settings().workspace
    return _promote_preview(workspace, src_id, target_layer)


@router.post(
    "/promote/{src_id}",
    response_model=PromoteResponse,
    responses={
        404: {"model": ErrorResponse},
        400: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
    },
)
async def promote_artifact(
    src_id: str = Path(..., description="来源 ID，如 SRC-0001"),
    req: PromoteRequest | None = None,
    target: str | None = None,
) -> PromoteResponse:
    """将内容晋升到更高信任层级

    支持目标: wiki, curated
    """
    # 兼容 body 参数和 query 参数
    target_layer = (req.target if req else target) or "wiki"

    if target_layer not in ("wiki", "curated"):
        raise HTTPException(status_code=400, detail=f"不支持的目标层级: {target_layer}")

    settings = get_settings()
    workspace = settings.workspace

    manifest = get_manifest(workspace, src_id)
    if manifest is None:
        raise HTTPException(status_code=404, detail=f"未找到 manifest: {src_id}")

    try:
        if target_layer == "wiki":
            gate = quality_gate(workspace, src_id)
            if not gate["passed"]:
                return PromoteResponse(
                    src_id=src_id,
                    target=target_layer,
                    success=False,
                    message=f"质量门禁未通过: {gate['reason']}",
                )
            from dochris.promote import promote_to_wiki

            success = promote_to_wiki(workspace, src_id)
        else:
            from dochris.promote import promote_to_curated

            success = promote_to_curated(workspace, src_id)
    except Exception as exc:
        logger.exception("晋升失败")
        raise HTTPException(
            status_code=500, detail="晋升操作失败，请查看服务端日志获取详情"
        ) from exc

    if not success:
        return PromoteResponse(
            src_id=src_id,
            target=target_layer,
            success=False,
            message=f"晋升失败，请检查 {src_id} 的状态是否满足条件",
        )

    return PromoteResponse(
        src_id=src_id,
        target=target_layer,
        success=True,
        message=f"{src_id} 已晋升到 {target_layer}",
    )
