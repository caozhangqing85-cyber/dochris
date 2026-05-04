"""共享常量、数据获取与辅助函数"""

from __future__ import annotations

import logging
import platform
import shutil
import tempfile
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd  # type: ignore[import-untyped]

from dochris import __version__
from dochris.manifest import get_all_manifests
from dochris.settings import get_settings

logger = logging.getLogger(__name__)

# ── 常量 ──────────────────────────────────────────────────────

_QUERY_MODE_LABELS: dict[str, str] = {
    "combined": "综合查询（推荐）",
    "concept": "概念搜索",
    "summary": "摘要搜索",
    "vector": "向量检索",
    "all": "全量搜索",
}
_STATUS_FILTERS = ["全部", "compiled", "ingested", "failed", "promoted_to_wiki", "promoted"]

_STATUS_LABELS: dict[str, str] = {
    "compiled": "✅ 已编译",
    "ingested": "📥 已摄入",
    "failed": "❌ 失败",
    "promoted_to_wiki": "🌟 已推广(Wiki)",
    "promoted": "🔒 已推广(Curated)",
    "unknown": "❓ 未知",
}

_STATUS_FILTER_LABELS = ["全部"] + [_STATUS_LABELS.get(s, s) for s in _STATUS_FILTERS[1:]]
_STATUS_LABEL_REVERSE = {v: k for k, v in _STATUS_LABELS.items()}

# 空数据占位 DataFrame
_EMPTY_TYPE_DF = pd.DataFrame({"类型": ["暂无数据"], "数量": [0]})
_EMPTY_STATUS_DF = pd.DataFrame({"状态": ["暂无数据"], "数量": [0]})
_EMPTY_QUALITY_DF = pd.DataFrame({"分数段": ["暂无数据"], "文件数": [0]})


# ============================================================
# 数据获取辅助函数
# ============================================================


def _get_manifest_data() -> tuple[list[dict], Counter[str], Counter[str]]:
    """获取 manifest 列表及统计"""
    settings = get_settings()
    manifests = get_all_manifests(settings.workspace)
    status_counter: Counter[str] = Counter(m.get("status", "unknown") for m in manifests)
    type_counter: Counter[str] = Counter(m.get("type", "unknown") for m in manifests)
    return manifests, status_counter, type_counter


def _do_query(query_str: str, top_k: int, mode: str = "combined") -> dict[str, Any]:
    """执行查询"""
    from dochris.phases.phase3_query import query

    return query(query_str, mode=mode, top_k=top_k)


def _format_query_results(result: dict[str, Any]) -> str:
    """格式化查询结果为 Markdown"""
    lines: list[str] = []
    elapsed = result.get("time_seconds", 0)
    mode = result.get("mode", "combined")
    lines.append(f"**查询耗时:** {elapsed:.2f}s | **模式:** {_QUERY_MODE_LABELS.get(mode, mode)}\n")

    answer = result.get("answer")
    if answer:
        lines.append("## AI 回答\n")
        lines.append(f"{answer}\n")

    vector_results = result.get("vector_results", [])
    if vector_results:
        lines.append("## 向量搜索结果\n")
        for i, r in enumerate(vector_results, 1):
            score = r.get("score", 0)
            title = r.get("title", "无标题")
            content = r.get("content", "")
            source = r.get("source", "")
            src_id = r.get("manifest_id", "")
            lines.append(f"### {i}. {title} (相似度: {score:.3f})")
            if source:
                lines.append(f"**来源:** `{source}`\n")
            if src_id:
                lines.append(f"**Manifest:** `{src_id}`\n")
            if content:
                display = content[:500] + "..." if len(content) > 500 else content
                lines.append(f"> {display}\n")

    concepts = result.get("concepts", [])
    if concepts:
        lines.append("## 概念匹配\n")
        for i, c in enumerate(concepts, 1):
            name = c.get("name", c.get("title", ""))
            lines.append(f"{i}. **{name}**")

    summaries = result.get("summaries", [])
    if summaries:
        lines.append("## 摘要匹配\n")
        for i, s in enumerate(summaries, 1):
            title = s.get("title", "无标题")
            source = s.get("source", "")
            lines.append(f"{i}. **{title}**")
            if source:
                lines.append(f"   - 来源: `{source}`")

    if not vector_results and not concepts and not summaries and not answer:
        lines.append("*未找到相关结果*")

    return "\n".join(lines)


def _get_file_table(search: str = "", status_filter: str = "全部") -> list[list[str]]:
    """获取文件列表（用于 Dataframe 展示），支持搜索和过滤"""
    internal_filter = _STATUS_LABEL_REVERSE.get(status_filter, status_filter)
    manifests, _, _ = _get_manifest_data()
    rows: list[list[str]] = []
    search_lower = search.lower().strip()

    for m in manifests:
        name = m.get("original_filename", m.get("source_file", "unknown"))
        file_type = m.get("type", "unknown")
        status = m.get("status", "unknown")
        quality = str(m.get("quality_score", "-"))
        manifest_id = m.get("id", "")

        if internal_filter != "全部" and status != internal_filter:
            continue
        if (
            search_lower
            and search_lower not in name.lower()
            and search_lower not in manifest_id.lower()
            and search_lower not in file_type.lower()
        ):
            continue

        rows.append([manifest_id, name, file_type, status, quality])
        if len(rows) >= 200:
            break
    return rows


