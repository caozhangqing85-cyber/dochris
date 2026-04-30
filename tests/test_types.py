"""
测试 types.py 模块
"""

from dataclasses import is_dataclass


class TestTypesModule:
    """测试类型定义模块"""

    def test_types_module_exists(self):
        """测试类型模块可以导入"""
        from dochris import types

        assert types is not None

    def test_file_status_enum(self):
        """测试 FileStatus 枚举"""
        from dochris.types import FileStatus

        assert FileStatus.PENDING == "pending"
        assert FileStatus.INGESTED == "ingested"
        assert FileStatus.COMPILED == "compiled"
        assert FileStatus.FAILED == "failed"
        assert FileStatus.SKIPPED == "skipped"

        # 测试枚举值
        values = [status.value for status in FileStatus]
        assert "pending" in values
        assert "compiled" in values

    def test_file_type_enum(self):
        """测试 FileType 枚举"""
        from dochris.types import FileType

        assert FileType.TXT == "txt"
        assert FileType.MD == "md"
        assert FileType.PDF == "pdf"
        assert FileType.DOCX == "docx"
        assert FileType.WAV == "wav"
        assert FileType.MP3 == "mp3"

    def test_manifest_entry_dataclass(self):
        """测试 ManifestEntry 数据类"""
        from dochris.types import FileStatus, FileType, ManifestEntry

        # 测试创建实例
        entry = ManifestEntry(
            id="SRC-0001",
            title="测试文档",
            file_type=FileType.PDF,
            file_path="raw/test.pdf",
            status=FileStatus.COMPILED,
            quality_score=90.5,
        )

        assert entry.id == "SRC-0001"
        assert entry.title == "测试文档"
        assert entry.file_type == FileType.PDF
        assert entry.status == FileStatus.COMPILED
        assert entry.quality_score == 90.5

        # 测试默认值
        entry2 = ManifestEntry(
            id="SRC-0002", title="测试", file_type=FileType.TXT, file_path="test.txt"
        )
        assert entry2.status == FileStatus.PENDING
        assert entry2.quality_score is None

    def test_manifest_entry_is_dataclass(self):
        """测试 ManifestEntry 是数据类"""
        from dochris.types import ManifestEntry

        assert is_dataclass(ManifestEntry)

    def test_compilation_result_dataclass(self):
        """测试 CompilationResult 数据类"""
        from dochris.types import CompilationResult

        result = CompilationResult(
            source_id="SRC-0001", success=True, quality_score=85.0
        )

        assert result.source_id == "SRC-0001"
        assert result.success is True
        assert result.quality_score == 85.0
        assert result.output_files == []
        assert result.error is None
        assert result.duration_seconds == 0.0

    def test_compilation_result_failure(self):
        """测试编译失败结果"""
        from dochris.types import CompilationResult

        result = CompilationResult(
            source_id="SRC-0002", success=False, error="API error"
        )

        assert result.success is False
        assert result.error == "API error"
        assert result.quality_score is None

    def test_query_result_dataclass(self):
        """测试 QueryResult 数据类"""
        from dochris.types import QueryResult

        result = QueryResult(query="测试查询")

        assert result.query == "测试查询"
        assert result.concepts == []
        assert result.summaries == []
        assert result.vector_results == []
        assert result.answer is None
        assert result.sources == []

    def test_query_result_with_data(self):
        """测试带数据的查询结果"""
        from dochris.types import QueryResult

        result = QueryResult(
            query="测试",
            concepts=[{"name": "概念1"}],
            summaries=[{"title": "摘要1"}],
            answer="测试答案",
            sources=["SRC-0001"],
        )

        assert len(result.concepts) == 1
        assert len(result.summaries) == 1
        assert result.answer == "测试答案"
        assert len(result.sources) == 1

    def test_quality_report_dataclass(self):
        """测试 QualityReport 数据类"""
        from dochris.types import QualityReport

        report = QualityReport(
            file_path="test.pdf", overall_score=85.0, dimension_scores={"length": 35}
        )

        assert report.file_path == "test.pdf"
        assert report.overall_score == 85.0
        assert report.dimension_scores == {"length": 35}
        assert report.deductions == []
        assert report.suggestions == []

    def test_quality_report_with_feedback(self):
        """测试带反馈的质量报告"""
        from dochris.types import QualityReport

        report = QualityReport(
            file_path="test.pdf",
            overall_score=75.0,
            deductions=["摘要过短"],
            suggestions=["增加详细内容"],
        )

        assert len(report.deductions) == 1
        assert len(report.suggestions) == 1
