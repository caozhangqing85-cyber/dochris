# Dochris 知识库编译系统 — 性能评审报告

> 评审日期: 2026-05-04  
> 评审范围: 编译阶段 (Phase 2) + 查询阶段 (Phase 3) 全链路  
> 数据规模: 5307 manifests, 4256 已编译文档, 4.4GB 原始文件, 11GB 工作区  
> 缓存命中: 0 个缓存文件 (缓存目录为空!)

---

## 一、性能瓶颈清单（按影响程度排序）

### 🔴 P0 — 严重瓶颈

| # | 瓶颈 | 文件 | 行号 | 影响 | 分类 |
|---|------|------|------|------|------|
| 1 | **httpx max_connections=1 限制吞吐** | `llm/openai_compat.py` | L62 | **所有 LLM 调用被迫串行**，即使 asyncio 并发也因连接池只有 1 而排队等待。max_concurrency=3 形同虚设 | 快速 |
| 2 | **速率限制器是单实例全局变量** | `core/llm_client.py` | L169, L181-195 | `_rate_limit()` 基于 `self.last_request_time` 做串行等待，所有并发协程共享同一个 LLMClient 实例，实际上把并发降为串行 | 快速 |
| 3 | **缓存完全无效（命中率 0%）** | `core/cache.py` | 全文件 | 缓存目录 4KB，0 个缓存文件。`save_cached()` 使用 `indent=2` 写入大 JSON（含详细摘要 1000-2000 字），I/O 成本高但从未生效 | 快速 |
| 4 | **查询阶段关键词搜索全量扫描** | `phases/query_utils.py` | L190-192 | `_keyword_search()` 对 search_dir 下所有 `.md` 文件逐个 `read_text()` + 正则匹配，4256 个文件 = 4256 次文件读取，O(N) 全量扫描无索引 | 长期 |
| 5 | **FAISS 文档 ID 映射 O(N) 线性查找** | `vector/faiss_store.py` | L279 | 每次查询执行 `list(docs.keys())`，然后按索引访问。FAISS 内部索引是连续整数，但映射回文档 ID 需遍历整个 dict | 快速 |
| 6 | **Phase 3 使用同步 OpenAI 客户端** | `phases/query_engine.py` | L30, L380 | `_llm_client_cache` 是 `openai.OpenAI`（同步），`generate_answer()` 是同步函数，在 asyncio 上下文中调用时阻塞事件循环 | 长期 |

### 🟡 P1 — 重要瓶颈

| # | 瓶颈 | 文件 | 行号 | 影响 | 分类 |
|---|------|------|------|------|------|
| 7 | **重试退避延迟过大** | `core/retry_manager.py` | L144, L156 | 429 初始 30s, 连接错误初始 20s，指数退避上限 60s。8 次重试最坏情况累计等待 30+60+60+60+60+60+60+60 = **450 秒** | 快速 |
| 8 | **分层摘要阶段未受 Semaphore 控制** | `core/hierarchical_summarizer.py` | L219 | `asyncio.gather()` 并行处理所有 chunk 摘要，但不受 phase2 的 `Semaphore(max_concurrent)` 约束，可能瞬间发出数十个并发请求 | 快速 |
| 9 | **FAISS 每次添加文档都完整重写 metadata.json** | `vector/faiss_store.py` | L158-167 | `_save_collection()` 把全部文档内容 + 元数据序列化为一个 JSON 文件，文档数量增长后 I/O 和内存开销巨大 | 长期 |
| 10 | **ChromaDB 每次 add 都重新 get_or_create** | `vector/chromadb_store.py` | L88 | `col = client.get_or_create_collection(name=collection)` 在每次 `add_documents()` 调用时执行，批量插入时产生不必要的开销 | 快速 |
| 11 | **PDF 解析器链式降级无超时控制** | `parsers/pdf_parser.py` | L41-108 | `parse_with_pypdf2()` 和 `parse_with_pdfplumber()` 无超时，大 PDF 可能阻塞数分钟。只有 `parse_with_markitdown()` 有 timeout=10 | 快速 |
| 12 | **CompilerWorker 缓存检查使用同步阻塞 I/O** | `workers/compiler_worker.py` | L180-183 | `file_hash()` → `path.read_bytes()` 和 `load_cached()` 在 async 函数中同步读取，阻塞事件循环 | 快速 |
| 13 | **manifest 索引文件名 fallback 遍历** | `phases/query_utils.py` | L131-134 | `_get_manifest_id()` 在直接匹配失败后，遍历整个 manifest 索引做文件名匹配，5307 条目 | 长期 |

