#!/usr/bin/env python3
"""
Phase 3: 查询系统（v3 — async-first + wiki 优先 + manifest 来源追踪）

搜索优先级：
1. wiki/concepts/ + wiki/summaries/  （已晋升，高信任）
2. outputs/concepts/ + outputs/summaries/  （编译产物，中信任）
3. ChromaDB 向量检索  （历史索引）

架构特点：
- query_async() 为异步主入口，FastAPI 直接 await
- query() 为同步入口，CLI 通过 asyncio.run() 调用
- LLM 调用通过 BaseLLMProvider（OpenAICompatProvider），与编译链路统一
"""

import asyncio
import logging
import sys
import time
from pathlib import Path

# 确保 scripts 包可导入
from typing import Any, cast

# --- 路径常量（向后兼容） ---
from dochris.phases import query_utils

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
from dochris.phases import query_engine

# 向后兼容：直接暴露搜索和工具函数（不涉及 LLM）
search_concepts = query_engine.search_concepts
search_summaries = query_engine.search_summaries
read_openclaw_config = query_engine.read_openclaw_config
print_result = query_engine.print_result

# LLM 相关：指向新的 async 函数
create_query_provider = query_engine.create_query_provider
generate_answer_async = query_engine.generate_answer_async
generate_answer_stream_async = query_engine.generate_answer_stream_async

# 向后兼容别名：供尚未迁移的测试和调用方使用
create_client = query_engine.create_client


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


def vector_search(query: str, top_k: int = 5, logger: logging.Logger | None = None) -> list:
    """向量搜索包装器，直接委托给 query_engine"""
    return cast(list, query_engine.vector_search(query, top_k, logger))


# ============================================================
# 统一查询（双入口模式）
# ============================================================


async def query_async(
    query_str: str,
    mode: str = "combined",
    top_k: int = 5,
    logger: logging.Logger | None = None,
    contribute: bool = False,
    workspace_path: str | Path | None = None,
) -> dict[str, Any]:
    """异步查询主入口。FastAPI 应 await 此函数。

    搜索阶段（概念/摘要/向量）使用同步调用（本地文件 I/O），
    LLM 生成阶段使用异步 Provider（AsyncOpenAI）。

    Args:
        query_str: 查询字符串
        mode: 查询模式 (concept/summary/vector/combined/all)
        top_k: 返回结果数量
        logger: 日志记录器
        contribute: 启用 Query-as-Contribution
        workspace_path: contribute=True 时需要提供工作区路径

    Returns:
        查询结果字典
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

    # --- 搜索阶段（同步，本地文件 I/O） ---
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

    # --- LLM 生成阶段（异步） ---
    if mode in ("combined", "all") and (
        result["concepts"] or result["summaries"] or result["vector_results"]
    ):
        provider = create_query_provider(logger)
        if provider:
            result["answer"] = await generate_answer_async(
                query_str,
                result["concepts"],
                result["summaries"],
                result["vector_results"],
                provider,
                logger,
            )
        else:
            result["answer"] = "（LLM 不可用，以下为纯检索结果。请检查 API 认证配置。）"
            logger.warning("LLM provider creation failed, showing retrieval results only")

    result["time_seconds"] = round(time.time() - start, 2)

    # Query-as-Contribution：将高质量回答写回候选区
    if contribute and result.get("answer") and workspace_path:
        try:
            from dochris.quality.query_contribution import auto_contribute_from_query

            contribution = auto_contribute_from_query(
                workspace_path=Path(workspace_path),
                query_result=result,
            )
            if contribution:
                result["contribution"] = {
                    "id": contribution["id"],
                    "quality_score": contribution["quality_score"],
                    "needs_review": contribution.get("needs_review", True),
                    "auto_promoted": contribution.get("auto_promoted", False),
                }
        except Exception as e:
            logger.warning(f"Query-as-Contribution 失败: {e}")

    return result


def query(
    query_str: str,
    mode: str = "combined",
    top_k: int = 5,
    logger: logging.Logger | None = None,
    contribute: bool = False,
    workspace_path: str | Path | None = None,
) -> dict[str, Any]:
    """同步查询入口。CLI 使用此函数。

    内部通过 asyncio.run() 调用 query_async()，
    安全因为 CLI 不在事件循环中运行。
    """
    return asyncio.run(
        query_async(
            query_str,
            mode=mode,
            top_k=top_k,
            logger=logger,
            contribute=contribute,
            workspace_path=workspace_path,
        )
    )


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
