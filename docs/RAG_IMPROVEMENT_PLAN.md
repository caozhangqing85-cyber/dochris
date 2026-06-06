# DocChris RAG 高风险短板分析与改进方案

> 本文档基于 2026-06-06 对 DocChris 仓库的只读代码分析与外部资料检索整理。目标是为 RAG 评估、重排序、可观测性、流式输出、语义分块 5 个高风险短板提供可落地的架构方案、接口设计、集成点、测试策略与实施路线。

## 0. 结论摘要

DocChris 已经具备一个完整的个人知识库编译基础：四阶段流水线、四层信任模型、LLM Provider 抽象、向量库抽象、插件扩展点、FastAPI 与 React 前端查询入口。当前高风险问题不在于“能不能查询”，而在于“查询结果是否稳定、可评估、可追踪、可持续优化”。

优先级建议：

1. **第 0 周（前置任务，必须先完成）**：统一查询链路 LLM 客户端（消除同步/异步分裂）、实现统一候选模型 `RetrievalCandidate`（含显式归一化分数语义）、统一 VectorStore 接口（Protocol 对齐 ABC）。这些是后续所有方案的架构基础。
2. **第 1 周**：补 Reranker 和 RAG 评估。前者直接提升上下文质量，后者建立可验证的改进闭环。
3. **第 2 周**：补可观测性和流式输出工程化。前者用于定位线上失败，后者提升交互体验并降低长回答等待成本。
4. **第 3 周**：补语义分块与原文 chunk 索引。该项改动面较大，应依赖第 1 周建立的评估体系验证收益。

## 1. 第一阶段：项目分析报告

### 1.1 架构概览

DocChris 是四阶段知识库编译系统：

```text
源文件
  |
  v
Phase 1 摄入
  - 扫描源文件
  - SHA 去重
  - 创建 manifests/sources/SRC-NNNN.json
  |
  v
Phase 2 编译
  - 解析 PDF / Markdown / Office / 音视频转录 / 代码
  - 调用 LLM 生成 one_line / key_points / detailed_summary / concepts
  - 质量评分、provenance、lint
  - 写 outputs/summaries、outputs/concepts
  - 写入向量库
  |
  v
Phase 3 查询
  - 关键词搜索 wiki/outputs
  - 向量检索 ChromaDB / FAISS / LEANN
  - 拼接上下文
  - LLM 基于 CONTEXT 生成带引用回答
  |
  v
Phase 4 分发
  - quality_gate
  - promote outputs -> wiki -> curated
  - Obsidian 同步
```

关键文件：

- `README.md`：项目定位、四阶段流水线、四层信任模型、功能概览。
- `CLAUDE.md`：架构总览、开发命令、目录结构、开发规范。
- `AGENTS.md`：当前仓库约束，尤其是只读/编辑、GitNexus 和 commit 约束。
- `pyproject.toml`：Python 3.11+，核心依赖 `openai`、`chromadb`、`sentence-transformers`、`json-repair`，可选 API/Web/PDF/OCR/audio/dev 依赖。
- `docker-compose.yml`：核心 `dochris` 服务、API 服务、ChromaDB 服务，API profile 通过 Uvicorn 启动。

### 1.2 核心抽象层

DocChris 同时使用 Protocol 和 ABC：

- `src/dochris/protocols.py`
  - `LLMProvider`：`generate()`、`close()`。
  - `VectorStore`：`add()`、`query()`、`delete()`、`list_collections()`。
  - `FileParser`：`supported_extensions()`、`parse()`。
  - `QualityScorer`：`score()`。
- `src/dochris/llm/base.py`
  - `BaseLLMProvider` ABC，定义 `generate()`、`generate_with_messages()`、`close()`。
- `src/dochris/vector/base.py`
  - `BaseVectorStore` ABC，定义 `add_documents()`、`query()`、`delete()`、`list_collections()`、`get_collection_count()`。

当前设计优点：

- Provider 与 VectorStore 已经具备可替换边界。
- 编译主链路集中在 `CompilerWorker`，便于插入评估、观测、chunking。
- 查询链路已有 `pre_query`、`post_query` 插件点，适合先用插件式方式接入 reranker，再沉淀为核心模块。

当前设计风险：

- 查询链路仍直接使用同步 `openai.OpenAI`，未完全复用 `BaseLLMProvider`。
- `protocols.VectorStore` 和 `vector/base.py` 的方法名不一致：前者是 `add()`，后者是 `add_documents()`。
- ChromaDB 旧查询路径和抽象层路径并存，embedding 配置与距离语义不完全统一。

### 1.3 插件系统扩展点

插件扩展点定义在 `src/dochris/plugin/hookspec.py`：

| Hook | 时机 | 适合扩展 |
| --- | --- | --- |
| `ingest_parser(file_path)` | 文件解析前 | EPUB、网页、专有格式解析 |
| `pre_compile(text, metadata)` | LLM 编译前 | 文本清洗、元数据增强、敏感内容处理 |
| `post_compile(src_id, result)` | 编译完成后 | 通知、索引、评估、异步任务 |
| `quality_score(text, metadata)` | 质量评分 | 替换或补充摘要评分 |
| `pre_query(query)` | 查询前 | Query rewrite、拼写纠错、意图识别 |
| `post_query(query, results)` | 查询后 | rerank、过滤、聚合 |

建议新功能的接入原则：

- 原型阶段优先复用 hooks，避免破坏现有架构。
- 稳定后沉淀为 `dochris.rag.*`、`dochris.eval.*`、`dochris.observability.*` 等核心模块。
- 所有新增能力都保留 `enabled=false` 默认配置，避免影响现有用户。

## 2. RAG 实现现状

### 2.1 文本分块策略

当前文件：`src/dochris/core/text_chunker.py`

当前策略：

1. `structure_aware_split()` 优先按 Markdown 标题切分。
2. 无标题时按数字编号切分。
3. 再回退到 `semantic_chunk()`，但这里的 semantic 是规则式语义边界，不是 embedding-based semantic chunking。
4. 最后可使用 `fixed_size_chunk()`。

默认参数：

- `chunk_size=4000` 字符。
- `overlap=200` 字符。
- Map-Reduce 摘要默认也使用 `chunk_size=4000`、`overlap=200`，但 `SummaryGenerator.generate_summary_smart()` 会按文本长度动态放大 chunk（仅 map_reduce 路径放大至 4000-20000，hierarchical 路径保持默认 4000）。

问题：

- chunk 以字符数计，不以 token 计，中文、英文、代码、表格的上下文窗口消耗不可控。
- 当前向量索引主要嵌入摘要和概念，不索引原文 chunk，RAG 证据颗粒度偏粗。
- 没有基于 embedding 相邻距离的断点选择，也没有 late chunking 或 parent-child chunking。

### 2.2 Embedding 生成方式

当前文件：

- `src/dochris/vector/chromadb_store.py`
- `src/dochris/vector/faiss_store.py`
- `src/dochris/settings/config.py`

当前实现：

- Settings 默认 `embedding_model="BAAI/bge-small-zh-v1.5"`。
- ChromaDB 抽象层默认 `BAAI/bge-small-zh-v1.5`，collection metadata 使用 `hnsw:space=cosine`。
- FAISS 默认 `all-MiniLM-L6-v2`，索引为 `IndexFlatL2`。
- API 启动时预加载 `BAAI/bge-small-zh-v1.5`。

问题：

- FAISS 默认 embedding 与 Settings 不一致。
- ChromaDB 旧路径直接查询现有 collection，依赖 collection 原有 embedding function。
- 缺少 embedding 维度、模型名、索引版本的显式元数据，后续更换模型时难以判断是否需要重建索引。

### 2.3 向量检索方式

当前文件：`src/dochris/phases/query_engine.py`

当前方式：

- `search_concepts()`：wiki 优先，outputs fallback，manifest 概念兜底。
- `search_summaries()`：wiki 优先，outputs fallback。
- `vector_search()`：遍历所有 ChromaDB collection 或抽象层 collection，合并后按 distance 升序排序。
- `search_all()`：关键词结果 + 向量结果并列返回。

问题：

- 没有统一候选对象模型。
- 没有 hybrid score 融合策略。
- 没有 reranker。
- 没有过滤接口透传到 API。
- top-k 同时承担“召回候选数”和“最终上下文数”，不利于两阶段检索。

### 2.4 查询生成方式

当前文件：`src/dochris/phases/query_engine.py`

Prompt 特征：

- 强制只使用 CONTEXT。
- 每个事实标注 `[S1]` 等来源编号。
- 概念链接限制为已知概念白名单。
- 信息不足时拒答。
- 查询缓存以 `query + context` hash 为 key。

缺失能力：

- 无 Query Rewriting。
- 无 HyDE。
- 无多查询扩展。
- 无上下文压缩。
- 无引用级 faithfulness 校验。

### 2.5 Reranker 与 RAG 评估

当前无正式 Reranker。`post_query` hook 可以做结果后处理，但没有标准候选模型、rerank score、阈值、top-n 策略。

当前无 RAG 评估。`QualityScorer` 评的是摘要产物，不评：

- 检索 recall / precision / NDCG / MRR。
- 上下文相关性。
- 回答 faithfulness。
- 回答 relevance。
- 引用是否支持具体句子。

## 3. LLM 调用链路

### 3.1 编译链路

当前文件：

- `src/dochris/core/llm_client.py`
- `src/dochris/core/summary_generator.py`
- `src/dochris/core/hierarchical_summarizer.py`
- `src/dochris/core/retry_manager.py`
- `src/dochris/llm/openai_compat.py`

特征：