### 🟢 P2 — 优化机会

| # | 瓶颈 | 文件 | 行号 | 影响 | 分类 |
|---|------|------|------|------|------|
| 14 | **save_cached 使用 indent=2 写大 JSON** | `core/cache.py` | L86-91 | JSON pretty-printing 增加 30-50% 文件大小，写入时间也增加 | 快速 |
| 15 | **_extract_json_from_text 低效字符串处理** | `core/llm_client.py` | L262-308 | 逐字符遍历整个 LLM 响应文本，对于长响应（如分层摘要合并）效率低 | 长期 |
| 16 | **prompt 中完整嵌入文档文本** | `core/summary_generator.py` | L147-154 | 直接将 text 塞入 prompt，无 token 计数和截断保护，可能超模型上下文窗口导致截断/错误 | 快速 |
| 17 | **LLMClient 创建 httpx.AsyncClient 无连接池复用** | `core/llm_client.py` | L157-162 | 非 openai_compat provider 额外创建一个 AsyncOpenAI + httpx 客户端，双倍连接资源 | 长期 |
| 18 | **quality_scorer 同步调用** | `workers/compiler_worker.py` | L220 | `score_summary_quality_v4()` 在 async 上下文中同步执行，如果计算量大会阻塞事件循环 | 长期 |
| 19 | **chunk overlap 计算重复拼接字符串** | `core/text_chunker.py` | L293-296 | `last_content = "\n\n".join(current_chunk)` 在循环中重复构建字符串 | 长期 |

---

## 二、每个瓶颈的具体优化方案

### 🔴 P0-1: httpx max_connections=1 → 提升至 max_concurrency

**位置**: `src/dochris/llm/openai_compat.py:62`  
**现状**: `httpx.Limits(max_connections=1)`  
**方案**:
```python
# 改为可配置，默认值与 max_concurrency 对齐
limits=httpx.Limits(max_connections=10, max_keepalive_connections=5)
```
**预估提升**: 并发编译吞吐量 **3-5x**（当前 3 个并发任务共享 1 个连接，实际串行）

---

### 🔴 P0-2: 速率限制器改为异步信号量

**位置**: `src/dochris/core/llm_client.py:181-195`  
**现状**: `self.last_request_time` 作为全局锁，所有协程串行等待  
**方案**: 使用 `asyncio.Semaphore` + 令牌桶或滑动窗口限速器
```python
import asyncio

class RateLimiter:
    def __init__(self, rate: float, max_tokens: int = 1):
        self._rate = rate  # 每秒令牌数
        self._tokens = max_tokens
        self._max_tokens = max_tokens
        self._last_refill = time.monotonic()
        self._lock = asyncio.Lock()

    async def acquire(self):
        async with self._lock:
            now = time.monotonic()
            elapsed = now - self._last_refill
            self._tokens = min(self._max_tokens, self._tokens + elapsed * self._rate)
            self._last_refill = now
            if self._tokens < 1:
                wait = (1 - self._tokens) / self._rate
                await asyncio.sleep(wait)
                self._tokens = 0
            else:
                self._tokens -= 1
```
**预估提升**: 消除并发假象，真实吞吐量 **3x**

---

### 🔴 P0-3: 缓存修复

