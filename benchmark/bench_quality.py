"""质量评分性能基准测试"""
import pytest


class TestQualityPerformance:
    def test_score_good_content(self, benchmark) -> None:
        """评分 - 正常内容"""
        from dochris.core.quality_scorer import score_summary_quality_v4

        data = {
            "title": "Test Title",
            "summary": "This is a test summary with enough content to be meaningful. " * 20,
            "key_points": ["Point 1", "Point 2", "Point 3"],
            "concepts": ["concept1", "concept2"],
        }
        benchmark(score_summary_quality_v4, data)

    def test_score_minimal_content(self, benchmark) -> None:
        """评分 - 最小内容"""
        from dochris.core.quality_scorer import score_summary_quality_v4

        data = {"title": "", "summary": "", "key_points": [], "concepts": []}
        benchmark(score_summary_quality_v4, data)