- 使用 `AsyncOpenAI`。
- `LLMClient` 创建 provider，并保留 `client` 属性兼容旧代码。
- `SummaryGenerator.generate_summary()` 构造 JSON 输出 prompt。
- 结构化输出解析顺序：`json.loads` -> `json_repair` -> `_extract_json_from_text()`（注意：第三步仅在 `json_repair` 未安装时触发，非"失败后"触发）。
- `RetryManager.llm_retry_with_filter()` 按 429、timeout、content filter、其他错误处理。退避上限受 `MAX_RETRY_WAIT=60` 限制，不会无限增长。
- 编译链路 timeout 为 300 秒（`LLMClient.__init__` 传入），与查询链路 60 秒区分。
- `HierarchicalSummarizer` 支持 Map-Reduce 和分层摘要，但 `_summarize_chunks_parallel()` 当前 `max_parallel=1`，更偏稳定而非吞吐（注：`_summarize_sections_parallel()` 使用 `Semaphore(3)` 并行度不同）。

### 3.2 查询链路

当前文件：`src/dochris/phases/query_engine.py`

特征：

- 使用同步 `openai.OpenAI`。
- client cache 为模块全局变量。
- `create_client()` 按环境变量、settings、OpenClaw fallback 创建 client。
- timeout 为 60 秒（注意：编译链路使用 300 秒，两者不一致）。
- `generate_answer_stream()` 使用 `stream=True`，逐 chunk yield。

问题：

- 查询链路未复用 `BaseLLMProvider`。
- token usage、latency、cost 没有统一记录。
- stream 和 non-stream 逻辑重复。
- 错误类型只记录日志，没有 trace/span 关联。

## 4. 质量体系

### 4.1 QualityScorer

当前文件：`src/dochris/core/quality_scorer.py`

评分维度：

| 维度 | 分值 | 当前算法 |
| --- | ---: | --- |
| detailed_summary 长度 | 25 | 按字符数阶梯给分 |
| key_points 完整性 | 30 | 有效要点数量阶梯给分 |
| 学习价值 | 15 | 命中学习价值关键词数量 |
| 信息密度 | 5 | 命中信息关键词数量 |
| one_line 质量 | 5 | 长度区间判断 |
| concepts 完整性 | 10 | 有效概念数量 |
| 模板文字检测 | -10 | 前 200 字符模板检测 |
| 超长文本惩罚 | -10 | detailed_summary 超 3000 字符后每 500 字扣 1 分，上限 10 分 |

该体系适合评估 Phase 2 输出是否像一份可读摘要，但不能证明 RAG 查询质量。

### 4.2 Quality Gate

当前文件：`src/dochris/quality/quality_gate.py`

当前门禁：

- status 必须是 `compiled`。
- error_message 必须为空。
- summary 必须存在。
- lint 必须通过。
- 概念默认解释 warning 会阻止晋升。
- `quality_score < min_score` 只是 warning，不是硬阻断。

风险：

- README 中质量阈值和实际门禁语义存在差异，需要文档统一。
- 门禁不检查 RAG 可检索性，不检查向量索引是否成功。

## 5. API 层

当前文件：

- `src/dochris/api/app.py`
- `src/dochris/api/auth.py`
- `src/dochris/api/routes/query.py`
- `frontend/src/lib/api.ts`
- `frontend/src/pages/QueryPage.tsx`

当前路由（12 个路由模块，共 22 个 API 端点 + 2 个根路径端点）：

- `/api/v1/query`、`/api/v1/query/stream`（query 模块，2 个端点）
- `/api/v1/status`（status 模块，1 个端点）
- `/api/v1/compile`（compile 模块，1 个端点）
- `/api/v1/promote`（promote 模块，1 个端点）
- `/api/v1/graph`（graph 模块，3 个端点）
- `/api/v1/manifests`（manifests 模块，2 个端点）
- `/api/v1/config`（config 模块，2 个端点）
- `/api/v1/files`（files 模块，1 个端点）
- `/api/v1/quality`（quality 模块，1 个端点）
- `/api/v1/contribution`（contribution 模块，3 个端点）
- `/api/v1/schema`（schema 模块，3 个端点）
- `/api/v1/recompile`（recompile 模块，2 个端点）

认证：

- `DOCHRIS_API_KEY`。
- 未配置时仅允许 localhost / 127.0.0.1 / ::1 / testclient。
- 使用 `hmac.compare_digest`。

流式输出：

- 后端已有 SSE 端点，但使用 `StreamingResponse` 和同步 generator。
- 前端已优先使用 `queryKnowledgeStream()`，失败后 fallback 普通查询（注意：仅服务端返回 404 时触发降级，网络超时等错误直接展示）。
- 目前没有 heartbeat、Last-Event-ID、连接取消感知、标准 `EventSourceResponse`。

Rate limiting：

- 当前无 rate limiting。

## 6. 监控与可观测性

当前能力：

- Python logging。
- workspace logs。
- `time_seconds`。
- benchmark 目录覆盖 query/vector/quality/compilation/parser/indexing 性能。

缺失能力：

- 无 OpenTelemetry trace。
- 无 Prometheus metrics。
- 无 LLM token usage / latency / cost tracking。
- 无检索、rerank、LLM、SSE 的同一 trace_id 串联。
- 无生产失败样本回放机制。

## 7. 第二阶段：资料来源与关键发现

### 7.1 RAG 评估体系资料

| 来源 | 链接 | 关键发现 | 对 DocChris 的用途 |
| --- | --- | --- | --- |
| Ragas Metrics | <https://docs.ragas.io/en/latest/concepts/metrics/> | Ragas 将 RAG 指标拆成 Context Precision、Context Recall、Response Relevancy、Faithfulness、Answer Accuracy、Context Relevance 等。 | 作为第一版自动评估指标来源。 |
| Ragas Available Metrics | <https://docs.ragas.io/en/latest/concepts/metrics/available_metrics/> | 指标覆盖 RAG、Agent、自然语言比较、SQL、通用 rubrics；支持修改或自定义指标。 | DocChris 可先接入核心 RAG 指标，再扩展 citation faithfulness。 |
| LangSmith Evaluate RAG | <https://docs.langchain.com/langsmith/evaluate-rag-tutorial> | 典型 RAG 评估拆成 correctness、groundedness、answer relevance、retrieval relevance。 | 适合设计 DocChris 的评估报告结构和失败归因。 |
| ARES paper | <https://arxiv.org/abs/2311.09476> | 自动化 RAG 评估可用少量人工标注评估多任务 RAG。 | 后续可作为“少量 golden set + LLM judge”路线参考。 |

采用建议：

- 第一版使用 Ragas 指标命名，但通过 adapter 封装，避免业务代码直接依赖 Ragas 数据结构。
- 评估结果按层归因：retrieval 失败、rerank 失败、generation 失败、citation 失败。
- 不把 RAGAS 分数直接当“百分制正确率”，而是作为同一测试集上的趋势指标。

### 7.2 Reranker 重排序资料

| 来源 | 链接 | 关键发现 | 对 DocChris 的用途 |
| --- | --- | --- | --- |
| BGE Reranker 文档 | <https://bge-model.com/bge/bge_reranker.html> | 官方示例建议 embedding 先召回 top 100，再用 BGE reranker 得到最终 top 3。 | DocChris 可采用 `candidate_k` 和 `final_k` 分离。 |
| Pinecone Rerankers and Two-Stage Retrieval | <https://www.pinecone.io/learn/series/rag/rerankers/> | Reranker/cross-encoder 对 query-document pair 打分；两阶段检索用快 retriever 召回、小候选集 rerank。 | 用于解释为什么不能只提高向量 top-k。 |
| Pinecone Rerank Results | <https://docs.pinecone.io/guides/search/rerank-results> | Rerank 根据 query 对候选文档重排，适合提升 RAG 上下文质量。 | API 设计可返回原始分和 rerank 分。 |
| Cohere Rerank 文档 | <https://docs.cohere.com/docs/reranking> | Rerank API 返回 index 和 relevance_score，可取 top_n。 | 可作为云端 reranker provider，但默认不启用。 |

采用建议：

- 默认使用本地 BGE / sentence-transformers provider，保护隐私。
- Cohere 作为可选 provider，必须显式配置 API key。
- Reranker 不替代 retriever；先召回更多候选，再缩小上下文。

### 7.3 可观测性监控资料

| 来源 | 链接 | 关键发现 | 对 DocChris 的用途 |
| --- | --- | --- | --- |
| OpenTelemetry GenAI Semantic Conventions | <https://opentelemetry.io/docs/specs/semconv/gen-ai/> | GenAI span/metric/event 语义约定仍在发展中，但已定义 GenAI operation、provider、request/response 等属性方向。 | DocChris trace 字段应尽量贴近 `gen_ai.*`，同时隔离在 adapter。 |
| OpenTelemetry GenAI spans | <https://opentelemetry.io/docs/specs/semconv/gen-ai/gen-ai-spans/> | LLM span 可记录 provider、input/output messages、token usage 等；需注意数据量与敏感内容。 | 默认只记录 metadata，不记录全文 prompt。 |
| Langfuse SDK Overview | <https://langfuse.com/docs/observability/sdk/overview> | Langfuse SDK 基于 OpenTelemetry，支持 async、latency、嵌套 observations，SDK 错误不应破坏应用。 | 可作为可选 LLM observability exporter。 |
| Phoenix tracing helpers | <https://arize.com/docs/phoenix/tracing/how-to-tracing/setup-tracing/instrument> | Phoenix 使用 OpenInference/OTel trace helpers 追踪函数、链、agent、工具。 | 可作为本地/开源 trace UI 选项。 |
| Prometheus Python client | <https://prometheus.github.io/client_python/instrumenting/> | Prometheus Python client 提供 Counter、Gauge、Histogram、Summary 等指标类型。 | `/metrics` 导出 API latency、LLM latency、token、错误数。 |

