"""
Phase 3 查询引擎：搜索接口、向量检索、LLM 回答生成、客户端管理
"""

import json
import logging
import os

import openai

from dochris.phases.query_utils import (
    DATA_PATH,
    OUTPUTS_CONCEPTS_PATH,
    OUTPUTS_SUMMARIES_PATH,
    WIKI_CONCEPTS_PATH,
    WIKI_SUMMARIES_PATH,
    _extract_concept,
    _extract_summary,
    _keyword_search,
)
from dochris.settings import OPENCLAW_CONFIG_PATH, get_settings

# 从 settings 获取默认模型
_settings = get_settings()
MODEL = _settings.query_model

# 全局缓存
_llm_client_cache: openai.OpenAI | None = None
_chromadb_client_cache: object | None = None
_vector_store_cache: object | None = None


# ============================================================
# 向量存储工厂（新增，支持抽象层）
# ============================================================


def get_vector_store() -> object:
    """获取向量存储实例（支持配置切换）

    根据 settings.vector_store 配置返回对应的向量存储实例：
    - "chromadb" (默认): ChromaDBStore
    - "faiss": FAISSStore

    Returns:
        向量存储实例（BaseVectorStore 子类）

    Examples:
        >>> store = get_vector_store()
        >>> results = store.query("my_collection", "search query", n_results=5)
    """
    global _vector_store_cache
    if _vector_store_cache is not None:
        return _vector_store_cache

    from dochris.settings import get_settings
    from dochris.vector import get_store as get_store_cls

    settings = get_settings()
    store_cls = get_store_cls(settings.vector_store)

    # 创建存储实例
    if settings.vector_store == "chromadb":
        # ChromaDB 使用 data_dir 作为持久化目录
        _vector_store_cache = store_cls(persist_directory=str(DATA_PATH))
    else:
        # 其他存储使用默认配置
        _vector_store_cache = store_cls()

    return _vector_store_cache


# ============================================================
# 搜索接口（保持向后兼容）
# ============================================================


def search_concepts(query: str, top_k: int = 5) -> list[dict]:
    """搜索概念 — wiki 优先，outputs fallback"""
    wiki_results = _keyword_search(
        query,
        WIKI_CONCEPTS_PATH,
        top_k,
        _extract_concept,
        "wiki",
    )
    if wiki_results:
        return wiki_results

    return _keyword_search(
        query,
        OUTPUTS_CONCEPTS_PATH,
        top_k,
        _extract_concept,
        "outputs",
    )


def search_summaries(query: str, top_k: int = 5) -> list[dict]:
    """搜索摘要 — wiki 优先，outputs fallback"""
    wiki_results = _keyword_search(
        query,
        WIKI_SUMMARIES_PATH,
        top_k,
        _extract_summary,
        "wiki",
    )
    if wiki_results:
        return wiki_results

    return _keyword_search(
        query,
        OUTPUTS_SUMMARIES_PATH,
        top_k,
        _extract_summary,
        "outputs",
    )


def search_all(query: str, top_k: int = 5) -> dict:
    """搜索全部（wiki 优先）

    Returns:
        {
            "concepts": [...],
            "summaries": [...],
            "vector_results": [...],
            "search_sources": ["wiki", "outputs", "vector"]
        }
    """
    concepts = search_concepts(query, top_k)
    summaries = search_summaries(query, top_k)

    # 确定搜索来源
    sources_used = set()
    if concepts:
        sources_used.add(concepts[0]["source"])
    if summaries:
        sources_used.add(summaries[0]["source"])

    # 向量检索始终执行（作为补充）
    vector_results = vector_search(query, top_k)
    if vector_results:
        sources_used.add("vector")

    return {
        "concepts": concepts,
        "summaries": summaries,
        "vector_results": vector_results,
        "search_sources": sorted(sources_used),
    }


# ============================================================
# 向量检索（保持不变）
# ============================================================


def vector_search(query: str, top_k: int = 5, logger: logging.Logger | None = None) -> list[dict]:
    """使用向量存储进行检索（支持配置切换）

    根据 settings.vector_store 配置选择后端：
    - "chromadb" (默认): 使用原有的 ChromaDB 逻辑
    - "faiss": 使用 FAISSStore 抽象层

    Args:
        query: 搜索查询字符串
        top_k: 返回结果数量
        logger: 日志记录器

    Returns:
        检索结果列表，每个结果包含 text、source、score 等字段
    """
    from dochris.settings import get_settings

    settings = get_settings()

    # 使用抽象层（非 chromadb 配置）
    if settings.vector_store != "chromadb":
        return _vector_search_with_store(query, top_k, logger)

    # chromadb 使用原有逻辑（保持向后兼容）
    global _chromadb_client_cache
    try:
        import chromadb

        if _chromadb_client_cache is None:
            _chromadb_client_cache = chromadb.PersistentClient(path=str(DATA_PATH))
        client = _chromadb_client_cache
        collections = client.list_collections()

        if not collections:
            if logger:
                logger.debug("No ChromaDB collections found")
            return []

        all_results: list[dict] = []
        for col in collections:
            try:
                results = col.query(
                    query_texts=[query],
                    n_results=min(top_k, col.count()),
                )
                if results and results["documents"]:
                    for i, doc in enumerate(results["documents"][0]):
                        metadata = results["metadatas"][0][i] if results["metadatas"] else {}
                        all_results.append(
                            {
                                "text": doc[:500],
                                "source": metadata.get("source", metadata.get("file", "unknown")),
                                "score": results["distances"][0][i] if results["distances"] else 0,
                                "type": "vector",
                                "manifest_id": None,
                            }
                        )
            except (AttributeError, KeyError, ValueError) as e:
                if logger:
                    logger.warning(f"ChromaDB query error: {e}")

        all_results.sort(key=lambda x: x["score"])
        return all_results[:top_k]

    except ImportError:
        if logger:
            logger.warning("chromadb not installed")
        return []
    except (OSError, RuntimeError) as e:
        if logger:
            logger.error(f"Vector search failed: {e}")
        return []


