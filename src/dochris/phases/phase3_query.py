#!/usr/bin/env python3
"""
Phase 3: 查询系统（v2 — wiki 优先 + manifest 来源追踪）

搜索优先级：
1. wiki/concepts/ + wiki/summaries/  （已晋升，高信任）
2. outputs/concepts/ + outputs/summaries/  （编译产物，中信任）
3. ChromaDB 向量检索  （历史索引）

新增功能：
- search_all(): wiki 优先搜索，fallback 到 outputs/
- manifest_id 追踪：每个结果关联到对应的 SRC-NNNN manifest
- 来源可信度标注：wiki / outputs / vector
"""

import logging
import sys
import time

# 确保 scripts 包可导入
from pathlib import Path
from typing import Any, cast

sys.path.insert(0, str(Path(__file__).parent))


# --- 路径常量（向后兼容） ---
import query_utils

# --- 工具函数 ---
from dochris.phases.query_utils import (
    MANIFESTS_PATH,
    setup_logging,
)

# 向后兼容代理：缓存变量和函数通过本模块暴露
# 使测试的 @patch('phase3_query.xxx') 生效
_manifest_index_cache = query_utils._manifest_index_cache


def _build_manifest_index() -> dict[str, str]:
    """构建 manifest 索引（代理）"""
    # 将本模块的 MANIFESTS_PATH 临时同步到 query_utils
    # 以支持测试中的 @patch('phase3_query.MANIFESTS_PATH')
    original = query_utils.MANIFESTS_PATH
    query_utils.MANIFESTS_PATH = MANIFESTS_PATH
    try:
        # 直接使用本模块可能被 patch 的版本
        # 但这里实际实现总是调用 query_utils 版本
        return cast(dict[str, str], query_utils._build_manifest_index())
    finally:
        query_utils.MANIFESTS_PATH = original


def _get_manifest_id(file_path: str) -> str | None:
    """通过文件路径查找 manifest ID（代理）"""
    global _manifest_index_cache
    if _manifest_index_cache is None:
        _manifest_index_cache = _build_manifest_index()
        query_utils._manifest_index_cache = _manifest_index_cache
    # 直接匹配
    if file_path in _manifest_index_cache:
        return cast(str | None, _manifest_index_cache[file_path])
    # 文件名匹配
    from pathlib import Path as _Path

    fname = _Path(file_path).name
    for key, src_id in _manifest_index_cache.items():
        if _Path(key).name == fname:
            return cast(str | None, src_id)
    return None


# --- 搜索引擎（使用 module 引用，保证缓存共享） ---
import query_engine

# 向后兼容：直接暴露所有公开符号
search_concepts = query_engine.search_concepts
search_summaries = query_engine.search_summaries
generate_answer = query_engine.generate_answer
read_openclaw_config = query_engine.read_openclaw_config
create_client = query_engine.create_client
print_result = query_engine.print_result


def search_all(query: str, top_k: int = 5) -> dict:
    """搜索全部（wiki 优先）— 重写以使用本模块的 vector_search"""
    concepts = search_concepts(query, top_k)
    summaries = search_summaries(query, top_k)

    sources_used = set()
    if concepts:
        sources_used.add(concepts[0]["source"])
    if summaries:
        sources_used.add(summaries[0]["source"])

    vector_results = vector_search(query, top_k)
    if vector_results:
        sources_used.add("vector")

    return {
        "concepts": concepts,
        "summaries": summaries,
        "vector_results": vector_results,
        "search_sources": sorted(sources_used),
    }


# 向后兼容：缓存变量需要可直接通过 phase3_query 模块修改
# 使用 property 不可行，直接在 module 上做 proxy
_chromadb_client_cache = query_engine._chromadb_client_cache
_llm_client_cache = query_engine._llm_client_cache