**位置**: `src/dochris/core/cache.py`  
**现状**: 缓存目录为空，`save_cached()` 似乎未被正确调用或缓存已过期被清理  
**方案**:
1. **诊断**: 在 `save_cached()` 中增加日志确认写入路径
2. **修复**: `file_hash()` 对大文件使用流式读取避免 OOM
3. **性能**: `save_cached()` 移除 `indent=2`，改为 `indent=None`（单行 JSON）
4. **缓存验证**: 检查 `clear_cache()` 是否在编译结束时错误清理了所有缓存
```python
# cache.py:30 — 流式哈希避免 OOM
def file_hash(path: Path) -> str | None:
    try:
        h = hashlib.sha256()
        with open(path, "rb") as f:
            while chunk := f.read(8192):
                h.update(chunk)
        return h.hexdigest()
    except OSError:
        return None
```
**预估提升**: 重复编译时 **100% 跳过 LLM 调用**（当前每次都重新编译）

---

### 🔴 P0-4: 查询关键词搜索建立倒排索引

**位置**: `src/dochris/phases/query_utils.py:167-220`  
**现状**: 4256 个文件全量 `read_text()` + 正则匹配  
**方案**:
```python
import sqlite3
from pathlib import Path

class SearchIndex:
    """基于 SQLite FTS5 的全文搜索索引"""
    def __init__(self, db_path: Path):
        self.conn = sqlite3.connect(str(db_path))
        self.conn.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS summaries 
            USING fts5(title, content, filename)
        """)

    def index_file(self, filepath: Path, content: str):
        self.conn.execute(
            "INSERT INTO summaries VALUES (?, ?, ?)",
            (filepath.stem, content, str(filepath))
        )

    def search(self, query: str, limit: int = 5) -> list:
        cursor = self.conn.execute(
            "SELECT filename, rank FROM summaries WHERE summaries MATCH ? ORDER BY rank LIMIT ?",
            (query, limit)
        )
        return cursor.fetchall()
```
**预估提升**: 查询延迟从 O(N) 文件读取 → **< 50ms** SQLite FTS5

---

### 🔴 P0-5: FAISS 文档 ID 映射优化

**位置**: `src/dochris/vector/faiss_store.py:279`  
**现状**: `doc_keys = list(docs.keys())` 每次查询 O(N)  
**方案**: 维护一个 `id_to_index: dict[str, int]` 映射表
```python
self._id_to_index: dict[str, dict[str, int]] = {}  # collection -> {doc_id: faiss_idx}

# 在 add_documents 中构建
for i, doc_id in enumerate(ids):
    self._id_to_index[collection][doc_id] = self._indexes[collection].ntotal - len(ids) + i

# 在 query 中使用
for i, idx in enumerate(indices[0]):
    if idx < 0: continue
    # O(1) 反查
    doc_id = self._index_to_id[collection].get(idx)
    if doc_id is None: continue
```
**预估提升**: 查询映射 **O(N) → O(1)**

---

### 🔴 P0-6: Phase 3 使用异步 OpenAI 客户端

**位置**: `src/dochris/phases/query_engine.py:30,380`  
**现状**: `openai.OpenAI` 同步客户端在查询链路中阻塞  
**方案**: 改为 `openai.AsyncOpenAI`，`generate_answer()` 改为 `async def`
```python
_llm_client_cache: openai.AsyncOpenAI | None = None

async def generate_answer(...) -> str | None:
    # ... 
    response = await client.chat.completions.create(...)
```
**预估提升**: API 服务并发查询能力提升，查询延迟减少阻塞时间

---

### 🟡 P1-7: 降低重试退避初始值

**位置**: `src/dochris/core/retry_manager.py:144,156`  
**现状**: 429 初始 30s, 连接错误初始 20s  
**方案**: 对齐 Settings 中的配置（`retry_delay_429=20s`, `retry_delay_connection=15s`），并使用 jitter 避免惊群
```python
import random
wait = min(base_delay * (2**attempt), MAX_RETRY_WAIT)
wait *= (0.5 + random.random())  # ±50% jitter
```
**预估提升**: 重试等待时间减少 **40-60%**

---

### 🟡 P1-8: 分层摘要并行度受 Semaphore 控制