采用建议：

- 基础层用 OpenTelemetry + Prometheus，不把 Langfuse/Phoenix 做硬依赖。
- 默认不记录 prompt/context 全文，避免隐私和日志膨胀。
- trace_id 写入 query response，便于前端错误反馈关联后端日志。

### 7.4 流式输出资料

| 来源 | 链接 | 关键发现 | 对 DocChris 的用途 |
| --- | --- | --- | --- |
| OpenAI Streaming Responses | <https://platform.openai.com/docs/guides/streaming-responses> | OpenAI streaming 使用 typed events；常见生命周期包括 created、delta、completed、error。 | DocChris SSE 事件应类型化：meta、retrieval、answer_delta、done、error。 |
| MDN Server-sent events | <https://developer.mozilla.org/en-US/docs/Web/API/Server-sent_events> | SSE 通过服务器向浏览器推送消息，浏览器用 `EventSource` 接收。 | 前端可从 fetch parser 演进到 EventSource 或保留 fetch 以支持自定义 headers。 |
| MDN Using SSE | <https://developer.mozilla.org/en-US/docs/Web/API/Server-sent_events/Using_server-sent_events> | SSE 响应 MIME type 为 `text/event-stream`，事件格式由 `event:`、`data:` 等字段组成。 | 当前 DocChris 格式基本正确，但可补 id/retry/heartbeat。 |
| FastAPI SSE | <https://fastapi.tiangolo.com/tutorial/server-sent-events/> | FastAPI 可用 `EventSourceResponse` 做 SSE。 | 建议从裸 `StreamingResponse` 升级到 `sse-starlette`。 |
| sse-starlette EventSourceResponse | <https://deepwiki.com/sysid/sse-starlette/2.1-eventsourceresponse> | `EventSourceResponse` 是 Starlette/FastAPI SSE 的 ASGI response class。 | 适合 heartbeat、ping、断连处理。 |

采用建议：

- 保留当前 `/query/stream` API 兼容性。
- 内部改成 async generator。
- 事件名改为稳定枚举，并增加 version 字段。

### 7.5 语义分块资料

| 来源 | 链接 | 关键发现 | 对 DocChris 的用途 |
| --- | --- | --- | --- |
| LangChain Text Splitters | <https://docs.langchain.com/oss/python/integrations/splitters/index> | 官方建议多数场景从 RecursiveCharacterTextSplitter 开始，因为它在上下文保持和 chunk size 间平衡较好。 | DocChris 当前结构分块接近 recursive 思路，可保留为默认。 |
| LangChain Recursive Splitter | <https://docs.langchain.com/oss/python/integrations/splitters/recursive_text_splitter> | 默认分隔符 `\n\n`、`\n`、空格、空字符串，尽量保留段落/句子/词。 | 可借鉴 token-aware recursive splitter。 |
| Jina Late Chunking | <https://jina.ai/news/late-chunking-in-long-context-embedding-models/> | Late chunking 先用长上下文模型编码全文，再在 pooling 前 chunk，可改善长文档上下文依赖。 | 适合长文章、课程转录、论文类文档的实验策略。 |
| Late Chunking paper | <https://arxiv.org/abs/2409.04701> | 短 chunk 检索更精确，但传统先切后 embed 会丢失长程上下文；late chunking 在 transformer 后、mean pooling 前切分。 | 作为高级可选策略，不建议第一版默认启用。 |
| Chonkie SemanticChunker | <https://chonkie.mintlify.app/oss/chunkers/semantic-chunker> | 提供 Python semantic chunker，可包含 delimiters。 | 可作为轻量替代，但需评估依赖成熟度。 |

采用建议：

- 第一版保留 DocChris 自研结构分块默认。
- 增加 token-aware recursive 和 embedding semantic 两个策略。
- late chunking 放入实验开关，必须通过 RAG eval 证明收益。

## 8. 第三阶段：完整解决方案

> **⚠️ 前置依赖**：以下三个前置任务必须在正式方案实施前完成。它们解决的是现有代码中的架构性阻碍，避免后续五个方案在各自范围内重复处理同一问题。

### 前置任务 A：统一查询链路 LLM 客户端

**问题**：查询链路（`query_engine.py`）直接使用同步 `openai.OpenAI` 创建客户端（`create_client()` 第 743+ 行），完全独立于编译链路的 `BaseLLMProvider` / `AsyncOpenAI` 抽象层。这导致：

- 同一项目中存在两套独立的 LLM 客户端体系，配置和错误处理不统一。
- `generate_answer()`（第 457-584 行）和 `generate_answer_stream()`（第 587-703 行）有约 54 行几乎完全重复的 context 构建逻辑（拼接 concepts、summaries、vector_results 为 `context_parts`）。
- 后续可观测性、流式输出改造都被绑定在同步路径上。

**迁移方案**：

1. **抽取 `build_answer_context()`**：将 `generate_answer()` 和 `generate_answer_stream()` 中重复的 context 构建逻辑（约 54 行）抽取为独立函数，两个调用方统一调用。函数签名：

```python
@dataclass(frozen=True)
class SourceRef:
    """上下文中的来源引用信息，供 eval、citation、trace 使用。"""

    manifest_id: str | None
    source: str          # 文件路径或标识
    channel: str         # "concept" / "summary" / "vector" / "chunk"
    text_hash: str       # 内容摘要哈希，用于去重和验证
    score: float         # 原始检索分数


def build_answer_context(
    concepts: list[dict],
    summaries: list[dict],
    vector_results: list[dict],
) -> tuple[str, dict[str, SourceRef]]:
    """构建统一上下文字符串和来源索引映射。

    Returns:
        (context_text, source_map) — context_text 为拼接后的上下文，
        source_map 为来源编号（如 "S1"）到 SourceRef 的映射，
        包含 manifest_id/source/channel/text_hash/score，供 RAG eval 引用归因使用。
    """
```

2. **迁移到 `BaseLLMProvider`**：将 `create_client()` 从创建同步 `openai.OpenAI` 改为创建 `OpenAICompatProvider`（内部使用 `AsyncOpenAI`）。`generate_answer()` 和 `generate_answer_stream()` 改为 `async` 函数，通过 `await provider.generate_with_messages()` 调用。

3. **双入口模式**（不能用 `asyncio.run()` 包装——FastAPI 已在运行 event loop，嵌套调用会直接报错）：
   - `query_engine.py` 内部核心实现全部改为 `async def`：`async def _generate_answer_impl(...)`、`async def _generate_answer_stream_impl(...)`。
   - `phase3_query.py` 提供 `async def query_async(...)` 作为主入口，FastAPI 路由 `await query_async(...)`。
   - CLI 同步入口保留 `def query(...)`，内部用 `asyncio.run(query_async(...))` 调用——因为 CLI 不在 event loop 中，此处 `asyncio.run()` 安全。
   - FastAPI 路由永远 `await` 异步版本，不走同步包装。

**涉及文件**：

- `src/dochris/phases/query_engine.py` — 核心改动（create_client、generate_answer、generate_answer_stream）
- `src/dochris/phases/phase3_query.py` — 透传 async 改造
- `src/dochris/api/routes/query.py` — 适配 async query 调用

**预计工作量**：1.5-2 天

**验收标准**：

- `generate_answer()` 和 `generate_answer_stream()` 的 context 构建逻辑不再重复。
- 查询链路通过 `BaseLLMProvider` 调用 LLM，不再直接使用 `openai.OpenAI`。
- 现有查询测试全通过。

### 前置任务 B：统一候选模型 RetrievalCandidate

**问题**：当前 `search_all()` 返回的 concepts、summaries、vector_results 各自使用不同的 dict 结构，没有统一的候选对象模型。Reranker、RAG 评估、可观测性、流式输出、API 层都需要一个统一的证据/候选数据结构。如果不先实现它，后续五个方案会各自定义不兼容的中间类型。

**数据类设计**：

```python
@dataclass
class RetrievalCandidate:
    """统一检索候选。

    所有后续方案（Reranker、Eval、Observability、API）通过此模型访问检索结果，
    不再猜测分数语义。normalized_score 是排序和比较的唯一依据。
    """

    id: str
    text: str
    source: str
    channel: Literal["concept", "summary", "vector", "chunk"]
    retriever: str  # 来源检索器标识，如 "keyword_concept"、"keyword_summary"、"chromadb"、"faiss"
    raw_score: float
    raw_distance: float | None = None
    score_kind: Literal["keyword", "cosine_distance", "l2_distance", "rerank"]  # 分数语义
    normalized_score: float  # 归一化到 0-1，排序和比较的唯一依据
    rank: int | None = None  # 在本通道内的排名，由 retrieve_candidates() 填充
    manifest_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    rerank_score: float | None = None  # 由 Reranker 填充，排序依据
```

**分数归一化策略**：

三种检索通道的原始分数不可直接比较，需要归一化：

| 通道 | 原始分 | 归一化公式 |
|------|--------|------------|
| keyword (concept/summary) | 累加整数（如 5、10、15） | `score / max(all_keyword_scores, 1)` → 0-1 |
| vector (ChromaDB) | cosine distance（如 0.3、0.8） | `1 - min(distance, 1.0)` → 0-1 |
| vector (FAISS) | L2 distance（如 50、200） | `1 / (1 + distance)` → 0-1 |

