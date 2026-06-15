"""
Phase 3 查询引擎：搜索接口、向量检索、LLM 回答生成、客户端管理
"""

import hashlib
import json
import logging
import os
from collections.abc import AsyncIterator
from typing import Any, cast

from dochris.llm.openai_compat import OpenAICompatProvider
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
from dochris.rag.schemas import RetrievalCandidate, SourceRef
from dochris.settings import OPENCLAW_CONFIG_PATH, get_settings


def _get_query_model() -> str:
    """动态获取查询模型名称（每次调用读取最新 settings）"""
    return get_settings().query_model


# 全局缓存
_llm_client_cache: OpenAICompatProvider | None = None
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
# 统一候选模型转换
# ============================================================


def retrieve_candidates(
    query: str,
    top_k: int = 5,
    candidate_k: int | None = None,
) -> list["RetrievalCandidate"]:
    """将多通道检索结果转为统一 RetrievalCandidate 列表。

    新入口，不影响 search_all() 的返回格式。返回强类型
    RetrievalCandidate 列表，所有后续方案通过此模型访问检索结果，
    不再猜测分数语义。

    Args:
        query: 查询文本
        top_k: 每个通道的最大结果数
        candidate_k: 总候选数上限（默认不限制）

    Returns:
        按 normalized_score 降序排列的 RetrievalCandidate 列表
    """
    from dochris.rag.schemas import RetrievalCandidate, normalize_score

    # rerank 模式下用 candidate_k 扩大召回，让 reranker 有足够候选精排
    fetch_k = candidate_k if candidate_k and candidate_k > top_k else top_k

    # 可观测性：记录检索操作
    _obs_start = _obs_time()
    raw_results = search_all(query, fetch_k)

    _record_retrieval_obs(
        retriever="search_all",
        candidate_count=sum(len(raw_results.get(k, [])) for k in ("concepts", "summaries", "vector_results")),
        latency_ms=_obs_elapsed_ms(_obs_start),
    )

    candidates: list[RetrievalCandidate] = []

    # 转换 concepts
    for i, item in enumerate(raw_results.get("concepts", [])):
        raw_score = float(item.get("score", 0))
        c = RetrievalCandidate(
            id=f"concept_{item.get('manifest_id', 'unknown')}_{i}",
            text=item.get("definition", item.get("content", "")),
            source=item.get("source", ""),
            channel="concept",
            retriever="keyword_concept",
            raw_score=raw_score,
            score_kind="keyword",
            normalized_score=normalize_score(raw_score, "keyword"),
            channel_rank=i + 1,
            manifest_id=item.get("manifest_id"),
            metadata={"name": item.get("name", ""), "title": item.get("title", "")},
        )
        candidates.append(c)

    # 转换 summaries
    for i, item in enumerate(raw_results.get("summaries", [])):
        raw_score = float(item.get("score", 0))
        c = RetrievalCandidate(
            id=f"summary_{item.get('manifest_id', 'unknown')}_{i}",
            text=item.get("content", item.get("text", "")),
            source=item.get("source", ""),
            channel="summary",
            retriever="keyword_summary",
            raw_score=raw_score,
            score_kind="keyword",
            normalized_score=normalize_score(raw_score, "keyword"),
            channel_rank=i + 1,
            manifest_id=item.get("manifest_id"),
            metadata={"title": item.get("title", "")},
        )
        candidates.append(c)

    # 转换 vector_results
    settings = get_settings()
    vector_store_type = settings.vector_store
    for i, item in enumerate(raw_results.get("vector_results", [])):
        raw_score = float(item.get("score", 0))
        raw_distance = raw_score  # vector search returns distance as score
        score_kind = "cosine_distance" if vector_store_type == "chromadb" else "l2_distance"
        c = RetrievalCandidate(
            id=f"vec_{item.get('manifest_id', 'unknown')}_{i}",
            text=item.get("text", ""),
            source=item.get("source", ""),
            channel="vector",
            retriever=vector_store_type,
            raw_score=raw_score,
            raw_distance=raw_distance,
            score_kind=score_kind,
            normalized_score=normalize_score(raw_score, score_kind, raw_distance),
            channel_rank=i + 1,
            manifest_id=item.get("manifest_id"),
            metadata={"type": item.get("type", "")},
        )
        candidates.append(c)

    # 按归一化分数降序排列
    candidates.sort(key=lambda x: x.normalized_score, reverse=True)

    # 去重：同一 manifest_id + 内容 hash 只保留归一化分数最高的候选
    seen: set[str] = set()
    deduped: list[RetrievalCandidate] = []
    for c in candidates:
        dedup_key = f"{c.manifest_id}_{c.content_hash()}"
        if dedup_key not in seen:
            seen.add(dedup_key)
            deduped.append(c)

    # 填充全局 rank
    for i, c in enumerate(deduped):
        c.rank = i + 1

    # 截断到 candidate_k
    if candidate_k is not None:
        deduped = deduped[:candidate_k]

    return deduped