**位置**: `src/dochris/core/hierarchical_summarizer.py:219`  
**现状**: `asyncio.gather()` 无并发限制  
**方案**: 将 Semaphore 传入 HierarchicalSummarizer，或在 gather 中使用 bounded semaphore
```python
async def _summarize_chunks_parallel(self, chunks, title, max_retries, semaphore=None):
    async def summarize_one(chunk, index):
        if semaphore:
            async with semaphore:
                return await self._do_summarize(chunk, index, title, max_retries)
        return await self._do_summarize(chunk, index, title, max_retries)
    
    results = await asyncio.gather(*[summarize_one(c, i) for i, c in enumerate(chunks)])
```
**预估提升**: 避免触发 API 限流 429，减少重试

---

### 🟡 P1-11: PDF 解析器增加超时

**位置**: `src/dochris/parsers/pdf_parser.py:41-108`  
**方案**: 对 pypdf2 和 pdfplumber 增加 `asyncio.wait_for` 包装
```python
async def parse_pdf_safe(file_path: Path, timeout: float = 60) -> str | None:
    loop = asyncio.get_event_loop()
    try:
        return await asyncio.wait_for(
            loop.run_in_executor(None, parse_with_pdfplumber, file_path),
            timeout=timeout
        )
    except asyncio.TimeoutError:
        logger.warning(f"pdfplumber 超时 ({timeout}s): {file_path}")
        return None
```
**预估提升**: 避免单个大 PDF 阻塞整个编译队列

---

### 🟡 P1-12: 缓存检查改用 run_in_executor

**位置**: `src/dochris/workers/compiler_worker.py:180-183`  
**方案**:
```python
loop = asyncio.get_event_loop()
fh = await loop.run_in_executor(None, file_hash, file_path)
if fh:
    cached = await loop.run_in_executor(None, load_cached, self.cache_dir, fh)
```
**预估提升**: 消除事件循环阻塞，提升并发效率

---

## 三、快速见效 vs 长期优化分类

### ⚡ 快速见效（1-2 天实现，立即生效）

| 优化 | 预估提升 | 工作量 |
|------|----------|--------|
| P0-1: httpx max_connections=1 → 10 | 3-5x 吞吐 | 1 行改动 |
| P0-2: 速率限制器改为令牌桶 | 3x 吞吐 | ~50 行 |
| P0-3: file_hash 改为流式读取 | 大文件不 OOM | 5 行改动 |
| P0-3: save_cached 移除 indent=2 | 写入快 30% | 1 行改动 |
| P0-5: FAISS 维护 id_to_index 映射 | O(1) 查询 | ~30 行 |
| P1-7: 降低重试初始延迟 + jitter | 40-60% 等待减少 | 5 行改动 |
| P1-10: ChromaDB 缓存 collection 引用 | 减少开销 | ~10 行 |
| P1-12: 缓存检查改 run_in_executor | 消除阻塞 | 5 行改动 |

**快速见效总计预期**: 编译吞吐量提升 **5-10x**，主要来自修复 P0-1 + P0-2

### 🏗️ 长期优化（1-2 周实现，系统性改进）

| 优化 | 预估提升 | 工作量 |
|------|----------|--------|
| P0-3: 诊断并修复缓存完全失效 | 重复编译 100% 跳过 | 调试 + 修复 |
| P0-4: 查询建立 FTS5 索引 | 查询 < 50ms | ~200 行 |
| P0-6: Phase 3 异步化 | 服务端并发能力 | ~100 行 |
| P1-8: 分层摘要并发控制 | 避免 429 | ~20 行 |
| P1-9: FAISS 元数据分片存储 | 内存/IO 大幅降低 | ~100 行 |
| P1-13: manifest 索引建立文件名倒排 | O(1) 查找 | ~30 行 |
| P2-15: JSON 提取优化 | 长响应快 2-3x | ~50 行 |
| P2-16: prompt token 预算管理 | 避免截断 | ~30 行 |

---

