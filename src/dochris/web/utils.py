"""Web UI 共享工具函数和常量"""

from __future__ import annotations

import logging
from collections import Counter
from pathlib import Path

import pandas as pd  # type: ignore[import-untyped]

from dochris.manifest import get_all_manifests
from dochris.settings import get_settings

logger = logging.getLogger(__name__)

# ── 查询模式标签 ──────────────────────────────────────────────
QUERY_MODE_LABELS: dict[str, str] = {
    "combined": "综合查询（推荐）",
    "concept": "概念搜索",
    "summary": "摘要搜索",
    "vector": "向量检索",
    "all": "全量搜索",
}

# ── 状态常量 ──────────────────────────────────────────────────
STATUS_FILTERS = [
    "全部",
    "ingested",
    "compiled",
    "failed",
    "compile_failed",
    "promoted_to_wiki",
    "promoted",
]

STATUS_LABELS: dict[str, str] = {
    "ingested": "📥 待编译",
    "compiled": "✅ 已编译",
    "failed": "❌ 失败",
    "compile_failed": "❌ 编译失败",
    "promoted_to_wiki": "🌟 已推广(Wiki)",
    "promoted": "🔒 已推广(Curated)",
    "unknown": "❓ 未知",
}

STATUS_FILTER_LABELS = ["全部"] + [STATUS_LABELS.get(s, s) for s in STATUS_FILTERS[1:]]
STATUS_LABEL_REVERSE = {v: k for k, v in STATUS_LABELS.items()}

# ── 空 DataFrame 常量 ────────────────────────────────────────
EMPTY_TYPE_DF = pd.DataFrame({"类型": ["暂无数据"], "数量": [0]})
EMPTY_STATUS_DF = pd.DataFrame({"状态": ["暂无数据"], "数量": [0]})
EMPTY_QUALITY_DF = pd.DataFrame({"分数段": ["暂无数据"], "文件数": [0]})


def get_manifest_data() -> tuple[list[dict], Counter[str], Counter[str]]:
    """获取 manifest 列表及统计"""
    settings = get_settings()
    manifests = get_all_manifests(settings.workspace)
    status_counter: Counter[str] = Counter(m.get("status", "unknown") for m in manifests)
    type_counter: Counter[str] = Counter(m.get("type", "unknown") for m in manifests)
    return manifests, status_counter, type_counter


def sanitize_path(p: Path) -> str:
    """脱敏路径，只显示最后两级目录"""
    parts = p.parts
    if len(parts) >= 2:
        return str(Path(*parts[-2:]))
    return p.name