# ============================================================
# Reranker 重排序
# ============================================================


def rerank_candidates(
    query: str,
    candidates: list[RetrievalCandidate],
    top_k: int = 5,
) -> list[RetrievalCandidate]:
    """对已归一化的候选列表进行重排序。

    仅在 Settings.reranker_enabled == "true" 时执行重排序，
    否则直接截断到 top_k 返回。

    Args:
        query: 用户查询文本
        candidates: retrieve_candidates() 返回的已归一化候选列表
        top_k: 最终返回的候选数量

    Returns:
        重排序后的候选列表（长度 <= top_k），
        每个候选的 rerank_score 被填充
    """
    settings = get_settings()

    if settings.reranker_enabled != "true":
        # Reranker 未启用，直接截断
        return candidates[:top_k]

    if not candidates:
        return []

    try:
        from dochris.rag.reranker.factory import create_reranker

        reranker = create_reranker(
            provider=settings.reranker_provider,
            model_name=settings.reranker_model,
        )
        _rerank_start = _obs_time()
        reranked = reranker.rerank(query, candidates, top_k=top_k)

        _record_rerank_obs(
            provider=settings.reranker_provider,
            input_count=len(candidates),
            output_count=len(reranked),
            latency_ms=_obs_elapsed_ms(_rerank_start),
        )

        logger = logging.getLogger("query_engine")
        logger.info(
            "Reranker 重排序完成: %d → %d 候选 (provider=%s, model=%s)",
            len(candidates),
            len(reranked),
            settings.reranker_provider,
            settings.reranker_model,
        )
        return reranked
    except ImportError as e:
        logger = logging.getLogger("query_engine")
        logger.warning("Reranker 依赖未安装，跳过重排序: %s", e)
        return candidates[:top_k]
    except Exception as e:
        logger = logging.getLogger("query_engine")
        logger.warning("Reranker 执行失败，回退到原始排序: %s", e)
        return candidates[:top_k]


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
                        raw_id = results["ids"][0][i] if results.get("ids") else ""
                        # 适配多后端 metadata schema（source/name/file）+ 从 id 提取 manifest_id
                        source = (
                            metadata.get("source")
                            or metadata.get("name")
                            or metadata.get("file")
                            or "unknown"
                        )
                        manifest_id = metadata.get("manifest_id") or _extract_manifest_id(raw_id)
                        all_results.append(
                            {
                                "text": doc[:500],
                                "source": source,
                                "score": results["distances"][0][i] if results["distances"] else 0,
                                "type": "vector",
                                "manifest_id": manifest_id,
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


def _extract_manifest_id(raw_id: str) -> str | None:
    """从向量库的文档 id 提取 manifest_id。

    适配不同 collection 的 id 格式：
    - summaries/concepts: "summary:SRC-0001" / "concept:名称" → "SRC-0001"
    - chunks: "SRC-0001_chunk_0001" → "SRC-0001"
    """
    if not raw_id:
        return None
    # 优先匹配 SRC-NNNN 模式
    import re

    m = re.search(r"(SRC-\d+)", raw_id)
    return m.group(1) if m else None


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

        # 读取 trust_level 过滤配置（仅 chunks collection 受影响）
        from dochris.settings import get_settings

        min_trust = get_settings().query_min_trust_level or ""

        all_results: list[dict] = []
        for collection in collections:
            try:
                # chunks collection 按 trust_level 过滤（启用时仅检索 wiki 及以上信任层）
                where = {"trust_level": min_trust} if collection == "chunks" and min_trust else None
                results = store.query(  # type: ignore[attr-defined]
                    collection=collection,
                    query_text=query,
                    n_results=top_k,
                    where=where,
                )
                for r in results:
                    metadata = r.get("metadata", {})
                    raw_id = r.get("id", "")
                    # 适配多后端的 metadata schema：
                    # - summaries/concepts: metadata.name + id 含 "summary:SRC-NNNN" 前缀
                    # - chunks: metadata.source + metadata.manifest_id
                    source = (
                        metadata.get("source")
                        or metadata.get("name")
                        or metadata.get("file")
                        or "unknown"
                    )
                    manifest_id = metadata.get("manifest_id") or _extract_manifest_id(raw_id)
                    all_results.append(
                        {
                            "text": r.get("document", "")[:500],
                            "source": source,
                            "score": r.get("distance", 0),
                            "type": "vector",
                            "manifest_id": manifest_id,
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


def build_answer_context(
    concepts: list[dict],
    summaries: list[dict],
    vector_results: list[dict],
) -> tuple[str, dict[str, SourceRef]]:
    """从检索结果构建统一的上下文字符串和来源引用映射。

    Args:
        concepts: 概念检索结果列表
        summaries: 摘要检索结果列表
        vector_results: 向量检索结果列表

    Returns:
        (context_text, source_map):
          - context_text: 用于 LLM prompt 的拼接上下文字符串，空结果时为 ""
          - source_map: 来源编号 "S1"/"S2"/... 到 SourceRef 的映射，空结果时为空 dict
    """
    context_parts: list[str] = []
    source_map: dict[str, SourceRef] = {}
    source_idx = 0

    if concepts:
        context_parts.append("### 相关概念\n")
        for c in concepts:
            source_idx += 1
            name = c.get("name", "")
            definition = c.get("definition", c.get("explanation", ""))
            context_parts.append(f"[S{source_idx}] **{name}**: {definition}")
            source_map[f"S{source_idx}"] = SourceRef(
                manifest_id=c.get("manifest_id"),
                source=c.get("source", ""),
                channel="concept",
                text_hash=hashlib.sha256(definition.encode()).hexdigest()[:12],
                score=float(c.get("score", 0)),
            )

    if summaries:
        context_parts.append("\n### 相关资料\n")
        for s in summaries:
            source_idx += 1
            title = s.get("title", "")
            one_line = s.get("one_line", "")
            context_parts.append(f"[S{source_idx}] **{title}**: {one_line}")
            for kp in s.get("key_points", []):
                context_parts.append(f"  - {kp}")
            source_map[f"S{source_idx}"] = SourceRef(
                manifest_id=s.get("manifest_id"),
                source=s.get("source", ""),
                channel="summary",
                text_hash=hashlib.sha256((one_line + title).encode()).hexdigest()[:12],
                score=float(s.get("score", 0)),
            )

    if vector_results:
        context_parts.append("\n### 向量检索结果\n")
        for v in vector_results:
            source_idx += 1
            text = v.get("text", v.get("definition", v.get("content", "")))[:300]
            context_parts.append(f"[S{source_idx}] [来源: {v.get('source', '')}] {text}")
            source_map[f"S{source_idx}"] = SourceRef(
                manifest_id=v.get("manifest_id"),
                source=v.get("source", ""),
                channel="vector",
                text_hash=hashlib.sha256(text.encode()).hexdigest()[:12],
                score=float(v.get("score", 0)),
            )

    context = "\n".join(context_parts)
    return context, source_map


def build_answer_prompt(
    context: str,
    query: str,
    concepts: list[dict],
) -> tuple[str, str, set[str]]:
    """构建 system prompt 和 user prompt。

    Args:
        context: 由 build_answer_context() 返回的上下文字符串
        query: 用户查询
        concepts: 概念列表（用于构建 wiki-link 白名单）

    Returns:
        (system_prompt, user_prompt, all_known_concepts)
    """
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

    return system, prompt, all_known


async def generate_answer_async(
    query: str,
    concepts: list[dict],
    summaries: list[dict],
    vector_results: list[dict],
    provider: OpenAICompatProvider,
    logger: logging.Logger,
) -> str | None:
    """使用 LLM 异步生成回答（三层幻觉防护：Prompt 锚定 + 概念白名单 + 后处理验证）

    通过 BaseLLMProvider 子类调用 LLM，与编译链路共享抽象层。
    支持查询缓存：相同查询 + 相同上下文直接返回缓存结果。

    Args:
        query: 用户问题
        concepts: 相关概念列表
        summaries: 相关摘要列表
        vector_results: 向量检索结果
        provider: OpenAICompatProvider 实例
        logger: 日志记录器

    Returns:
        生成的回答文本，失败时返回 None
    """
    context, _source_map = build_answer_context(concepts, summaries, vector_results)
    if not context:
        return "未找到相关内容。请尝试其他关键词。"

    # 查询缓存检查
    from dochris.core.cache import load_query_cache, query_cache_key, save_query_cache

    settings = get_settings()
    cache_key = query_cache_key(query, context)
    cached = load_query_cache(settings.cache_dir, cache_key)
    if cached is not None:
        logger.info(f"Query cache hit for: {query[:50]}...")
        return cached

    system, prompt, all_known = build_answer_prompt(context, query, concepts)

    try:
        answer = await provider.generate_with_messages(
            messages=[{"role": "system", "content": system}, {"role": "user", "content": prompt}],
            max_tokens=2048,
            temperature=0.1,
        )
        if not answer:
            return None
        answer = answer.strip()

        # Layer 3: 后处理验证，清除虚假 wiki-link
        answer = _sanitize_wiki_links(answer, all_known)

        # 保存到缓存
        save_query_cache(settings.cache_dir, cache_key, answer)
        return answer
    except Exception as e:
        logger.error(f"LLM API error: {e}")
        return None


async def generate_answer_stream_async(
    query: str,
    concepts: list[dict],
    summaries: list[dict],
    vector_results: list[dict],
    provider: OpenAICompatProvider,
    logger: logging.Logger,
) -> AsyncIterator[str]:
    """异步流式生成回答，逐 chunk yield。

    通过 BaseLLMProvider.generate_stream() 调用 LLM。

    Yields:
        str: 每个 chunk 的文本内容
    """
    context, _source_map = build_answer_context(concepts, summaries, vector_results)
    if not context:
        yield "未找到相关内容。请尝试其他关键词。"
        return

    # 查询缓存检查
    from dochris.core.cache import load_query_cache, query_cache_key, save_query_cache

    settings = get_settings()
    cache_key = query_cache_key(query, context)
    cached = load_query_cache(settings.cache_dir, cache_key)
    if cached is not None:
        logger.info(f"Query cache hit (stream) for: {query[:50]}...")
        yield cached
        return

    system, prompt, all_known = build_answer_prompt(context, query, concepts)

    try:
        full_answer: list[str] = []
        async for chunk in provider.generate_stream(
            prompt=prompt,
            system_prompt=system,
            max_tokens=2048,
            temperature=0.1,
        ):
            full_answer.append(chunk)
            yield chunk

        # 后处理并缓存完整回答
        answer = "".join(full_answer).strip()
        answer = _sanitize_wiki_links(answer, all_known)
        save_query_cache(settings.cache_dir, cache_key, answer)

    except Exception as e:
        logger.error(f"LLM API error (stream): {e}")
        yield f"\n\n[错误] LLM 请求失败: {e}"


# ============================================================
# 客户端管理
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


def _try_create_provider(
    api_key: str,
    base_url: str | None,
    model: str,
    logger: logging.Logger | None,
    source_label: str,
) -> OpenAICompatProvider | None:
    """尝试用给定参数创建 OpenAICompatProvider。

    Args:
        api_key: API 密钥
        base_url: API 基础 URL（可为 None）
        model: 模型名称
        logger: 日志记录器
        source_label: 来源标签（用于日志）

    Returns:
        创建成功的 provider，失败时返回 None
    """
    try:
        provider = OpenAICompatProvider(
            api_key=api_key,
            api_base=base_url,
            model=model,
            max_tokens=2048,
            temperature=0.1,
            timeout=60,
        )
        if logger:
            logger.info(f"Query LLM provider created ({source_label}, base_url={base_url})")
        return provider
    except Exception as e:
        if logger:
            logger.error(f"Failed to create provider ({source_label}): {e}")
        return None


def create_query_provider(logger: logging.Logger | None = None) -> OpenAICompatProvider | None:
    """创建查询链路 LLM Provider（3 级 fallback：env → settings → OpenClaw）

    使用 OpenAICompatProvider（内部 AsyncOpenAI），与编译链路统一抽象。

    API Key 优先级:
    1. 环境变量 OPENAI_API_KEY
    2. settings 中的 api_key
    3. OpenClaw 配置文件（fallback）

    Args:
        logger: 日志记录器

    Returns:
        OpenAICompatProvider 实例，失败时返回 None
    """
    global _llm_client_cache
    if _llm_client_cache is not None:
        return _llm_client_cache

    settings = get_settings()
    model = settings.query_model

    # 1. 优先尝试环境变量
    api_key = os.environ.get("OPENAI_API_KEY")
    if api_key:
        provider = _try_create_provider(api_key, settings.api_base, model, logger, "env var")
        if provider:
            _llm_client_cache = provider
            return _llm_client_cache

    # 2. 尝试 settings 中的 api_key
    if settings.api_key:
        provider = _try_create_provider(
            settings.api_key, settings.api_base, model, logger, "settings"
        )
        if provider:
            _llm_client_cache = provider
            return _llm_client_cache

    # 3. Fallback: 尝试 OpenClaw 配置文件
    openclaw = read_openclaw_config(logger)
    if openclaw:
        base_url = openclaw.get("baseUrl") or None
        provider = _try_create_provider(
            openclaw["apiKey"], base_url, model, logger, "OpenClaw config"
        )
        if provider:
            _llm_client_cache = provider
            return _llm_client_cache

    if logger:
        logger.error("Cannot create query LLM provider: no API key found in env/settings/OpenClaw")
    return None


def create_client(logger: logging.Logger | None = None) -> OpenAICompatProvider | None:
    """已废弃：请使用 create_query_provider()。

    保留为向后兼容 alias，供尚未迁移的调用方使用。
    """
    return create_query_provider(logger)


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


# ============================================================
# 可观测性辅助函数（零开销 fallback）
# ============================================================


def _obs_time() -> float:
    """获取当前时间（秒）。"""
    import time

    return time.time()


def _obs_elapsed_ms(start: float) -> float:
    """计算耗时（毫秒）。"""
    import time

    return (time.time() - start) * 1000


def _record_retrieval_obs(
    retriever: str, candidate_count: int, latency_ms: float
) -> None:
    """记录检索可观测性指标（静默 fallback）。"""
    try:
        from dochris.observability import get_observability

        obs = get_observability()
        if obs.enabled:
            obs.record_retrieval(
                query="",
                candidate_count=candidate_count,
                latency_ms=latency_ms,
                retriever_type=retriever,
            )
    except Exception:
        pass


def _record_rerank_obs(
    provider: str,
    input_count: int,
    output_count: int,
    latency_ms: float,
) -> None:
    """记录 Rerank 可观测性指标（静默 fallback）。"""
    try:
        from dochris.observability.metrics import record_rerank

        record_rerank(
            provider=provider,
            input_count=input_count,
            output_count=output_count,
            latency=latency_ms / 1000.0,
        )
    except Exception:
        pass