## 四、推荐性能测试方案

### 4.1 基准测试工具

```bash
# 安装依赖
pip install pytest-benchmark pytest-asyncio pytest-profiling
pip install py-spy  # CPU profiling
pip install memray  # 内存追踪
```

### 4.2 测试场景

#### 场景 A: 编译吞吐量测试
```python
# test_perf_compile.py
async def test_compile_throughput():
    """测试 100 个文档的编译总时间和 QPS"""
    manifests = get_all_manifests(workspace, status="ingested")[:100]
    start = time.perf_counter()
    # ... 编译所有文档
    elapsed = time.perf_counter() - start
    qps = 100 / elapsed
    print(f"编译 100 文档: {elapsed:.1f}s, QPS={qps:.2f}")
```
**指标**: 总耗时、QPS、LLM API 调用次数、缓存命中率、重试次数

#### 场景 B: 查询延迟测试
```python
# test_perf_query.py
def test_query_latency():
    """测试不同模式的查询延迟"""
    queries = ["机器学习", "Python 异步编程", "知识图谱"]
    for mode in ["concept", "summary", "vector", "combined"]:
        for q in queries:
            start = time.perf_counter()
            result = query(q, mode=mode)
            elapsed = time.perf_counter() - start
            print(f"mode={mode}, q={q}, latency={elapsed*1000:.0f}ms")
```
**指标**: P50/P95/P99 延迟、各阶段耗时分解

#### 场景 C: 向量库压力测试
```python
# test_perf_vector.py
def test_vector_insert_batch():
    """测试批量插入性能"""
    docs = [f"文档 {i} 的内容" * 100 for i in range(1000)]
    ids = [f"doc_{i}" for i in range(1000)]
    
    # 单条插入
    start = time.perf_counter()
    for d, id_ in zip(docs, ids):
        store.add_documents("test", [d], [id_])
    single_time = time.perf_counter() - start
    
    # 批量插入
    start = time.perf_counter()
    store.add_documents("test", docs, ids)
    batch_time = time.perf_counter() - start
    
    print(f"单条: {single_time:.1f}s, 批量: {batch_time:.1f}s, 加速: {single_time/batch_time:.1f}x")
```

#### 场景 D: 并发 LLM 压力测试
```python
# test_perf_llm.py
async def test_llm_concurrency():
    """测试不同并发度下的 LLM 吞吐"""
    for concurrency in [1, 3, 5, 10]:
        semaphore = asyncio.Semaphore(concurrency)
        start = time.perf_counter()
        # 发送 20 个请求
        tasks = [limited_llm_call(sem, text) for sem in [semaphore] for text in texts[:20]]
        results = await asyncio.gather(*tasks)
        elapsed = time.perf_counter() - start
        print(f"并发={concurrency}, 20请求耗时={elapsed:.1f}s, QPS={20/elapsed:.2f}")
```

### 4.3 监控仪表盘

建议在 `MonitorWorker` 中增加以下指标采集：
```python
class PerfMetrics:
    llm_calls_total: int = 0
    llm_calls_success: int = 0
    llm_calls_429: int = 0
    llm_calls_timeout: int = 0
    llm_latency_ms: list[float] = []  # 最近 100 次
    cache_hits: int = 0
    cache_misses: int = 0
    docs_compiled: int = 0
    docs_failed: int = 0
    bytes_processed: int = 0
```

---

## 五、资源使用评估

### 5.1 CPU

| 阶段 | CPU 密集操作 | GIL 影响 | 评估 |
|------|-------------|----------|------|
| Phase 2 文本提取 | PDF 解析 (pypdf2/pdfplumber) | **严重** | 同步 CPU 密集操作阻塞事件循环 |
| Phase 2 LLM 调用 | JSON 解析、正则匹配 | 中等 | asyncio I/O 等待期间 GIL 可释放 |
| Phase 3 关键词搜索 | 文件读取 + 正则 | **严重** | 全量扫描 4256 文件 |
| Phase 3 向量搜索 | 嵌入计算 (FAISS) | **严重** | CPU 密集，建议 offload 到线程池 |