def _sanitize_path(p: Path) -> str:
    """脱敏路径，只显示最后两级目录"""
    parts = p.parts
    if len(parts) >= 2:
        return str(Path(*parts[-2:]))
    return p.name


def _get_system_status() -> str:
    """获取系统状态文本"""
    settings = get_settings()
    manifests, status_counter, type_counter = _get_manifest_data()

    lines = [
        "## 系统信息",
        f"- **版本:** {__version__}",
        f"- **Python:** {platform.python_version()}",
        f"- **平台:** {platform.platform()}",
        f"- **工作区:** `{_sanitize_path(settings.workspace)}`",
        f"- **LLM 模型:** {settings.model}",
        f"- **查询模型:** {settings.query_model}",
        f"- **API Base:** `{settings.api_base}`",
        f"- **API Key:** {'已配置' if settings.api_key else '未配置'}",
    ]

    try:
        disk = shutil.disk_usage(str(settings.workspace))
        total_gb = disk.total / (1024**3)
        used_gb = disk.used / (1024**3)
        free_gb = disk.free / (1024**3)
        pct = disk.used / disk.total * 100
        lines.append(
            f"- **磁盘:** {used_gb:.1f}/{total_gb:.1f}GB ({pct:.0f}%) — 剩余 {free_gb:.1f}GB"
        )
    except (OSError, ValueError):
        pass

    lines.extend(
        [
            "",
            "## 文件统计",
            f"- **总计:** {len(manifests)}",
            f"- **已摄入:** {status_counter.get('ingested', 0)}",
            f"- **已编译:** {status_counter.get('compiled', 0)}",
            f"- **已推广 (wiki):** {status_counter.get('promoted_to_wiki', 0)}",
            f"- **已推广 (curated):** {status_counter.get('promoted', 0)}",
            f"- **失败:** {status_counter.get('failed', 0)}",
        ]
    )

    wiki_dir = settings.workspace / "wiki"
    concepts_count = 0
    summaries_count = 0
    try:
        concepts_dir = wiki_dir / "concepts"
        if concepts_dir.exists():
            concepts_count = sum(1 for p in concepts_dir.iterdir() if p.is_file())
        summaries_dir = wiki_dir / "summaries"
        if summaries_dir.exists():
            summaries_count = sum(1 for p in summaries_dir.iterdir() if p.is_file())
    except OSError:
        pass
    lines.extend(
        [
            "",
            "## 知识库统计",
            f"- **概念数:** {concepts_count}",
            f"- **摘要数:** {summaries_count}",
        ]
    )

    lines.extend(
        [
            "",
            "## 文件类型分布",
        ]
    )
    for ft, count in type_counter.most_common():
        lines.append(f"- **{ft}:** {count}")

    data_dir = settings.data_dir
    chroma_path = data_dir / "chroma.sqlite3"
    if chroma_path.exists():
        size_mb = chroma_path.stat().st_size / (1024 * 1024)
        lines.extend(
            [
                "",
                "## 向量数据库",
                f"- **路径:** `{_sanitize_path(data_dir)}`",
                f"- **大小:** {size_mb:.1f} MB",
            ]
        )
    else:
        lines.extend(["", "## 向量数据库", "- **状态:** 未初始化"])

    lines.extend(["", "## 关键依赖"])
    for pkg in [
        "gradio",
        "chromadb",
        "pandas",
        "openai",
        "sentence_transformers",
        "markitdown",
        "json_repair",
        "rich",
    ]:
        try:
            mod = __import__(pkg)
            ver = getattr(mod, "__version__", "未知")
            display_name = pkg.replace("_", "-")
            lines.append(f"- **{display_name}:** {ver}")
        except ImportError:
            display_name = pkg.replace("_", "-")
            lines.append(f"- **{display_name}:** 未安装")

    return "\n".join(lines)


def _get_compile_info() -> str:
    """获取编译预览信息"""
    manifests, status_counter, _ = _get_manifest_data()
    pending = status_counter.get("ingested", 0)
    compiled = status_counter.get("compiled", 0)
    failed = status_counter.get("failed", 0)
    return (
        f"**待编译:** {pending} | **已编译:** {compiled} | **失败:** {failed}"
        f" | **总计:** {len(manifests)}"
    )


def handle_upload(files: list[Any]) -> str:
    """处理文件上传"""
    if not files:
        return "*未选择文件*"
    settings = get_settings()
    raw_dir = settings.raw_dir
    raw_dir.mkdir(parents=True, exist_ok=True)
    count = 0
    for f in files:
        try:
            src = Path(f.name)
            dst = raw_dir / src.name
            if not dst.exists():
                shutil.copy2(src, dst)
                count += 1
        except Exception as e:
            logger.warning(f"上传文件 {f.name} 失败: {e}")
    return f"已上传 {count}/{len(files)} 个文件到 raw/ 目录"


def _export_markdown(content: str, prefix: str = "export") -> str | None:
    """将 Markdown 内容导出到临时文件"""
    if not content or content.startswith("*"):
        return None
    try:
        tmp = tempfile.NamedTemporaryFile(
            mode="w", suffix=".md", prefix=prefix, delete=False, encoding="utf-8"
        )
        tmp.write(
            f"# 知识库查询结果\n\n导出时间:"
            f" {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n---\n\n{content}"
        )
        tmp.close()
        return tmp.name
    except Exception as e:
        logger.warning(f"导出失败: {e}")
        return None