def vector_search(query: str, top_k: int = 5, logger: logging.Logger | None = None) -> list:
    """向量搜索包装器，确保读写本模块的缓存"""
    global _chromadb_client_cache
    # 同步缓存到 query_engine
    query_engine._chromadb_client_cache = _chromadb_client_cache
    result = query_engine.vector_search(query, top_k, logger)
    # 同步缓存回来
    _chromadb_client_cache = query_engine._chromadb_client_cache
    return cast(list, result)


# ============================================================
# 统一查询
# ============================================================


def query(
    query_str: str, mode: str = "combined", top_k: int = 5, logger: logging.Logger | None = None
) -> dict[str, Any]:
    """
    执行查询

    mode:
      "concept"  — 概念搜索（wiki 优先）
      "summary"  — 摘要搜索（wiki 优先）
      "vector"   — 向量检索
      "combined" — 综合查询
      "all"      — 搜索全部，返回 search_sources 标注
    """
    if logger is None:
        logger = logging.getLogger("phase3")

    start = time.time()
    result: dict[str, Any] = {
        "query": query_str,
        "mode": mode,
        "concepts": [],
        "summaries": [],
        "vector_results": [],
        "search_sources": [],
        "answer": None,
        "time_seconds": 0,
    }

    if mode == "all":
        all_result = search_all(query_str, top_k)
        result["concepts"] = all_result["concepts"]
        result["summaries"] = all_result["summaries"]
        result["vector_results"] = all_result["vector_results"]
        result["search_sources"] = all_result["search_sources"]
    else:
        if mode in ("concept", "combined"):
            result["concepts"] = search_concepts(query_str, top_k)
            if result["concepts"]:
                result["search_sources"].append(result["concepts"][0]["source"])

        if mode in ("summary", "combined"):
            result["summaries"] = search_summaries(query_str, top_k)
            if result["summaries"]:
                result["search_sources"].append(result["summaries"][0]["source"])

        if mode in ("vector", "combined"):
            result["vector_results"] = vector_search(query_str, top_k, logger)
            if result["vector_results"]:
                result["search_sources"].append("vector")

    # 综合模式使用 LLM 生成回答
    if mode in ("combined", "all") and (
        result["concepts"] or result["summaries"] or result["vector_results"]
    ):
        # 同步 LLM 客户端缓存
        global _llm_client_cache
        query_engine._llm_client_cache = _llm_client_cache
        client = create_client(logger)
        _llm_client_cache = query_engine._llm_client_cache

        if client:
            result["answer"] = generate_answer(
                query_str,
                result["concepts"],
                result["summaries"],
                result["vector_results"],
                client,
                logger,
            )
        else:
            result["answer"] = "（LLM 不可用，以下为纯检索结果。请检查 API 认证配置。）"
            logger.warning("LLM client creation failed, showing retrieval results only")

    result["time_seconds"] = round(time.time() - start, 2)
    return result


def interactive_mode(logger: logging.Logger) -> None:
    """交互式查询模式"""
    print("知识库查询系统 (输入 'quit' 退出)")
    print("模式: concept / summary / vector / combined / all (默认 combined)")
    print("-" * 40)

    while True:
        try:
            user_input = input("\n> ").strip()
        except (EOFError, KeyboardInterrupt):
            break

        if not user_input or user_input.lower() in ("quit", "exit", "q"):
            break

        mode = "combined"
        parts = user_input.split(maxsplit=1)
        if len(parts) == 2 and parts[0] in ("concept", "summary", "vector", "combined", "all"):
            mode = parts[0]
            query_str = parts[1]
        else:
            query_str = user_input

        result = query(query_str, mode=mode, logger=logger)
        print_result(result)


if __name__ == "__main__":
    logger = setup_logging()

    if len(sys.argv) > 1:
        query_str = " ".join(sys.argv[1:])
        mode = "combined"
        result = query(query_str, mode=mode, logger=logger)
        print_result(result)
    else:
        interactive_mode(logger)