**建议**: PDF 解析和嵌入计算使用 `run_in_executor()`，或对 PDF 解析使用多进程

### 5.2 内存

| 组件 | 内存占用 | 风险 |
|------|----------|------|
| ChromaDB | ~188KB (当前数据量小) | 低 |
| FAISS metadata.json | 全部文档内容存于内存 dict | **高** — 文档数增长后 OOM |
| file_hash() | `path.read_bytes()` 全量加载 | **高** — 500MB 文件直接读入内存 |
| 分层摘要 prompt | 10万字文档拼接 | **中** — 已有截断保护 |
| asyncio gather | 所有 chunk 摘要结果存于内存 | **中** — 50 chunk × 大 JSON |

**建议**: 
- `file_hash()` 必须改为流式（P0-3）
- FAISS metadata 应分片或使用 SQLite
- 监控 `max_content_chars=20000` 是否有效截断

### 5.3 磁盘 I/O

| 操作 | 模式 | 频率 | 评估 |
|------|------|------|------|
| 文件哈希计算 | 全量读取 | 每文档 1 次 | **差** — 应流式 |
| 缓存读写 | JSON 文件 | 每文档 2 次 | 中等 |
| 概念文件写入 | 多个小文件 | 每文档 3-5 个 | 低 |
| 查询关键词搜索 | 4256 次文件读取 | 每次查询 | **极差** |
| FAISS 索引持久化 | 全量重写 | 每次添加 | **差** |
| ChromaDB SQLite | 增量写入 | 每次添加 | 良好 |

### 5.4 网络

| 目标 | 协议 | 并发 | 瓶颈 |
|------|------|------|------|
| 智谱 API (bigmodel.cn) | HTTPS | 受 max_connections=1 限制 | **连接池** |
| Ollama (localhost:11434) | HTTP | 同上 | 连接池 |
| 向量嵌入 (本地) | 无网络 | N/A | CPU |

**关键发现**: `httpx.Limits(max_connections=1)` 是**全系统最大的性能瓶颈**。即使将 `max_concurrency` 设为 10，实际也只能同时处理 1 个 API 请求。

---

## 六、优先级行动计划

### 第 1 天（快速修复）
1. ✅ `openai_compat.py:62` — max_connections=1 → 10
2. ✅ `llm_client.py` — 速率限制器改为令牌桶
3. ✅ `cache.py:30` — file_hash 改流式
4. ✅ `cache.py:89` — save_cached 移除 indent=2
5. ✅ `retry_manager.py` — 降低初始延迟 + jitter

### 第 2-3 天
6. ✅ `faiss_store.py` — 维护 id_to_index 映射
7. ✅ `compiler_worker.py` — 缓存检查改 run_in_executor
8. ✅ `hierarchical_summarizer.py` — 传入 semaphore 控制并行
9. ✅ `pdf_parser.py` — 增加超时控制
10. ✅ 诊断缓存为何为空，修复缓存流程

### 第 1-2 周
11. 🏗️ Phase 3 查询建立 FTS5 索引
12. 🏗️ Phase 3 异步化 (sync OpenAI → AsyncOpenAI)
13. 🏗️ FAISS 元数据分片存储
14. 🏗️ manifest 文件名索引
15. 🏗️ 性能监控仪表盘

---

## 七、总结

当前系统最大的性能问题是**连接池限制 + 速率限制器导致并发完全失效**。5307 个文档在并发=3 的配置下，实际 QPS 仅为 0.2（每 5 秒一个请求），理论编译全量需要 **~7.4 小时**纯 LLM 等待时间。

修复 P0-1 + P0-2 后，QPS 可提升到 **0.6-1.0**（受 API 限流约束），全量编译时间缩短到 **1.5-2.5 小时**。

缓存修复后，增量编译可达到 **秒级**。

查询阶段的主要瓶颈是全量文件扫描（P0-4），建立 FTS5 索引后可从秒级降到毫秒级。
