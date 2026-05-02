"""Pydantic v2 数据模型 — API 请求/响应"""

from __future__ import annotations

from pydantic import BaseModel, Field

# ── 查询 ─────────────────────────────────────────────────────


class QueryRequest(BaseModel):
    """查询请求"""

    q: str = Field(..., min_length=1, description="查询关键词")
    mode: str = Field(default="combined", description="查询模式: concept|summary|vector|combined|all")
    top_k: int = Field(default=5, ge=1, le=50, description="返回结果数量")


class SearchResult(BaseModel):
    """单条搜索结果"""

    title: str = ""
    content: str = ""
    source: str = ""
    file_path: str = ""
    manifest_id: str | None = None
    score: float = 0.0


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


# ── 编译 ─────────────────────────────────────────────────────


class CompileRequest(BaseModel):
    """编译请求"""

    limit: int | None = Field(default=None, ge=1, le=1000, description="编译数量限制")
    concurrency: int = Field(default=1, ge=1, le=10, description="并发数")
    dry_run: bool = Field(default=False, description="模拟运行")


class CompileResponse(BaseModel):
    """编译响应"""

    status: str
    message: str
    total: int = 0
    compiled: int = 0
    failed: int = 0


# ── 状态 ─────────────────────────────────────────────────────


class StatusResponse(BaseModel):
    """系统状态响应"""

    workspace: str
    version: str
    manifests: ManifestStats
    config: ConfigInfo


class ManifestStats(BaseModel):
    """manifest 统计"""

    total: int = 0
    ingested: int = 0
    compiled: int = 0
    failed: int = 0
    promoted_to_wiki: int = 0
    promoted: int = 0
    by_type: dict[str, int] = Field(default_factory=dict)


class ConfigInfo(BaseModel):
    """配置摘要"""

    model: str = ""
    api_base: str = ""
    max_concurrency: int = 1
    min_quality_score: int = 85
    has_api_key: bool = False


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