def _vector_search_with_store(
    query: str, top_k: int = 5, logger: logging.Logger | None = None
) -> list[dict]:
    """使用抽象层进行向量检索

    遍历所有 collection，合并结果后按距离排序。

    Args:
        query: 搜索查询字符串
        top_k: 返回结果数量
        logger: 日志记录器

    Returns:
        检索结果列表，每个结果包含 text、source、score 等字段
    """
    try:
        store = get_vector_store()
        collections = store.list_collections()

        if not collections:
            if logger:
                logger.debug("No vector store collections found")
            return []

        all_results: list[dict] = []
        for collection in collections:
            try:
                results = store.query(
                    collection=collection,
                    query_text=query,
                    n_results=top_k,
                )
                for r in results:
                    metadata = r.get("metadata", {})
                    all_results.append(
                        {
                            "text": r.get("document", "")[:500],
                            "source": metadata.get("source", metadata.get("file", "unknown")),
                            "score": r.get("distance", 0),
                            "type": "vector",
                            "manifest_id": metadata.get("manifest_id"),
                        }
                    )
            except Exception as e:
                if logger:
                    logger.warning(f"Vector store query error on {collection}: {e}")

        all_results.sort(key=lambda x: x["score"])
        return all_results[:top_k]

    except ImportError as e:
        if logger:
            logger.warning(f"Vector store dependency not installed: {e}")
        return []
    except (OSError, RuntimeError) as e:
        if logger:
            logger.error(f"Vector search failed: {e}")
        return []


# ============================================================
# LLM 回答生成（保持不变）
# ============================================================


def generate_answer(
    query: str,
    concepts: list[dict],
    summaries: list[dict],
    vector_results: list[dict],
    client: openai.OpenAI,
    logger: logging.Logger,
) -> str | None:
    """使用 LLM 综合生成回答

    Args:
        query: 用户问题
        concepts: 相关概念列表
        summaries: 相关摘要列表
        vector_results: 向量检索结果
        client: OpenAI 客户端
        logger: 日志记录器

    Returns:
        生成的回答文本，失败时返回 None
    """
    context_parts: list[str] = []

    if concepts:
        context_parts.append("### 相关概念\n")
        for c in concepts:
            context_parts.append(f"**{c['name']}**: {c['definition']}")

    if summaries:
        context_parts.append("\n### 相关资料\n")
        for s in summaries:
            context_parts.append(f"**{s['title']}**: {s['one_line']}")
            for kp in s["key_points"]:
                context_parts.append(f"  - {kp}")

    if vector_results:
        context_parts.append("\n### 向量检索结果\n")
        for v in vector_results:
            context_parts.append(f"[来源: {v['source']}]\n{v['text'][:300]}")

    if not context_parts:
        return "未找到相关内容。请尝试其他关键词。"

    context = "\n".join(context_parts)

    system = """你是一个知识库助手。根据提供的上下文信息回答用户的问题。
要求：
1. 只基于提供的上下文回答，不要编造信息
2. 引用相关概念时使用 [[概念名]] 格式
3. 回答要简洁、有条理
4. 如果上下文中没有足够信息，明确说明"""

    prompt = f"""上下文信息：
{context}

用户问题：{query}

请根据上下文回答："""

    try:
        messages = [{"role": "system", "content": system}, {"role": "user", "content": prompt}]
        response = client.chat.completions.create(
            model=MODEL,
            max_tokens=2048,
            messages=messages,
        )
        return response.choices[0].message.content.strip()
    except (openai.APIError, openai.APITimeoutError, openai.RateLimitError) as e:
        logger.error(f"LLM API error: {e}")
        return None
    except (AttributeError, KeyError, IndexError) as e:
        logger.error(f"LLM response parsing error: {e}")
        return None


# ============================================================
# 客户端管理（保持不变）
# ============================================================