**去重策略**：同一 `manifest_id` + 同一 `text` 内容 hash 只保留归一化分数最高的候选。

**实现方式**：

- 新增 `src/dochris/rag/schemas.py`，定义 `RetrievalCandidate`。
- 从 `query_engine.py` 的 `search_all()` 中抽取 `retrieve_candidates()` 函数，将 concepts/summaries/vector_results 统一转为 `list[RetrievalCandidate]`。
- `search_all()` 保持原有返回格式不变（向后兼容），`retrieve_candidates()` 作为新入口。

**预计工作量**：0.5-1 天

**验收标准**：

- `RetrievalCandidate` 可表示所有检索通道的结果。
- `retrieve_candidates()` 返回归一化后的统一候选列表。
- 现有 `search_all()` 行为不受影响。

### 前置任务 C：统一 VectorStore 接口

**问题**：`protocols.VectorStore` 和 `vector/base.py:BaseVectorStore` 的接口不一致：

| 差异点 | Protocol (`protocols.py`) | ABC (`vector/base.py`) |
|--------|--------------------------|------------------------|
| 添加方法名 | `add()` | `add_documents()` |
| query 返回类型 | `dict[str, Any]` | `list[dict[str, Any]]` |
| query 额外参数 | 无 | `where: dict` |
| 额外方法 | 无 | `get_collection_count()`, `collection_exists()` |

实际实现（`ChromaDBStore`、`FAISSStore`）都继承 `BaseVectorStore` ABC，因此 Protocol 的 `isinstance` 检查会失败。

**迁移方案**：

- 更新 `protocols.VectorStore` 的方法名和返回类型对齐 `BaseVectorStore` ABC。
- 保持 `BaseVectorStore` 不变（实际实现的基类）。
- 添加注释说明 Protocol 和 ABC 的关系：Protocol 用于鸭子类型检查，ABC 用于继承。

**涉及文件**：

- `src/dochris/protocols.py` — 更新 VectorStore Protocol

**预计工作量**：0.5 天

**验收标准**：

- `isinstance(ChromaDBStore(), VectorStore)` 返回 `True`。
- 现有测试全通过。

## 短板 1：RAG 评估体系

### 现状分析

当前代码位置：

- `src/dochris/phases/query_engine.py`
  - `search_all()`
  - `vector_search()`
  - `generate_answer()`
  - `generate_answer_stream()`
- `src/dochris/phases/phase3_query.py`
  - `query()`
- `src/dochris/core/quality_scorer.py`
  - `score_summary_quality_v4()`
  - `score_summary_quality_v4_report()`
- `src/dochris/quality/quality_gate.py`
  - `quality_gate()`

当前实现方式：

- 查询返回 concepts、summaries、vector_results、answer、time_seconds。
- 质量评分评估 Phase 2 摘要产物。
- quality gate 检查 status、error、summary、lint。
- 没有保存每次查询的上下文快照和评估样本。

存在的问题：

- 无法知道检索召回是否命中正确文档。
- 无法知道 LLM 回答是否完全由上下文支持。
- 无法比较 reranker、chunker、embedding 模型的改动收益。
- 无法在 CI 中防止 RAG 质量回退。

### 行业最佳实践

参考项目 1：Ragas

- 来源：<https://docs.ragas.io/en/latest/concepts/metrics/available_metrics/>
- 实现方式摘要：提供 Context Precision、Context Recall、Response Relevancy、Faithfulness 等 RAG 指标；LLM-based metrics 可用一个或多个 LLM 调用得到分数；支持自定义指标。
- 适配方式：DocChris 不直接暴露 Ragas 原始类型，而是提供 adapter，输入统一的 `RAGEvalSample`。

参考项目 2：LangSmith RAG evaluation

- 来源：<https://docs.langchain.com/langsmith/evaluate-rag-tutorial>
- 实现方式摘要：把 RAG 应用评估拆成 correctness、groundedness、relevance、retrieval relevance。
- 适配方式：DocChris eval report 也按 retrieval / generation / citation 分层。

业界推荐方案：

- 建立 golden query set。
- 每个样本保存 question、expected source ids、optional ground truth。
- 每次 pipeline 改动后跑离线 eval。
- 指标按层归因，不只输出总分。

### 设计方案

新增文件：

- `src/dochris/eval/__init__.py`：评估模块导出。
- `src/dochris/eval/schemas.py`：`RAGEvalSample`、`RAGEvalResult`、`RAGEvalReport`。
- `src/dochris/eval/rag_metrics.py`：本地指标、Ragas adapter、LLM judge adapter。
- `src/dochris/eval/datasets.py`：golden set JSONL 读写、从 manifest 生成候选问题。
- `src/dochris/eval/runner.py`：批量执行 query、收集上下文、计算指标。
- `src/dochris/api/routes/evaluation.py`：评估 API。
- `frontend/src/pages/EvaluationPage.tsx`：评估报告页面。
- `tests/test_eval_rag_metrics.py`：指标单测。
- `tests/test_api/test_evaluation.py`：API 单测。
- `benchmark/test_bench_rag_eval.py`：评估性能基准。

修改文件：

- `src/dochris/phases/query_engine.py`
  - 增加 `collect_context` 参数或新函数 `build_query_context()`。
  - 返回 `contexts`、`source_refs`、`retrieval_scores`。
- `src/dochris/phases/phase3_query.py`
  - `query()` 透传 `collect_context`。
- `src/dochris/api/app.py`
  - 挂载 evaluation router。
- `src/dochris/api/schemas.py`
  - 增加评估响应 schema。
- `src/dochris/cli/main.py`
  - 增加 `kb eval rag --dataset ... --out ...`。
- `mkdocs.yml`
  - 增加评估文档入口。

接口设计：

```python
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal


@dataclass(frozen=True)
class RAGEvalSample:
    """RAG 评估样本。"""

    id: str
    question: str
    expected_source_ids: list[str] = field(default_factory=list)
    ground_truth: str | None = None
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class QueryEvidence:
    """一次查询实际使用的证据。"""

    text: str
    source: str
    manifest_id: str | None
    score: float
    rank: int
    channel: Literal["keyword", "vector", "rerank", "rewritten"]
    original_query: str | None = None  # 记录 pre_query hook 改写前的原始 query


@dataclass(frozen=True)
class RAGEvalResult:
    """单条样本评估结果。"""

    sample_id: str
    answer: str
    evidence: list[QueryEvidence]
    metrics: dict[str, float]
    failures: list[str] = field(default_factory=list)


class RAGEvaluator:
    """RAG 评估执行器。"""

    def __init__(self, workspace: Path, judge_model: str | None = None) -> None:
        self.workspace = workspace
        self.judge_model = judge_model

    async def evaluate_sample(self, sample: RAGEvalSample) -> RAGEvalResult:
        """执行一次查询并计算检索、生成、引用指标。"""
        ...

    async def evaluate_dataset(self, samples: list[RAGEvalSample]) -> dict[str, Any]:
        """批量评估并输出汇总报告。"""
        ...
```

数据流：

```text
golden_questions.jsonl
  |
  v
RAGEvalRunner
  |
  +--> phase3_query.query(collect_context=True)
  |       |
  |       +--> concepts / summaries / vector_results / answer / contexts
  |
  +--> retrieval metrics
  |       - recall@k
  |       - precision@k
  |       - mrr
  |       - ndcg
  |
  +--> generation metrics
          - faithfulness
          - answer relevancy
          - context relevancy
          - citation coverage
  |
  v
reports/rag-eval-YYYYMMDD.json
reports/rag-eval-YYYYMMDD.md
```

配置项：

- 环境变量：
  - `RAG_EVAL_ENABLED=false`
  - `RAG_EVAL_PROVIDER=local|ragas`
  - `RAG_EVAL_MODEL=glm-4-flash`
  - `RAG_EVAL_DATASET=eval/rag_golden.jsonl`
  - `RAG_EVAL_MIN_FAITHFULNESS=0.80`
  - `RAG_EVAL_MIN_CONTEXT_RECALL=0.75`
- Settings 字段：
  - `rag_eval_enabled: bool`
  - `rag_eval_provider: str`
  - `rag_eval_model: str`
  - `rag_eval_dataset: Path`
- CLI：
  - `kb eval rag --dataset eval/rag_golden.jsonl --out reports/`
  - `kb eval generate --count 50 --from compiled`

与现有代码的集成点：

- `query_engine.py`
  - 在 `generate_answer()` 前把 concepts、summaries、vector_results 转为统一 `QueryEvidence`。
  - 把 `context_parts` 构建逻辑抽到 `build_answer_context()`，供 eval 复用。
- `compiler_worker.py`
  - 在 `post_compile` 后可选生成候选 QA 样本，不默认启用。
  - 注意：`post_compile` hook 返回 None，候选 QA 样本生成应通过 `RAGEvaluator` 直接从 manifest/outputs 目录读取，不依赖 hook 返回值。
- `api/routes/query.py`
  - 响应中可选返回 `trace_id` 和 `evidence_ids`。
- `types.py`
  - `QueryResult` dataclass 需新增 `contexts`、`source_refs`、`retrieval_scores` 字段（或新建 `QueryResultWithEvidence`），需考虑向后兼容——新字段应有默认值。
- `RAGEvaluator`
  - `judge_model` 应走异步 `BaseLLMProvider` 路径，与编译链路一致（依赖前置任务 A 完成）。
- Web UI
  - 新增”评估”页面，展示趋势、失败样本、指标分布。

测试策略：

- 单元测试：
  - `recall@k`、`precision@k`、`mrr`、`ndcg` 固定输入输出。
  - 无 ground truth 时跳过对应指标。
  - LLM judge mock 输出异常时降级。
