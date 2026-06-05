"""
Phase 3 查询引擎：搜索接口、向量检索、LLM 回答生成、客户端管理
"""

import json
import logging
import os
from typing import Any, cast

import openai

from dochris.phases.query_utils import (
    DATA_PATH,
    MANIFESTS_PATH,
    OUTPUTS_CONCEPTS_PATH,
    OUTPUTS_SUMMARIES_PATH,
    WIKI_CONCEPTS_PATH,
    WIKI_SUMMARIES_PATH,
    _extract_concept,
    _extract_summary,
    _keyword_search,
)
from dochris.plugin import get_plugin_manager
from dochris.settings import OPENCLAW_CONFIG_PATH, get_settings


def _get_query_model() -> str:
    """动态获取查询模型名称（每次调用读取最新 settings）"""
    return get_settings().query_model

# 全局缓存
_llm_client_cache: openai.OpenAI | None = None
_chromadb_client_cache: Any | None = None
_vector_store_cache: Any | None = None


def clear_caches() -> None:
    """清理全局缓存，释放资源"""
    global _llm_client_cache, _chromadb_client_cache, _vector_store_cache
    _llm_client_cache = None
    _chromadb_client_cache = None
    _vector_store_cache = None


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
        _vector_store_cache = store_cls(persist_directory=str(DATA_PATH))  # type: ignore[call-arg]
    elif settings.vector_store == "leann":
        # LEANN 使用 data_dir 下的子目录
        _vector_store_cache = store_cls(index_dir=str(DATA_PATH / "leann_indexes"))  # type: ignore[call-arg]
    else:
        # 其他存储使用默认配置
        _vector_store_cache = store_cls()

    return _vector_store_cache


# ============================================================
# 搜索接口（保持向后兼容）
# ============================================================


def search_concepts(query: str, top_k: int = 5) -> list[dict]:
    """搜索概念 — wiki 优先，outputs fallback，manifest 兜底

    三级 fallback 策略:
    1. wiki/concepts/ 关键词搜索（已晋升，高信任）
    2. outputs/concepts/ 关键词搜索（编译产物）
    3. manifest compiled_summary.concepts 遍历（兜底，覆盖宽泛查询）
    """
    # 查询前处理
    plugin_manager = get_plugin_manager()
    processed_query = plugin_manager.call_hook_firstresult("pre_query", query) or query

    wiki_results = _keyword_search(
        processed_query,
        WIKI_CONCEPTS_PATH,
        top_k,
        _extract_concept,
        "wiki",
    )
    if wiki_results:
        return wiki_results

    outputs_results = _keyword_search(
        processed_query,
        OUTPUTS_CONCEPTS_PATH,
        top_k,
        _extract_concept,
        "outputs",
    )
    if outputs_results:
        return outputs_results

    # Fallback: 从 manifest 的 compiled_summary.concepts 中搜索
    return _search_manifest_concepts(processed_query, top_k)


def _search_manifest_concepts(query: str, top_k: int = 5) -> list[dict]:
    """从 manifest 的 compiled_summary.concepts 中搜索概念

    当文件名关键词匹配失败时，遍历所有已编译 manifest 的概念列表，
    对概念名和解释做子串匹配。

    Args:
        query: 查询字符串
        top_k: 最大返回数

    Returns:
        匹配的概念列表
    """
    if not MANIFESTS_PATH.exists():
        return []

    import json
    import re

    results: list[dict] = []
    query_lower = query.lower()
    # 提取查询中的关键词（中文按 2-3 字切分，英文按空格分词）
    query_terms = set()
    for token in re.findall(r"[a-z0-9_]+|[一-鿿]+", query_lower):
        query_terms.add(token)
        if re.fullmatch(r"[一-鿿]+", token):
            query_terms.update(token[i : i + 2] for i in range(len(token) - 1))

    if not query_terms:
        return []

    for manifest_file in MANIFESTS_PATH.glob("SRC-*.json"):
        try:
            with open(manifest_file, encoding="utf-8") as f:
                m = json.load(f)
        except (json.JSONDecodeError, OSError, UnicodeDecodeError):
            continue

        compiled = m.get("compiled_summary")
        if not compiled or not isinstance(compiled, dict):
            continue

        raw_concepts = compiled.get("concepts", [])
        if not isinstance(raw_concepts, list):
            continue

        for concept in raw_concepts:
            if isinstance(concept, dict):
                name = str(concept.get("name", "") or "").strip()
                explanation = str(concept.get("explanation", "") or "").strip()
            elif isinstance(concept, str) and concept.strip():
                name = concept.strip()
                explanation = ""
            else:
                continue

            if not name:
                continue

            name_lower = name.lower()
            expl_lower = explanation.lower()

            score = 0
            for term in query_terms:
                if term in name_lower:
                    score += 5
                if term in expl_lower:
                    score += 2

            if score > 0:
                results.append(
                    {
                        "name": name,
                        "definition": explanation,
                        "title": name,
                        "content": explanation,
                        "score": score,
                        "source": "outputs",
                        "manifest_id": m.get("id"),
                    }
                )

    results.sort(key=lambda x: x["score"], reverse=True)
    return results[:top_k]


