"""
Phase 3 查询工具函数：日志、manifest 索引、关键词搜索、内容提取
"""

import json
import logging
import re

# 导入统一配置
import sys
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any

import openai

sys.path.insert(0, str(Path(__file__).parent))
from dochris.settings import (
    LOG_DATE_FORMAT,
    LOG_FORMAT_SIMPLE,
    QUERY_MODEL,
    get_data_dir,
    get_default_workspace,
    get_logs_dir,
    get_manifests_dir,
    get_outputs_dir,
    get_wiki_concepts_dir,
    get_wiki_dir,
    get_wiki_summaries_dir,
)

# 路径配置（从 config 导入）
KB_PATH = get_default_workspace()
WIKI_PATH = get_wiki_dir()
WIKI_SUMMARIES_PATH = get_wiki_summaries_dir()
WIKI_CONCEPTS_PATH = get_wiki_concepts_dir()
OUTPUTS_PATH = get_outputs_dir()
OUTPUTS_SUMMARIES_PATH = OUTPUTS_PATH / "summaries"
OUTPUTS_CONCEPTS_PATH = OUTPUTS_PATH / "concepts"
DATA_PATH = get_data_dir()
LOGS_PATH = get_logs_dir()
MANIFESTS_PATH = get_manifests_dir()

# LLM 配置
MODEL = QUERY_MODEL

# 全局缓存
_llm_client_cache: openai.OpenAI | None = None
_chromadb_client_cache: object | None = None
_manifest_index_cache: dict[str, str] | None = None  # file_path → src_id 映射


def setup_logging() -> logging.Logger:
    """设置日志系统

    Returns:
        配置好的 logger 实例
    """
    LOGS_PATH.mkdir(parents=True, exist_ok=True)
    log_file = LOGS_PATH / f"phase3_{datetime.now().strftime(LOG_DATE_FORMAT)}.log"
    logger = logging.getLogger("phase3")
    logger.setLevel(logging.DEBUG)
    fh = logging.FileHandler(log_file, encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    fmt = logging.Formatter(LOG_FORMAT_SIMPLE)
    fh.setFormatter(fmt)
    ch.setFormatter(fmt)
    logger.addHandler(fh)
    logger.addHandler(ch)
    return logger


# ============================================================
# Manifest 来源追踪
# ============================================================


def _build_manifest_index() -> dict[str, str]:
    """构建文件路径 → manifest ID 的索引缓存

    扫描所有 manifest，建立：
    - file_path → src_id
    - title（去特殊字符） → src_id

    Returns:
        文件路径到 manifest ID 的映射字典
    """
    index: dict[str, str] = {}
    if not MANIFESTS_PATH.exists():
        return index
    for f in MANIFESTS_PATH.glob("SRC-*.json"):
        try:
            with open(f, encoding="utf-8") as fh:
                m = json.load(fh)
            src_id = m["id"]
            # 按 file_path 索引
            fp = m.get("file_path", "")
            if fp:
                index[fp] = src_id
            # 按 title 索引（去特殊字符，用于匹配摘要文件名）
            title = m.get("title", "")
            if title:
                safe_title = re.sub(r'[<>:"/\\|?*]', "", title).strip()[:80]
                index[f"wiki/summaries/{safe_title}.md"] = src_id
                index[f"outputs/summaries/{safe_title}.md"] = src_id
        except (json.JSONDecodeError, OSError, KeyError, UnicodeDecodeError):
            continue
    return index


def _get_manifest_id(file_path: str) -> str | None:
    """通过文件路径查找 manifest ID"""
    global _manifest_index_cache
    if _manifest_index_cache is None:
        _manifest_index_cache = _build_manifest_index()

    # 直接匹配
    if file_path in _manifest_index_cache:
        return _manifest_index_cache[file_path]

    # 尝试用文件名部分匹配
    fname = Path(file_path).name
    for key, src_id in _manifest_index_cache.items():
        if Path(key).name == fname:
            return src_id

    return None


def _get_manifest_status(src_id: str) -> str | None:
    """获取 manifest 状态

    Args:
        src_id: Manifest ID（如 "SRC-0001"）

    Returns:
        状态字符串，如果未找到则返回 None
    """
    if not src_id:
        return None
    manifest_file = MANIFESTS_PATH / f"{src_id}.json"
    if not manifest_file.exists():
        return None
    try:
        with open(manifest_file, encoding="utf-8") as f:
            m = json.load(f)
        return m.get("status")
    except (json.JSONDecodeError, OSError, UnicodeDecodeError):
        return None


# ============================================================
# 关键词搜索（通用）
# ============================================================


def _keyword_search(
    query: str,
    search_dir: Path,
    top_k: int,
    extract_fn: Callable[[Path, str], dict],
    source_label: str,
) -> list[dict[str, Any]]:
    """通用关键词搜索

    Args:
        query: 搜索关键词
        search_dir: 搜索目录
        top_k: 最大返回数
        extract_fn: 提取函数，接收 (file_path, text) 返回 dict
        source_label: 来源标签（"wiki" / "outputs"）
    """
    if not search_dir.exists():
        return []

    results = []
    query_lower = query.lower()
    query_terms = set(re.findall(r"[\w]+", query_lower))

    for md_file in search_dir.glob("*.md"):
        try:
            text = md_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        text_lower = text.lower()

        score = 0
        stem = md_file.stem.lower()

        # 文件名精确匹配
        if stem in query_lower:
            score += 10

        # 术语匹配
        for term in query_terms:
            if term in stem:
                score += 5
            count = text_lower.count(term)
            score += min(count, 3)

        if score > 0:
            item = extract_fn(md_file, text)
            item["score"] = score
            item["source"] = source_label
            item["file"] = str(md_file)
            item["manifest_id"] = _get_manifest_id(str(md_file))
            results.append(item)

    results.sort(key=lambda x: x["score"], reverse=True)
    return results[:top_k]


def _extract_concept(file_path: Path, text: str) -> dict:
    """从概念文件提取定义"""
    definition = ""
    for line in text.split("\n"):
        if line.startswith("## 定义"):
            continue
        if line.startswith("## "):
            break
        if line.strip() and not line.startswith("#"):
            definition += line + "\n"

    return {
        "name": file_path.stem,
        "definition": definition.strip(),
    }


def _extract_summary(file_path: Path, text: str) -> dict:
    """从摘要文件提取一句话摘要和要点"""
    one_line = ""
    key_points = []
    section = ""

    for line in text.split("\n"):
        if line.startswith("## 一句话摘要"):
            section = "one_line"
            continue
        elif line.startswith("## 要点"):
            section = "key_points"
            continue
        elif line.startswith("## "):
            section = ""

        if section == "one_line" and line.strip():
            one_line = line.strip()
        elif section == "key_points" and line.strip().startswith("- "):
            key_points.append(line.strip()[2:])

    return {
        "title": file_path.stem,
        "one_line": one_line,
        "key_points": key_points[:3],
    }