- 集成测试：
  - 临时 workspace + 3 个 manifest + 5 条 golden query。
  - 验证 report JSON 和 Markdown 生成。
- 基准测试：
  - 10 / 100 / 1000 样本评估开销。
  - Ragas provider 和 local metric provider 对比。

预计工作量：

- 新增代码行数：约 800 行。
- 修改代码行数：约 250 行。
- 新增依赖：可选 `ragas>=0.3`、`datasets>=2.0`。
- 预计开发时间：4-5 天。

## 短板 2：Reranker 重排序

### 现状分析

当前代码位置：

- `src/dochris/phases/query_engine.py`
  - `search_all()`
  - `vector_search()`
  - `_vector_search_with_store()`
- `src/dochris/plugin/hookspec.py`
  - `post_query()`

当前实现方式：

- 关键词搜索返回整数累加分。
- 向量搜索返回 distance，API 层再归一化。
- `search_all()` 简单合并 concepts、summaries、vector_results。
- 没有统一候选模型，也没有 rerank score。

存在的问题：

- first-stage retrieval 和 final context selection 没分离。
- `top_k=5` 同时限制召回和最终上下文，容易漏掉真正相关 chunk。
- 关键词、summary、concept、vector 的 score 不可直接比较。
- 没有 query-document pair 级别的精排序。

### 行业最佳实践

参考项目 1：BGE Reranker

- 来源：<https://bge-model.com/bge/bge_reranker.html>
- 实现方式摘要：先用 embedding 模型取 top 100，再用 BGE reranker 得到 final top 3。
- DocChris 采用点：增加 `candidate_k` 和 `final_k`。

参考项目 2：Pinecone two-stage retrieval

- 来源：<https://www.pinecone.io/learn/series/rag/rerankers/>
- 实现方式摘要：bi-encoder / vector DB 快速召回，cross-encoder reranker 对 query-document pair 打分并重排。
- DocChris 采用点：把 reranker 放在 retrieval 和 LLM context 之间。

参考项目 3：Cohere Rerank

- 来源：<https://docs.cohere.com/docs/reranking>
- 实现方式摘要：输入 query 和 documents，返回 index 与 relevance_score。
- DocChris 采用点：定义 provider 抽象，支持云端 reranker 但默认关闭。

业界推荐方案：

- `candidate_k` 取 30-100。
- `final_k` 取 3-8。
- rerank 分数作为排序依据，不直接当“事实可信度”。
- 对 reranker 结果做延迟预算和缓存。

### 设计方案

新增文件：

- `src/dochris/rag/__init__.py`
- `src/dochris/rag/schemas.py`
- `src/dochris/rag/reranker/__init__.py`
- `src/dochris/rag/reranker/base.py`
- `src/dochris/rag/reranker/bge.py`
- `src/dochris/rag/reranker/sentence_transformers.py`
- `src/dochris/rag/reranker/cohere.py`
- `src/dochris/rag/reranker/factory.py`
- `tests/test_reranker.py`
- `benchmark/test_bench_reranker.py`

修改文件：

- `src/dochris/phases/query_engine.py`
  - 增加 `retrieve_candidates()`。
  - `search_all()` 增加 `candidate_k`、`rerank_enabled`。
  - `generate_answer()` 接收 reranked evidence。
- `src/dochris/api/routes/query.py`
  - 增加 query 参数 `rerank`、`candidate_k`。
- `src/dochris/api/schemas.py`
  - `SearchResult` 增加 `raw_score`、`rerank_score`、`rank_source`。
- `src/dochris/settings/config.py`
  - 增加 reranker 配置。
- `frontend/src/pages/QueryPage.tsx`
  - 展示 rerank score 和排序来源。

接口设计：

```python
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Literal


@dataclass
class RetrievalCandidate:
    """统一检索候选。"""

    id: str
    text: str
    source: str
    channel: Literal["concept", "summary", "vector", "chunk"]
    raw_score: float
    raw_distance: float | None = None
    manifest_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    rerank_score: float | None = None


class BaseReranker(ABC):
    """Reranker 抽象基类。"""

    name: str = "base"

    @abstractmethod
    def rerank(
        self,
        query: str,
        candidates: list[RetrievalCandidate],
        top_k: int,
    ) -> list[RetrievalCandidate]:
        """按 query-candidate 相关性重排候选。"""
        ...


class BGEReranker(BaseReranker):
    """基于 FlagEmbedding 的 BGE Reranker。"""

    name = "bge"

    def __init__(self, model_name: str, use_fp16: bool = True) -> None:
        ...

    def rerank(
        self,
        query: str,
        candidates: list[RetrievalCandidate],
        top_k: int,
    ) -> list[RetrievalCandidate]:
        ...
```

数据流：

```text
用户 query
  |
  v
关键词检索 + 向量检索
  |
  v
RetrievalCandidate[]  candidate_k=50
  |
  v
score normalize + dedupe
  |
  v
Reranker(query, candidates)
  |
  v
top final_k evidence
  |
  v
generate_answer()
```

配置项：

- 环境变量：
  - `RERANKER_ENABLED=false`
  - `RERANKER_PROVIDER=bge`
  - `RERANKER_MODEL=BAAI/bge-reranker-base`
  - `RERANKER_CANDIDATE_K=50`
  - `RERANKER_TOP_K=5`
  - `RERANKER_MAX_LENGTH=512`
  - `RERANKER_CACHE_TTL_SECONDS=3600`
- CLI：
  - `kb query "..." --rerank --candidate-k 50 --top-k 5`

与现有代码的集成点：

- `query_engine.py`
  - 在 `search_all()` 中，先扩大召回，再调用 `rerank_candidates()`。
  - 在 `generate_answer()` 前只传入 reranked top-k。
  - ChromaDB 旧路径（直接 chromadb client）和抽象层路径（BaseVectorStore）的输出格式差异需在 `retrieve_candidates()` 中统一处理（前置任务 B 已提供统一转换）。
  - 分数归一化策略：keyword score 按累加整数 / max_score 归一化到 0-1；vector distance 用 `1 - min(distance, 1.0)` 转换；去重策略为同一 `manifest_id` + 同一 text hash 保留最高分。
- `compiler_worker.py`
  - 不直接触发 rerank，但后续原文 chunk indexing 会影响候选质量。
  - `_embed_to_vector_store()` 目前只索引 summaries 和 concepts 两个 collection，后续 raw chunk indexing（短板 5）会新增 chunks collection，reranker 需要搜索三个 collection 的结果并统一排序。
- `api/routes/query.py`
  - `/query` 和 `/query/stream` 都支持 `rerank=true`。
  - `SearchResult` 需增加 `raw_score`、`rerank_score`、`rank_source` 字段（API 契约变更，新字段应有默认值以保持向后兼容）。
- Web UI
  - Query 页向量检索 Tab 增加”原始分 / rerank 分 / 来源 channel”。

测试策略：

- 单元测试：
  - mock reranker 结果排序。
  - 候选去重：同一 manifest / 同一 text hash 只保留最佳。
  - reranker disabled 时保持旧行为。
- 集成测试：
  - 临时知识库中验证 rerank 后 context 顺序改变。
- 基准测试：
  - candidate_k=10/50/100 延迟。
  - CPU/MPS/GPU 可用性检测。
- RAG 质量测试：
  - 使用第 1 个方案的 eval runner 对比 `rerank=false/true`。

预计工作量：

- 新增代码行数：约 600 行。
- 修改代码行数：约 220 行。
- 新增依赖：可选 `FlagEmbedding>=1.3.0`；复用现有 `sentence-transformers`。
- 预计开发时间：3-4 天。

## 短板 3：可观测性监控

### 现状分析

当前代码位置：

- `src/dochris/core/summary_generator.py`
- `src/dochris/core/hierarchical_summarizer.py`
- `src/dochris/phases/query_engine.py`
- `src/dochris/api/routes/query.py`
- `benchmark/`

当前实现方式：

- 使用标准 logging。
- 查询返回 `time_seconds`。
- benchmark 覆盖性能，但不输出生产指标。

存在的问题：

- 无 trace_id 串联 API、retrieval、rerank、LLM。
- 无 token usage、cost、latency histogram。
- 出现错误回答时，无法快速判断是检索失败、rerank 失败还是 LLM 生成失败。
- 无 `/metrics`。

### 行业最佳实践

参考项目 1：OpenTelemetry GenAI Semantic Conventions

- 来源：<https://opentelemetry.io/docs/specs/semconv/gen-ai/>
- 实现方式摘要：定义 GenAI 操作的 span、metric、event 语义，包括 provider、operation、request、response 等属性。
- DocChris 采用点：内部 span 属性尽量使用 `gen_ai.*`，但通过 wrapper 隔离规范变化。

参考项目 2：Langfuse

- 来源：<https://langfuse.com/docs/observability/sdk/overview>
- 实现方式摘要：基于 OpenTelemetry，支持嵌套 observations、latency、prompt/eval 功能，SDK 错误不应破坏应用。
- DocChris 采用点：作为可选 exporter，不做硬依赖。

参考项目 3：Phoenix

- 来源：<https://arize.com/docs/phoenix/tracing/how-to-tracing/setup-tracing/instrument>
- 实现方式摘要：OpenInference/OTel helpers 追踪函数、chain、agent、tool。
- DocChris 采用点：适合本地观察 retrieval -> rerank -> generation。

参考项目 4：Prometheus Python client

- 来源：<https://prometheus.github.io/client_python/instrumenting/>
- 实现方式摘要：Counter、Gauge、Histogram、Summary 适合应用指标。
- DocChris 采用点：提供 `/metrics` 给 Docker/Grafana。