def search_summaries(query: str, top_k: int = 5) -> list[dict]:
    """搜索摘要 — wiki 优先，outputs fallback"""
    # 查询前处理
    plugin_manager = get_plugin_manager()
    processed_query = plugin_manager.call_hook_firstresult("pre_query", query) or query

    wiki_results = _keyword_search(
        processed_query,
        WIKI_SUMMARIES_PATH,
        top_k,
        _extract_summary,
        "wiki",
    )
    if wiki_results:
        return wiki_results

    return _keyword_search(
        processed_query,
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
    # 查询前处理
    plugin_manager = get_plugin_manager()
    processed_query = plugin_manager.call_hook_firstresult("pre_query", query) or query

    concepts = search_concepts(processed_query, top_k)
    summaries = search_summaries(processed_query, top_k)

    # 确定搜索来源
    sources_used = set()
    if concepts:
        sources_used.add(concepts[0]["source"])
    if summaries:
        sources_used.add(summaries[0]["source"])

    # 向量检索始终执行（作为补充）
    vector_results = vector_search(processed_query, top_k)
    if vector_results:
        sources_used.add("vector")

    results = {
        "concepts": concepts,
        "summaries": summaries,
        "vector_results": vector_results,
        "search_sources": sorted(sources_used),
    }

    # 查询后处理
    post_processed = plugin_manager.call_hook("post_query", query, [results])
    if post_processed and post_processed[0] is not None:
        return cast(dict[str, Any], post_processed[0])

    return results


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
        import os

        # 阻止 ChromaDB 默认 embedding function 尝试连接 HuggingFace Hub
        os.environ.setdefault("HF_HUB_OFFLINE", "1")

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
            except Exception as e:
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
        collections = store.list_collections()  # type: ignore[attr-defined]

        if not collections:
            if logger:
                logger.debug("No vector store collections found")
            return []

        all_results: list[dict] = []
        for collection in collections:
            try:
                results = store.query(  # type: ignore[attr-defined]
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


def _get_all_concept_names() -> list[str]:
    """获取知识库中所有已知概念名（用于 wiki-link 白名单）"""
    names: list[str] = []
    for concepts_dir in [OUTPUTS_CONCEPTS_PATH, WIKI_CONCEPTS_PATH]:
        if concepts_dir.exists():
            for md_file in concepts_dir.glob("*.md"):
                names.append(md_file.stem)
    return list(dict.fromkeys(names))  # 去重保序


def _sanitize_wiki_links(answer: str, valid_concepts: set[str]) -> str:
    """后处理：验证 [[概念名]] 链接，移除指向不存在概念的双方括号"""
    import re as _re

    def _replace(match: _re.Match[str]) -> str:
        name = match.group(1)
        if name in valid_concepts:
            return f"[[{name}]]"
        return name

    return _re.sub(r"\[\[([^\]]+)\]\]", _replace, answer)


def generate_answer(
    query: str,
    concepts: list[dict],
    summaries: list[dict],
    vector_results: list[dict],
    client: openai.OpenAI,
    logger: logging.Logger,
    stream: bool = False,
) -> str | None:
    """使用 LLM 综合生成回答（三层幻觉防护：Prompt 锚定 + 概念白名单 + 后处理验证）

    支持查询缓存：相同查询 + 相同上下文直接返回缓存结果。

    Args:
        query: 用户问题
        concepts: 相关概念列表
        summaries: 相关摘要列表
        vector_results: 向量检索结果
        client: OpenAI 客户端
        logger: 日志记录器
        stream: 是否使用流式输出（由 generate_answer_stream 使用）

    Returns:
        生成的回答文本，失败时返回 None
    """
    context_parts: list[str] = []
    source_idx = 0

    if concepts:
        context_parts.append("### 相关概念\n")
        for c in concepts:
            source_idx += 1
            name = c.get("name", "")
            definition = c.get("definition", c.get("explanation", ""))
            context_parts.append(f"[S{source_idx}] **{name}**: {definition}")

    if summaries:
        context_parts.append("\n### 相关资料\n")
        for s in summaries:
            source_idx += 1
            title = s.get("title", "")
            one_line = s.get("one_line", "")
            context_parts.append(f"[S{source_idx}] **{title}**: {one_line}")
            for kp in s.get("key_points", []):
                context_parts.append(f"  - {kp}")

    if vector_results:
        context_parts.append("\n### 向量检索结果\n")
        for v in vector_results:
            source_idx += 1
            text = v.get("text", v.get("definition", v.get("content", "")))[:300]
            context_parts.append(f"[S{source_idx}] [来源: {v.get('source', '')}] {text}")

    if not context_parts:
        return "未找到相关内容。请尝试其他关键词。"

    context = "\n".join(context_parts)

    # 查询缓存检查
    from dochris.core.cache import load_query_cache, query_cache_key, save_query_cache

    settings = get_settings()
    cache_key = query_cache_key(query, context)
    cached = load_query_cache(settings.cache_dir, cache_key)
    if cached is not None:
        logger.info(f"Query cache hit for: {query[:50]}...")
        return cached

    # 构建 wiki-link 白名单：检索到的概念名 + 知识库全部概念名
    retrieved_names = {c.get("name", "") for c in concepts if c.get("name")}
    all_known = set(_get_all_concept_names()) | retrieved_names
    concept_allowlist_str = "、".join(sorted(all_known)) if all_known else "（无）"

    system = (
        "你是一个严格基于源文档的知识库助手。\n\n"
        "## 严格规则\n\n"
        "1. **只使用上下文中的信息**：你的回答必须完全基于下方 CONTEXT 中提供的检索结果。"
        "不得使用任何外部知识、推断或假设。\n"
        "2. **强制引用**：每个事实性陈述必须标注来源编号 [S1], [S2] 等。"
        "示例：「根据资料，软着陆是指房价通过长时间的价值回归实现下跌 [S1]。」\n"
        f"3. **Wiki-link 规则**：使用 [[概念名]] 格式引用概念时，"
        f"只能使用以下已知概念：{concept_allowlist_str}。不得为不存在的概念创建链接。\n"
        "4. **信息不足时拒绝回答**：如果上下文中没有足够信息回答问题，"
        "回复「根据当前知识库中的资料，无法完整回答这个问题。」并说明缺少哪些信息。\n"
        "5. **不要添加无关内容**：不要扩展、不要解释上下文中未提到的内容。\n\n"
        "## 输出格式\n\n"
        "- 使用清晰的段落结构\n"
        "- 每个事实后标注 [Sn] 引用\n"
        "- 相关概念使用 [[概念名]] 链接（仅限上面列出的已知概念）"
    )

    prompt = f"""CONTEXT:
{context}

用户问题：{query}

请严格基于 CONTEXT 回答，每个事实标注 [Sn] 引用，概念链接仅使用已知概念列表中的名称。"""

    try:
        messages = [{"role": "system", "content": system}, {"role": "user", "content": prompt}]  # type: ignore[list-item]
        response = client.chat.completions.create(
            model=_get_query_model(),
            max_tokens=2048,
            temperature=0.1,
            messages=messages,  # type: ignore[arg-type]
            stream=stream,
        )

        if stream:
            return response  # type: ignore[return-value]

        content = response.choices[0].message.content
        if not content:
            return None
        answer = content.strip()

        # Layer 3: 后处理验证，清除虚假 wiki-link
        answer = _sanitize_wiki_links(answer, all_known)

        # 保存到缓存
        save_query_cache(settings.cache_dir, cache_key, answer)
        return answer
    except (openai.APIError, openai.APITimeoutError, openai.RateLimitError) as e:
        logger.error(f"LLM API error: {e}")
        return None
    except (AttributeError, KeyError, IndexError) as e:
        logger.error(f"LLM response parsing error: {e}")
        return None


def generate_answer_stream(
    query: str,
    concepts: list[dict],
    summaries: list[dict],
    vector_results: list[dict],
    client: openai.OpenAI,
    logger: logging.Logger,
):
    """流式生成回答，逐 chunk 返回

    Yields:
        str: 每个 chunk 的文本内容
    """
    # 构建上下文和 prompt（与 generate_answer 相同的逻辑）
    context_parts: list[str] = []
    source_idx = 0

    if concepts:
        context_parts.append("### 相关概念\n")
        for c in concepts:
            source_idx += 1
            name = c.get("name", "")
            definition = c.get("definition", c.get("explanation", ""))
            context_parts.append(f"[S{source_idx}] **{name}**: {definition}")

    if summaries:
        context_parts.append("\n### 相关资料\n")
        for s in summaries:
            source_idx += 1
            title = s.get("title", "")
            one_line = s.get("one_line", "")
            context_parts.append(f"[S{source_idx}] **{title}**: {one_line}")
            for kp in s.get("key_points", []):
                context_parts.append(f"  - {kp}")

    if vector_results:
        context_parts.append("\n### 向量检索结果\n")
        for v in vector_results:
            source_idx += 1
            text = v.get("text", v.get("definition", v.get("content", "")))[:300]
            context_parts.append(f"[S{source_idx}] [来源: {v.get('source', '')}] {text}")

    if not context_parts:
        yield "未找到相关内容。请尝试其他关键词。"
        return

    context = "\n".join(context_parts)

    # 查询缓存检查
    from dochris.core.cache import load_query_cache, query_cache_key, save_query_cache

    settings = get_settings()
    cache_key = query_cache_key(query, context)
    cached = load_query_cache(settings.cache_dir, cache_key)
    if cached is not None:
        logger.info(f"Query cache hit (stream) for: {query[:50]}...")
        yield cached
        return

    # 构建 prompt
    retrieved_names = {c.get("name", "") for c in concepts if c.get("name")}
    all_known = set(_get_all_concept_names()) | retrieved_names
    concept_allowlist_str = "、".join(sorted(all_known)) if all_known else "（无）"

    system = (
        "你是一个严格基于源文档的知识库助手。\n\n"
        "## 严格规则\n\n"
        "1. **只使用上下文中的信息**：你的回答必须完全基于下方 CONTEXT 中提供的检索结果。"
        "不得使用任何外部知识、推断或假设。\n"
        "2. **强制引用**：每个事实性陈述必须标注来源编号 [S1], [S2] 等。"
        "示例：「根据资料，软着陆是指房价通过长时间的价值回归实现下跌 [S1]。」\n"
        f"3. **Wiki-link 规则**：使用 [[概念名]] 格式引用概念时，"
        f"只能使用以下已知概念：{concept_allowlist_str}。不得为不存在的概念创建链接。\n"
        "4. **信息不足时拒绝回答**：如果上下文中没有足够信息回答问题，"
        "回复「根据当前知识库中的资料，无法完整回答这个问题。」并说明缺少哪些信息。\n"
        "5. **不要添加无关内容**：不要扩展、不要解释上下文中未提到的内容。\n\n"
        "## 输出格式\n\n"
        "- 使用清晰的段落结构\n"
        "- 每个事实后标注 [Sn] 引用\n"
        "- 相关概念使用 [[概念名]] 链接（仅限上面列出的已知概念）"
    )

    prompt = f"""CONTEXT:
{context}

用户问题：{query}

请严格基于 CONTEXT 回答，每个事实标注 [Sn] 引用，概念链接仅使用已知概念列表中的名称。"""

    try:
        messages = [{"role": "system", "content": system}, {"role": "user", "content": prompt}]  # type: ignore[list-item]
        stream_resp = client.chat.completions.create(
            model=_get_query_model(),
            max_tokens=2048,
            temperature=0.1,
            messages=messages,  # type: ignore[arg-type]
            stream=True,
        )

        full_answer = []
        for chunk in stream_resp:
            delta = chunk.choices[0].delta
            if delta.content:
                full_answer.append(delta.content)
                yield delta.content

        # 后处理并缓存完整回答
        answer = "".join(full_answer).strip()
        answer = _sanitize_wiki_links(answer, all_known)
        save_query_cache(settings.cache_dir, cache_key, answer)

    except (openai.APIError, openai.APITimeoutError, openai.RateLimitError) as e:
        logger.error(f"LLM API error (stream): {e}")
        yield f"\n\n[错误] LLM 请求失败: {e}"
    except (AttributeError, KeyError, IndexError) as e:
        logger.error(f"LLM response parsing error (stream): {e}")
        yield f"\n\n[错误] 响应解析失败: {e}"


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
            return cast(dict[str, Any], provider)
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
            if base_url:
                _llm_client_cache = openai.OpenAI(api_key=api_key, base_url=base_url, timeout=60)
            else:
                _llm_client_cache = openai.OpenAI(api_key=api_key, timeout=60)
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
            if settings.api_base:
                _llm_client_cache = openai.OpenAI(
                    api_key=settings.api_key, base_url=settings.api_base, timeout=60
                )
            else:
                _llm_client_cache = openai.OpenAI(api_key=settings.api_key, timeout=60)
            if logger:
                logger.info(
                    f"OpenAI 兼容客户端创建成功（使用 settings，Base URL: {settings.api_base}）"
                )
            return _llm_client_cache
        except (openai.OpenAIError, ValueError) as e:
            if logger:
                logger.error(f"使用 settings 创建客户端失败: {e}")

    # 3. Fallback: 尝试 OpenClaw 配置文件
    provider = read_openclaw_config(logger)
    if provider:
        try:
            base_url = provider.get("baseUrl", "") or ""
            if base_url:
                _llm_client_cache = openai.OpenAI(
                    api_key=provider["apiKey"], base_url=base_url, timeout=60
                )
            else:
                _llm_client_cache = openai.OpenAI(api_key=provider["apiKey"], timeout=60)
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
