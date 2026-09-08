"""Pydantic v2 数据模型 — API 请求/响应"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

# ── 查询 ─────────────────────────────────────────────────────


class QueryRequest(BaseModel):
    """查询请求"""

    q: str = Field(..., min_length=1, description="查询关键词")
    mode: str = Field(
        default="combined", description="查询模式: concept|summary|vector|combined|all"
    )
    top_k: int = Field(default=5, ge=1, le=50, description="返回结果数量")


class SearchResult(BaseModel):
    """单条搜索结果"""

    title: str = ""
    content: str = ""
    source: str = ""
    file_path: str = ""
    manifest_id: str | None = None
    score: float = 0.0
    rerank_score: float | None = None
    rank_source: str = ""
    """排序来源: keyword / vector / rerank"""


class Citation(BaseModel):
    """结构化引用：把回答中的 [Sn] 映射回可验证的来源。"""

    ref: str
    """引用编号，如 "S1" """

    manifest_id: str | None = None
    """来源 manifest ID（如 SRC-0001）"""

    source: str = ""
    """来源文件路径或标识（wiki/outputs/vector + 文件名）"""

    channel: str = ""
    """检索通道：concept / summary / vector"""

    text_hash: str = ""
    """被引用文本的内容哈希，用于版本追踪"""

    score: float = 0.0
    """检索分数"""


class QueryResponse(BaseModel):
    """查询响应"""

    query: str
    mode: str
    concepts: list[SearchResult] = []
    summaries: list[SearchResult] = []
    vector_results: list[SearchResult] = []
    search_sources: list[str] = []
    answer: str | None = None
    time_seconds: float = 0.0
    reranked: bool = False
    """是否经过 Reranker 重排序"""

    citations: list[Citation] = []
    """回答中 [Sn] 引用到来源的结构化映射"""

    unresolved_refs: list[str] = []
    """回答中出现但无法映射到来源的引用编号"""

    warnings: list[str] = []
    """非致命降级信息（如向量检索不可用）"""

    llm_unavailable: bool = False
    """LLM 生成通道不可用（如未配置 API Key），answer 为降级提示而非真实回答"""

    timings: dict[str, float] = {}
    """阶段耗时（秒）：retrieval/rerank/first_token/generation/total"""

    trace_id: str = ""
    """请求追踪 ID，用于关联后端日志与 citations"""


class QueryContributionRequest(BaseModel):
    """将一次已完成的只读查询显式写入候选知识区。"""

    query: str = Field(..., min_length=1, max_length=500)
    mode: str = Field(default="combined", max_length=32)
    concepts: list[SearchResult] = Field(default_factory=list)
    summaries: list[SearchResult] = Field(default_factory=list)
    vector_results: list[SearchResult] = Field(default_factory=list)
    search_sources: list[str] = Field(default_factory=list)
    answer: str = Field(..., min_length=100, max_length=200_000)
    time_seconds: float = Field(default=0.0, ge=0.0)


class QueryContributionResponse(BaseModel):
    """显式贡献写入回执。"""

    id: str
    quality_score: int = Field(ge=0, le=100)
    needs_review: bool = True
    auto_promoted: bool = False
    status: str = "candidate"


# ── 编译 ─────────────────────────────────────────────────────


class CompileRequest(BaseModel):
    """编译请求"""

    limit: int | None = Field(default=None, ge=1, le=1000, description="编译数量限制")
    concurrency: int = Field(default=1, ge=1, le=10, description="并发数")
    dry_run: bool = Field(default=False, description="模拟运行")


class CompileResponse(BaseModel):
    """编译响应"""

    job_id: str | None = None
    status: str
    message: str
    total: int = 0
    processed: int = 0
    compiled: int = 0
    failed: int = 0
    current_files: list[str] = Field(default_factory=list)
    failed_files: list[str] = Field(default_factory=list)
    """编译失败（或异常终止）的文档 ID 列表"""
    failure_details: list[dict[str, Any]] = Field(default_factory=list)
    """失败明细：[{src_id, error}]，error 已脱敏"""
    cancel_requested: bool = False
    concurrency: int = 1
    limit: int | None = None
    attempt: int = 1
    retry_of: str | None = None
    retryable: bool = False
    error: str | None = None
    created_at: str | None = None
    started_at: str | None = None
    finished_at: str | None = None


class CompileJobFailuresResponse(BaseModel):
    """单次编译任务的失败明细（已脱敏）。"""

    job_id: str
    status: str
    failed: int = 0
    failed_files: list[str] = Field(default_factory=list)
    failure_details: list[dict[str, Any]] = Field(default_factory=list)


# ── 状态 ─────────────────────────────────────────────────────


class SystemInfo(BaseModel):
    """系统运行环境信息"""

    python_version: str = ""
    platform: str = ""
    disk_usage_bytes: int = 0
    disk_total_bytes: int = 0


class StatusResponse(BaseModel):
    """系统状态响应"""

    workspace: str
    version: str
    manifests: ManifestStats
    config: ConfigInfo
    system: SystemInfo = SystemInfo()


class ManifestStats(BaseModel):
    """manifest 统计"""

    total: int = 0
    ingested: int = 0
    compiled: int = 0
    failed: int = 0
    promoted_to_wiki: int = 0
    promoted: int = 0
    by_type: dict[str, int] = Field(default_factory=dict)
    trust_levels: dict[str, int] = Field(default_factory=dict)
    concepts_count: int = 0
    summaries_count: int = 0


class ConfigInfo(BaseModel):
    """配置摘要"""

    model: str = ""
    api_base: str = ""
    max_concurrency: int = 1
    min_quality_score: int = 85
    has_api_key: bool = False
    query_model: str = ""
    llm_provider: str = "openai_compat"
    workspace: str = ""
    temperature: float = 0.1


# ── 晋升 ─────────────────────────────────────────────────────


class PromoteRequest(BaseModel):
    """晋升请求"""

    target: str = Field(..., description="目标层级: wiki|curated")


class PromoteResponse(BaseModel):
    """晋升响应"""

    src_id: str
    target: str
    success: bool
    message: str


# ── 通用 ─────────────────────────────────────────────────────


class ErrorResponse(BaseModel):
    """错误响应"""

    error: str
    detail: str = ""