def read_openclaw_config(logger: logging.Logger | None = None) -> dict | None:
    """读取 OpenClaw 配置文件，返回 providers.zai 的配置

    Args:
        logger: 日志记录器

    Returns:
        配置字典，失败时返回 None
    """
    try:
        with open(OPENCLAW_CONFIG_PATH, encoding="utf-8") as f:
            config = json.load(f)
        provider = config.get("models", {}).get("providers", {}).get("zai", {})
        if provider and provider.get("apiKey"):
            if logger:
                logger.info("从 OpenClaw 配置读取 API Key")
                logger.info(f"Base URL: {provider.get('baseUrl', 'default')}")
            return provider
        else:
            if logger:
                logger.error("未在 OpenClaw 配置中找到 models.providers.zai.apiKey")
            return None
    except (json.JSONDecodeError, OSError, UnicodeDecodeError) as e:
        if logger:
            logger.error(f"读取 OpenClaw 配置失败: {e}")
        return None
    except KeyError as e:
        if logger:
            logger.error(f"OpenClaw 配置格式错误，缺少键: {e}")
        return None


def create_client(logger: logging.Logger | None = None) -> openai.OpenAI | None:
    """创建 OpenAI 兼容客户端（按优先级读取 API Key）

    API Key 优先级:
    1. 环境变量 OPENAI_API_KEY
    2. settings.py 中的 api_key
    3. OpenClaw 配置文件（fallback）

    Args:
        logger: 日志记录器

    Returns:
        OpenAI 客户端实例，失败时返回 None
    """
    global _llm_client_cache
    if _llm_client_cache is not None:
        return _llm_client_cache

    # 1. 优先尝试环境变量
    api_key = os.environ.get("OPENAI_API_KEY")
    if api_key:
        try:
            settings = get_settings()
            base_url = settings.api_base
            client_kwargs = {"api_key": api_key, "timeout": 60}
            if base_url:
                client_kwargs["base_url"] = base_url
            _llm_client_cache = openai.OpenAI(**client_kwargs)
            if logger:
                logger.info(f"OpenAI 兼容客户端创建成功（使用环境变量，Base URL: {base_url}）")
            return _llm_client_cache
        except (openai.OpenAIError, ValueError) as e:
            if logger:
                logger.error(f"使用环境变量创建客户端失败: {e}")

    # 2. 尝试 settings.py 中的 api_key
    settings = get_settings()
    if settings.api_key:
        try:
            client_kwargs = {"api_key": settings.api_key, "timeout": 60}
            if settings.api_base:
                client_kwargs["base_url"] = settings.api_base
            _llm_client_cache = openai.OpenAI(**client_kwargs)
            if logger:
                logger.info(f"OpenAI 兼容客户端创建成功（使用 settings，Base URL: {settings.api_base}）")
            return _llm_client_cache
        except (openai.OpenAIError, ValueError) as e:
            if logger:
                logger.error(f"使用 settings 创建客户端失败: {e}")

    # 3. Fallback: 尝试 OpenClaw 配置文件
    provider = read_openclaw_config(logger)
    if provider:
        try:
            client_kwargs = {"api_key": provider["apiKey"], "timeout": 60}
            if provider.get("baseUrl"):
                client_kwargs["base_url"] = provider["baseUrl"]
            _llm_client_cache = openai.OpenAI(**client_kwargs)
            if logger:
                logger.info("OpenAI 兼容客户端创建成功（使用 OpenClaw 配置）")
            return _llm_client_cache
        except (openai.OpenAIError, TypeError, ValueError) as e:
            if logger:
                logger.error(f"使用 OpenClaw 配置创建客户端失败: {e}")

    if logger:
        logger.error("无法创建 LLM 客户端：环境变量、settings、OpenClaw 配置中均未找到 API Key")
    return None


# ============================================================
# print_result
# ============================================================


def print_result(result: dict) -> None:
    """打印查询结果"""
    print(f"\n{'=' * 60}")
    print(f"查询: {result['query']}")
    print(f"模式: {result['mode']}")
    if result.get("search_sources"):
        print(f"来源: {', '.join(result['search_sources'])}")
    print(f"耗时: {result['time_seconds']}s")
    print(f"{'=' * 60}")

    if result["concepts"]:
        print(f"\n## 相关概念 ({len(result['concepts'])})")
        for c in result["concepts"]:
            src_tag = f" [{c.get('source', '?')}]" if c.get("source") else ""
            mid = c.get("manifest_id", "")
            mid_tag = f" ({mid})" if mid else ""
            print(f"  [[{c['name']}]]{src_tag}{mid_tag} (score: {c['score']})")
            if c.get("definition"):
                print(f"    {c['definition'][:100]}")

    if result["summaries"]:
        print(f"\n## 相关资料 ({len(result['summaries'])})")
        for s in result["summaries"]:
            src_tag = f" [{s.get('source', '?')}]" if s.get("source") else ""
            mid = s.get("manifest_id", "")
            mid_tag = f" ({mid})" if mid else ""
            print(f"  [[{s['title']}]]{src_tag}{mid_tag} (score: {s['score']})")
            if s.get("one_line"):
                print(f"    {s['one_line']}")

    if result["vector_results"]:
        print(f"\n## 向量检索 ({len(result['vector_results'])})")
        for v in result["vector_results"]:
            print(f"  [{v['source']}] (score: {v['score']:.3f})")
            print(f"    {v['text'][:100]}...")

    if result["answer"]:
        print("\n## AI 回答")
        print(result["answer"])