### 设计方案

新增文件：

- `src/dochris/observability/__init__.py`
- `src/dochris/observability/tracing.py`
- `src/dochris/observability/metrics.py`
- `src/dochris/observability/cost.py`
- `src/dochris/observability/middleware.py`
- `src/dochris/api/routes/metrics.py`
- `tests/test_observability_metrics.py`
- `tests/test_observability_tracing.py`

修改文件：

- `src/dochris/api/app.py`
  - 加 request middleware。
  - 挂载 `/metrics`。
- `src/dochris/core/summary_generator.py`
  - LLM 调用包 span。
- `src/dochris/core/hierarchical_summarizer.py`
  - chunk summarize、merge 包 span。
- `src/dochris/phases/query_engine.py`
  - retrieval、rerank、generate 包 span。
- `src/dochris/llm/openai_compat.py`
  - 捕获 usage、model、latency。

接口设计：

```python
from __future__ import annotations

from contextlib import AbstractContextManager
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class LLMUsage:
    """LLM 调用用量。"""

    provider: str
    model: str
    operation: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    latency_ms: float = 0.0
    cost_usd: float | None = None
    error_type: str | None = None


@dataclass(frozen=True)
class SpanContext:
    """Span 上下文信息。"""

    span_id: str
    trace_id: str


class CostEstimator:
    """LLM 调用成本估算接口。"""

    def estimate(self, provider: str, model: str, prompt_tokens: int, completion_tokens: int) -> float | None:
        """根据 provider/model 和 token 用量估算 USD 成本。定价数据通过配置文件维护。"""
        ...


class ObservabilityManager:
    """统一观测入口。"""

    def span(self, name: str, **attrs: Any) -> AbstractContextManager[SpanContext]:
        """创建 trace span，返回包含 span_id 和 trace_id 的上下文。"""
        ...

    def record_llm_usage(self, usage: LLMUsage) -> None:
        """记录 LLM token、延迟、成本。"""
        ...

    def record_retrieval(
        self,
        query: str,
        candidate_count: int,
        latency_ms: float,
        collection_name: str | None = None,
        retriever_type: str | None = None,
    ) -> None:
        """记录检索指标。collection_name 和 retriever_type 用于分析检索瓶颈。"""
        ...
```

数据流：

```text
HTTP request / CLI command
  |
  v
trace_id created
  |
  +--> retrieval span
  +--> vector store span
  +--> reranker span
  +--> llm generation span
  +--> cache span
  |
  v
Prometheus metrics + optional OTLP export
  |
  v
Grafana / Phoenix / Langfuse
```

配置项：

- 环境变量：
  - `OBSERVABILITY_ENABLED=true`
  - `PROMETHEUS_ENABLED=true`
  - `OTEL_EXPORTER_OTLP_ENDPOINT=`
  - `OTEL_SERVICE_NAME=dochris`
  - `LANGFUSE_PUBLIC_KEY=`
  - `LANGFUSE_SECRET_KEY=`
  - `PHOENIX_ENDPOINT=`
  - `OBSERVABILITY_CAPTURE_CONTENT=false`
- Settings 字段：
  - `observability_enabled: bool`
  - `prometheus_enabled: bool`
  - `otel_exporter_otlp_endpoint: str`
  - `observability_capture_content: bool`

与现有代码的集成点：

- **LLM usage 统一记录**（前置任务 A 完成后）：
  - 查询链路和编译链路都通过 `BaseLLMProvider` 调用 LLM，`LLMUsage`（token/latency/cost）统一在 Provider wrapper 层记录，**不需要**在 `query_engine.py` 中手动埋 LLM 调用指标。
  - `llm/openai_compat.py` 的 `generate_with_messages()` 内部记录 usage、model、latency，编译和查询链路自动受益。
- `query_engine.py`（只记录检索侧指标）：
  - `vector_search()` 记录 candidate count、collection count、latency。
  - `build_answer_context()` 记录 context token 数、source count。
  - `generate_answer()` / `generate_answer_stream()` 记录 cache hit/miss。
- `compiler_worker.py`
  - `compile_document()` 作为 parent span。
  - `_extract_text()`、`_generate_with_fallback()`、`_embed_to_vector_store()` 作为 child spans。
- `api/routes/query.py`
  - response 增加 `trace_id`。
- `api/app.py`
  - middleware 执行顺序应为 **CORS → tracing → auth → route handler**，确保 trace_id 覆盖认证失败场景。
- `api/auth.py`
  - `verify_api_key` 需被 trace 覆盖，用于统计认证失败率。
- Docker 多 worker 场景
  - 需使用 `prometheus_client.multiprocess` 模式，建议在 `docker-compose.yml` 中配置 `PROMETHEUS_MULTIPROC_DIR` 环境变量。
- Web UI
  - 可在错误提示中显示 trace_id。
  - 后续新增”监控”页面。

测试策略：

- 单元测试：
  - metrics registry 不重复注册。
  - usage cost 计算。
  - disabled 时无副作用。
- 集成测试：
  - `/metrics` 返回 Prometheus 文本。
  - query 后指标计数递增。
- 基准测试：
  - observability enabled/disabled 延迟差异。
- 安全测试：
  - 默认不记录 prompt/context 全文。

预计工作量：

- 新增代码行数：约 900 行。
- 修改代码行数：约 300 行。
- 新增依赖：`opentelemetry-api>=1.25`、`opentelemetry-sdk>=1.25`、`prometheus-client>=0.20`；可选 `langfuse`、`arize-phoenix-otel`。
- 预计开发时间：4-5 天。

## 短板 4：流式输出工程化

### 现状分析

当前代码位置：

- `src/dochris/api/routes/query.py`
  - `query_stream()`
- `src/dochris/phases/query_engine.py`
  - `generate_answer_stream()`
- `frontend/src/lib/api.ts`
  - `queryKnowledgeStream()`
- `frontend/src/pages/QueryPage.tsx`

当前实现方式：

- 后端 `StreamingResponse` 返回 SSE 格式字符串。
- 先返回 meta，再返回 keyword results，再做向量检索，最后流式回答。
- 向量检索用 `ThreadPoolExecutor` 加 10 秒 timeout。
- 前端通过 `fetch()` 读取 `ReadableStream` 并解析 `event:` / `data:`。

存在的问题：

- 不是 async-first，长连接和阻塞操作边界不清晰。
- 无 heartbeat/ping，代理或浏览器可能认为连接空闲。
- 无 request disconnect 检测，用户关闭页面后后端可能继续生成。
- 事件 schema 没版本。
- 前端 Markdown 渲染只是 `pre-wrap`，引用和 Markdown 增量解析能力有限。

### 行业最佳实践

参考项目 1：OpenAI Streaming Responses

- 来源：<https://platform.openai.com/docs/guides/streaming-responses>
- 实现方式摘要：streaming 使用 typed events；delta、completed、error 等生命周期分明。
- DocChris 采用点：事件枚举稳定化。

参考项目 2：MDN Server-sent events

- 来源：<https://developer.mozilla.org/en-US/docs/Web/API/Server-sent_events/Using_server-sent_events>
- 实现方式摘要：SSE 使用 `text/event-stream`，客户端用 EventSource 接收事件；事件由 `event:`、`data:`、空行分隔。
- DocChris 采用点：补 `id`、`retry`、heartbeat。

参考项目 3：FastAPI / sse-starlette

- 来源：<https://fastapi.tiangolo.com/tutorial/server-sent-events/>
- 来源：<https://deepwiki.com/sysid/sse-starlette/2.1-eventsourceresponse>
- 实现方式摘要：`EventSourceResponse` 是 FastAPI/Starlette SSE 常用 ASGI response class。
- DocChris 采用点：替换裸 `StreamingResponse`。

### 设计方案

新增文件：

- `src/dochris/api/sse.py`：SSE event 编码、schema、heartbeat。
- `src/dochris/phases/query_stream.py`：async query stream orchestration。
- `frontend/src/lib/sse.ts`：统一 SSE parser。
- `frontend/src/components/StreamingMarkdown.tsx`：流式 Markdown + wiki-link 渲染。
- `tests/test_api/test_query_stream.py`：后端 SSE 测试。
- `frontend/src/lib/sse.test.ts`：前端 parser 测试。

修改文件：

- `src/dochris/api/routes/query.py`
  - `query_stream()` 调用 `stream_query_events()`。
- `src/dochris/phases/query_engine.py`
  - `generate_answer_stream()` 与 non-stream 共用 context builder。
- `frontend/src/pages/QueryPage.tsx`
  - 使用 `StreamingMarkdown`。
  - 展示阶段状态：检索中、重排中、生成中。

接口设计：

```python
from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any, Literal


class QueryStreamEventName(StrEnum):
    """查询流式事件名（使用 StrEnum，与项目 types.py 中 FileStatus/FileType 惯例一致）。"""

    META = "meta"
    RETRIEVAL = "retrieval"
    RERANK = "rerank"
    ANSWER_DELTA = "answer_delta"
    DONE = "done"
    ERROR = "error"
    PING = "ping"


@dataclass(frozen=True)
class QueryStreamEvent:
    """查询流式事件。"""

    event: QueryStreamEventName
    data: dict[str, Any] | str
    id: str | None = None
    retry: int | None = None


async def stream_query_events(
    query: str,
    mode: str,
    top_k: int,
    rerank: bool = False,
) -> AsyncIterator[QueryStreamEvent]:
    """按阶段流式输出查询事件。"""
    ...
```

数据流：

