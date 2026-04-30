"""Dochris 核心类型定义"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class FileStatus(StrEnum):
    """文件处理状态"""

    PENDING = "pending"
    INGESTED = "ingested"
    COMPILED = "compiled"
    FAILED = "failed"
    SKIPPED = "skipped"


class FileType(StrEnum):
    """支持的文件类型"""

    TXT = "txt"
    MD = "md"
    PDF = "pdf"
    DOCX = "docx"
    WAV = "wav"
    MP3 = "mp3"


@dataclass
class ManifestEntry:
    """源文件 manifest 条目"""

    id: str
    title: str
    file_type: FileType
    file_path: str
    status: FileStatus = FileStatus.PENDING
    quality_score: float | None = None
    word_count: int | None = None
    error_message: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class CompilationResult:
    """编译结果"""

    source_id: str
    success: bool
    quality_score: float | None = None
    output_files: list[str] = field(default_factory=list)
    error: str | None = None
    duration_seconds: float = 0.0


@dataclass
class QueryResult:
    """查询结果"""

    query: str
    concepts: list[dict[str, Any]] = field(default_factory=list)
    summaries: list[dict[str, Any]] = field(default_factory=list)
    vector_results: list[dict[str, Any]] = field(default_factory=list)
    answer: str | None = None
    sources: list[str] = field(default_factory=list)


@dataclass
class QualityReport:
    """质量评分报告"""

    file_path: str
    overall_score: float
    dimension_scores: dict[str, float] = field(default_factory=dict)
    deductions: list[str] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)