```text
frontend QueryPage
  |
  v
GET /api/v1/query/stream
  |
  v
meta event
  |
  v
retrieval event: keyword results
  |
  v
retrieval event: vector results
  |
  v
rerank event: reranked results
  |
  v
answer_delta events
  |
  v
done event
```

配置项：

- 环境变量：
  - `SSE_ENABLED=true`
  - `SSE_PING_SECONDS=15`
  - `SSE_VECTOR_TIMEOUT_SECONDS=10`
  - `SSE_MAX_CONNECTIONS=20`
  - `SSE_EVENT_VERSION=1`
- CLI：
  - 暂不需要。

与现有代码的集成点：

- `query_engine.py`
  - 抽出 `build_answer_context()`。
  - `generate_answer_stream()` 只负责 LLM chunk，不负责检索 orchestration。
  - **前置条件**：必须先完成 `build_answer_context()` 抽取（前置任务 A），否则流式改造复杂度倍增。
  - **同步→异步迁移**：当前 `ThreadPoolExecutor(max_workers=1)` 包装同步 `vector_search()`，迁移到 async generator 后需用 `asyncio.to_thread()` 替代，或在前置任务 A 中将 `vector_search()` 异步化。
  - **缓存命中处理**：`generate_answer_stream()` 中缓存命中（第 638-644 行）应作为 `done` 事件返回，而非 `answer_delta`，保持前端渲染逻辑一致。
- `api/routes/query.py`
  - 替换 `_generate()` 内联函数。
- Web UI
  - Query 页 Answer Tab 使用流式 Markdown。
  - 状态栏显示当前阶段和耗时。

测试策略：

- 单元测试：
  - SSE event encode/decode。
  - error event schema。
  - heartbeat 事件。
- 集成测试：
  - TestClient stream 消费事件顺序。
  - vector timeout 后仍能继续 answer。
  - LLM 不可用时返回 error/done。
- 前端测试：
  - chunk 被拆分在多行时 parser 正确。
  - Markdown 增量更新不丢内容。
- 手动 smoke：
  - 大问题流式回答。
  - 用户刷新页面后后端取消。

预计工作量：

- 新增代码行数：约 500 行。
- 修改代码行数：约 250 行。
- 新增依赖：可选 `sse-starlette>=2.1`、前端可选 `react-markdown`。
- 预计开发时间：2-3 天。

## 短板 5：语义分块策略优化

### 现状分析

当前代码位置：

- `src/dochris/core/text_chunker.py`
  - `structure_aware_split()`
  - `semantic_chunk()`
  - `fixed_size_chunk()`
- `src/dochris/core/summary_generator.py`
  - `generate_summary_smart()`
- `src/dochris/core/hierarchical_summarizer.py`
  - `generate_map_reduce_summary()`
  - `generate_hierarchical_summary()`
- `src/dochris/workers/compiler_worker.py`
  - `_embed_to_vector_store()`

当前实现方式：

- 用规则式 chunker 处理长文本摘要。
- 向量库主要索引摘要和概念。
- `summary_text` 截取 detailed_summary 前 2000 字。

存在的问题：

- 无原文 chunk 检索，回答证据只能来自摘要/概念/已有向量集合。
- chunk strategy 无法按文档类型选择。
- 无 token-aware chunking。
- 无 semantic breakpoint。
- 长文档里跨段指代、表格上下文、章节上下文容易丢失。

### 行业最佳实践

参考项目 1：LangChain RecursiveCharacterTextSplitter

- 来源：<https://docs.langchain.com/oss/python/integrations/splitters/recursive_text_splitter>
- 实现方式摘要：按 `\n\n`、`\n`、空格、空字符串逐级切分，尽量保留段落、句子和词。
- DocChris 采用点：保留结构优先的默认策略，并增加 token-aware recursive 版本。

参考项目 2：Jina Late Chunking

- 来源：<https://jina.ai/news/late-chunking-in-long-context-embedding-models/>
- 来源：<https://arxiv.org/abs/2409.04701>
- 实现方式摘要：先用长上下文 embedding 模型编码全文，再在 mean pooling 前按 chunk pooling 得到上下文感知 chunk embedding。
- DocChris 采用点：作为实验策略，针对长文档建立 benchmark。

参考项目 3：Chonkie SemanticChunker

- 来源：<https://chonkie.mintlify.app/oss/chunkers/semantic-chunker>
- 实现方式摘要：提供 Python semantic chunker，可保留 delimiters。
- DocChris 采用点：参考 API 形态，但不第一版硬依赖。

### 设计方案

新增文件：

- `src/dochris/rag/chunking/__init__.py`
- `src/dochris/rag/chunking/base.py`
- `src/dochris/rag/chunking/structure.py`
- `src/dochris/rag/chunking/recursive.py`
- `src/dochris/rag/chunking/semantic.py`
- `src/dochris/rag/chunking/late.py`
- `src/dochris/rag/chunking/factory.py`
- `src/dochris/rag/indexer.py`
- `tests/test_rag_chunking.py`
- `benchmark/test_bench_chunking_strategies.py`

修改文件：

- `src/dochris/core/text_chunker.py`
  - 保留现有函数作为兼容 wrapper。
- `src/dochris/workers/compiler_worker.py`
  - `_embed_to_vector_store()` 增加 raw chunk indexing。
- `src/dochris/phases/query_engine.py`
  - `vector_search()` 搜索 `chunks` collection。
- `src/dochris/vector/base.py`
  - 明确 embedding model metadata。
- `src/dochris/settings/config.py`
  - 增加 chunking 配置。

接口设计：

```python
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Literal


@dataclass
class ChunkMetadata:
    """文本块元数据。

    输入字段（调用方传入）：src_id, title, section, strategy, extra
    输出字段（split() 填充）：start_char, end_char
    """

    src_id: str           # 输入：来源 manifest ID（如 SRC-0001）
    title: str            # 输入：文档标题
    section: str = ""     # 输入：所属章节
    start_char: int = 0   # 输出：chunk 在原文中的起始字符位置
    end_char: int = 0     # 输出：chunk 在原文中的结束字符位置
    strategy: str = "structure"  # 输入：分块策略名称
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class DocumentChunk:
    """用于检索索引的文档块。"""

    id: str
    content: str
    metadata: ChunkMetadata


class BaseChunker(ABC):
    """文档分块策略抽象。"""

    name: str = "base"

    @abstractmethod
    def split(self, text: str, metadata: ChunkMetadata) -> list[DocumentChunk]:
        """将文档文本切为可索引 chunk。"""
        ...


class SemanticChunker(BaseChunker):
    """基于 embedding 相邻距离断点的语义分块器。

    注意：应复用已有 embedding function（如 ChromaDB store 内部加载的），
    避免重复加载模型浪费内存。
    """

    name = "semantic"

    def __init__(self, embedding_model: str, breakpoint_percentile: float = 95.0) -> None:
        ...
```

数据流：

```text
CompilerWorker._extract_text()
  |
  v
ChunkerFactory.create(settings.chunk_strategy)
  |
  v
DocumentChunk[]
  |
  +--> summaries/concepts 正常生成
  |
  +--> chunks collection 向量索引
          - id: SRC-0001_chunk_0001
          - source: SRC-0001
          - title
          - section
          - start_char / end_char
          - strategy
  |
  v
query_engine.vector_search()
  |
  v
chunk evidence -> reranker -> answer
```

配置项：

- 环境变量：
  - `CHUNK_STRATEGY=structure`
  - `INDEX_RAW_CHUNKS=false`
  - `CHUNK_SIZE_TOKENS=800`
  - `CHUNK_OVERLAP_TOKENS=120`
  - `CHUNK_SIZE_CHARS=4000`
  - `CHUNK_OVERLAP_CHARS=200`
  - `SEMANTIC_BREAKPOINT_PERCENTILE=95`
  - `LATE_CHUNKING_ENABLED=false`
  - `LATE_CHUNKING_MODEL=jinaai/jina-embeddings-v2-base-zh`
- CLI：
  - `kb compile --chunk-strategy semantic --index-raw-chunks`
  - `kb index chunks --strategy recursive`

与现有代码的集成点：

- `compiler_worker.py`
  - `_extract_text()` 后保留原文 text。
  - `_embed_to_vector_store()` 对 raw chunks 建 `chunks` collection。
  - **编译缓存版本**：缓存 key 需区分是否启用 chunk indexing，建议在 cache hash 中加入 `chunk_strategy` + `index_raw_chunks` 参数，避免旧缓存导致 chunk 缺失。
  - **store 实例复用**：`_embed_to_vector_store()` 每次调用都 `store_cls(persist_directory=...)` 创建新实例，对大文档（数百 chunk）有性能问题，建议将 store 实例提升为 `CompilerWorker` 属性。
- `query_engine.py`
  - `vector_search()` 默认搜索 `summaries`、`concepts`、`chunks`。
  - `generate_answer()` context 中标注 section 和 chunk id。
- `api/routes/query.py`
  - `SearchResult` 增加 `section`、`chunk_id`（新字段应有默认值以保持向后兼容）。
- `promote.py`
  - 晋升时需考虑 `chunks` collection 的 metadata 更新（如 trust level 从 `outputs` → `wiki`），避免已晋升文档的 chunk 仍标记为低信任层。
- `vector/chromadb_store.py`
  - `SemanticChunker` 应复用已有的 embedding function（chromadb_store 内部加载的），避免重复加载模型浪费内存。
- Web UI
  - “相关文档”Tab 展示 chunk 所在章节。
  - “向量检索”Tab 支持按 source/section 过滤。

测试策略：

- 单元测试：
  - Markdown 标题、中文编号、长段落、代码块、表格的 chunk 边界。
  - chunk metadata start/end 正确。
  - strategy disabled 时不索引 raw chunks。
- 集成测试：
  - 编译一个长文档后产生 `chunks` collection。
  - 查询能返回 chunk evidence。
- 基准测试：
  - structure vs recursive vs semantic 的 chunk 数、索引耗时、查询耗时。
  - RAG eval 对比不同策略的 Recall@k 和 Faithfulness。

预计工作量：

- 新增代码行数：约 750 行。
- 修改代码行数：约 280 行。
- 新增依赖：可选 `langchain-text-splitters>=0.3`、`tiktoken>=0.7`；semantic 版复用 `sentence-transformers`。
- 预计开发时间：4-5 天。

## 9. 横向架构约束

### 9.1 不破坏现有架构

所有功能必须满足：

- 默认关闭或保持旧行为。
- 新增功能通过 Settings、CLI 参数或插件显式启用。
- Provider / VectorStore / Plugin 抽象不被绕过。
- 查询 API 保持向后兼容。

### 9.2 配置命名建议

建议新增配置集中在 Settings，按功能分组并使用前缀区分：

```python
# --- RAG 评估 ---
rag_eval_enabled: bool = False
rag_eval_provider: str = "local"
rag_eval_model: str = "glm-4-flash"
rag_eval_dataset: Path = Path("eval/rag_golden.jsonl")

# --- Reranker ---
reranker_enabled: bool = False
reranker_provider: str = "bge"
reranker_model: str = "BAAI/bge-reranker-base"
reranker_candidate_k: int = 50
reranker_top_k: int = 5

# --- 可观测性 ---
observability_enabled: bool = False
prometheus_enabled: bool = False
otel_exporter_otlp_endpoint: str = ""

# --- SSE 流式 ---
sse_ping_seconds: int = 15
sse_max_connections: int = 20

# --- 语义分块 ---
chunk_strategy: str = "structure"
index_raw_chunks: bool = False
chunk_size_tokens: int = 800
chunk_overlap_tokens: int = 120
```

**配置映射优化**：

当前 `Settings.from_env()` 中约 15 个字段需要手动映射环境变量。新增 20+ 个配置项后，维护成本将显著上升。建议在第 0 周 Day 0d 实现 typed env helper：

```python
# 第 0 周 Day 0d 实现
_env_mapping: ClassVar[dict[str, tuple[str, Any, Callable | None]]] = {
    "reranker_enabled": ("RERANKER_ENABLED", False, None),
    "reranker_provider": ("RERANKER_PROVIDER", "bge", None),
    "chunk_size_tokens": ("CHUNK_SIZE_TOKENS", 800, int),
    ...
}
```

这样 `from_env()` 只需遍历 `_env_mapping` 自动读取环境变量，后续方案新增配置只需加一行映射，不再手写 `os.environ.get()` 调用。

### 9.3 统一候选与证据模型

Reranker、评估、引用、可观测性都需要一个统一证据模型。建议优先实现 `RetrievalCandidate` / `QueryEvidence`，否则后续功能会重复做字段转换。

```text
SearchResult API schema
  ^
  |
QueryEvidence
  ^
  |
RetrievalCandidate
  ^
  |
keyword / vector / chunk retrievers
```

## 10. 实施路线图

> **总时间**：3.5-4 周（含前置任务）。前置任务解决架构性阻碍，确保后续方案不重复处理同一问题。

### 第 0 周：前置任务（2-3 天）

Day 0a（0.5-1 天）：

- 新增 `src/dochris/rag/schemas.py`，定义 `RetrievalCandidate` 数据类。
- 从 `query_engine.py` 的 `search_all()` 中抽取 `retrieve_candidates()` 函数。
- 实现分数归一化策略（keyword / vector distance 归一化到 0-1）。
- 实现去重策略（同一 manifest_id + text hash 保留最高分）。
- 现有 `search_all()` 行为不受影响。

Day 0b（0.5 天）：

- 更新 `protocols.VectorStore` 方法名和返回类型对齐 `BaseVectorStore` ABC。
- 验证 `isinstance(ChromaDBStore(), VectorStore)` 通过。

Day 0c（1-1.5 天）：

- 抽取 `build_answer_context()`，消除 `generate_answer()` 和 `generate_answer_stream()` 中约 54 行重复的 context 构建逻辑。
- 迁移 `create_client()` 从同步 `openai.OpenAI` 到 `BaseLLMProvider` / `AsyncOpenAI`。
- 采用双入口模式：`query_async()` 为异步主实现，FastAPI `await` 调用；CLI 通过 `asyncio.run(query_async())` 同步调用。
- 全量查询测试验证无回归。

Day 0d（0.5 天）：

- 在 `Settings` 中实现 typed env helper（`_env_mapping` 类变量或等价机制），支持新增配置项自动从环境变量读取。
- 将后续方案所需的 20+ 个配置项通过此机制一次性注册，避免每个 PR 手写 `from_env()` 映射。
- 验证现有配置项行为不变。

### 第 1 周：Reranker + RAG 评估（5 天）

Day 1-2：

- 实现 BGE / SentenceTransformers reranker（`sentence_transformers.CrossEncoder` 作为默认轻量实现，BGE 作为可选）。
- `kb query` 和 `/api/v1/query` 支持 `rerank=true`。
- 加 reranker 单测和 benchmark。

Day 3-4：

- 新增 RAG eval schema、dataset loader、基础 retrieval metrics。
- 支持 golden JSONL。
- 接入 LLM judge / Ragas adapter。
- 生成 JSON + Markdown 评估报告。

Day 5：

- 跑 baseline：无 reranker vs reranker。
- 输出第一份评测报告，确定默认 candidate_k / final_k。

### 第 2 周：可观测性 + 流式输出（6-7 天）

Day 1-2：

- 新增 observability manager。
- Prometheus counters/histograms。
- 处理 Docker 多 worker 场景（`prometheus_client.multiprocess`）。

Day 3-4：

- LLM 调用、retrieval、rerank 包 span（注意：查询链路需手动埋点）。
- response 增加 trace_id。
- middleware 执行顺序：CORS → tracing → auth → route handler。
- `/metrics` 和 optional OTLP exporter。
- 验证默认不记录敏感全文。

Day 5-6：

- 重构 SSE 为 async generator（依赖前置任务 A 的 `build_answer_context()` 已抽取）。
- 增加 ping、error、done、versioned events。
- 处理 `ThreadPoolExecutor` → `asyncio.to_thread()` 迁移。
- 缓存命中返回 `done` 事件。

Day 7：

- 前端 StreamingMarkdown。
- SSE 集成测试与手动 smoke。

### 第 3 周：语义分块 + 整体优化（6-7 天）

Day 1-2：

- 新增 chunking 抽象和 structure wrapper。
- 增加 recursive token-aware chunker。
- raw chunks indexing。
- 查询支持 chunks collection。

Day 3-4：

- semantic chunker 实验实现（复用已有 embedding function）。
- chunk benchmark。
- 运行 RAG eval 对比 structure / recursive / semantic。
- 根据结果决定默认策略。

Day 5-6：

- 编译缓存 key 版本化（加入 chunk_strategy + index_raw_chunks）。
- promote 适配 chunks collection metadata 更新。
- store 实例提升为 CompilerWorker 属性（性能优化）。

Day 7：

- 文档更新。
- CI 测试补齐。
- 生成最终 benchmark 和 eval 对比报告。

## 11. 风险与回滚

| 风险 | 影响 | 缓解 |
| --- | --- | --- |
| Reranker 延迟过高 | 查询变慢 | 默认关闭；candidate_k 限制；缓存 rerank 分数 |
| Ragas 依赖较重 | 安装复杂 | 做 optional extra；保留 local metrics |
| OTel 记录敏感内容 | 隐私风险 | 默认只记录 metadata；全文记录需显式开启 |
| SSE 代理缓冲 | 用户看不到流式效果 | 设置 no-cache、X-Accel-Buffering、heartbeat |
| raw chunk 索引膨胀 | 磁盘与内存上涨 | 默认关闭；按文件类型/质量阈值启用 |
| semantic chunking 收益不稳定 | 引入复杂度但无质量收益 | 必须通过 RAG eval 后再默认启用 |
| 查询链路迁移到异步引入回归 | 查询功能不可用 | 前置任务独立分支开发 + 全量查询测试 + 渐进式迁移（先加 async wrapper 再移除 sync） |
| 多个方案依赖 RetrievalCandidate 模型变更 | 连锁修改 | 优先合入 RetrievalCandidate，后续方案以此为基线 |
| raw chunk 索引导致编译缓存失效 | 重编译所有文档 | 缓存 key 加入 chunk_strategy 版本号，旧缓存自动失效 |

## 12. 验收标准

Reranker：

- `rerank=false` 时旧测试全通过。
- `rerank=true` 时 response 包含 rerank score。
- benchmark 中 candidate_k=50 的额外延迟可接受。

RAG 评估：

- 能读取 JSONL golden set。
- 能输出 retrieval 和 generation 分层指标。
- CI 可跑小样本 smoke eval。

可观测性：

- `/metrics` 可访问。
- 每次 query 有 trace_id。
- LLM latency、token usage、error count 可统计。

流式输出：

- SSE 事件顺序稳定。
- 长回答能在首 token 前明显降低等待。
- 客户端断开后后端停止继续生成。

语义分块：

- raw chunk indexing 可配置。
- chunk evidence 能返回 source/section/chunk_id。
- 至少一个评估集上 Recall@k 或 Faithfulness 有可量化提升。
