"""
质量评分模块单元测试

覆盖 score_summary_quality_v4 的所有维度子函数和公共 API。
"""

import pytest

from dochris.core.quality_scorer import (
    DimensionScore,
    QualityReport,
    _detect_template,
    _safe_list,
    _safe_str,
    _score_concepts,
    _score_detail_length,
    _score_info_density,
    _score_key_points,
    _score_learning_value,
    _score_one_line,
    _tiered_score,
    get_quality_threshold,
    score_summary_quality_v4,
    score_summary_quality_v4_report,
)


# ============================================================
# 工具函数测试
# ============================================================


class TestSafeStr:
    """测试 _safe_str 防御性字符串提取"""

    def test_none(self) -> None:
        assert _safe_str(None) == ""

    def test_string(self) -> None:
        assert _safe_str("hello") == "hello"

    def test_empty_string(self) -> None:
        assert _safe_str("") == ""

    def test_int(self) -> None:
        assert _safe_str(42) == "42"

    def test_zero(self) -> None:
        assert _safe_str(0) == ""

    def test_list(self) -> None:
        assert _safe_str([1, 2]) == "[1, 2]"

    def test_false_returns_empty(self) -> None:
        assert _safe_str(False) == ""


class TestSafeList:
    """测试 _safe_list 防御性列表提取"""

    def test_none(self) -> None:
        assert _safe_list(None) == []

    def test_list(self) -> None:
        assert _safe_list([1, 2, 3]) == [1, 2, 3]

    def test_empty_list(self) -> None:
        assert _safe_list([]) == []

    def test_string_returns_empty(self) -> None:
        assert _safe_list("abc") == []

    def test_int_returns_empty(self) -> None:
        assert _safe_list(42) == []


class TestTieredScore:
    """测试 _tiered_score 阶梯评分"""

    def test_exact_threshold(self) -> None:
        tiers = [(100, 50), (50, 25), (10, 5)]
        assert _tiered_score(100, tiers) == 50

    def test_between_tiers(self) -> None:
        tiers = [(100, 50), (50, 25), (10, 5)]
        assert _tiered_score(75, tiers) == 25

    def test_below_all(self) -> None:
        tiers = [(100, 50), (50, 25)]
        assert _tiered_score(5, tiers) == 0

    def test_default(self) -> None:
        tiers = [(100, 50)]
        assert _tiered_score(1, tiers, default=3) == 3


# ============================================================
# 维度子函数测试
# ============================================================


class TestScoreDetailLength:
    """测试 detailed_summary 长度评分"""

    @pytest.mark.parametrize(
        "length,expected",
        [
            (0, 0),
            (50, 0),
            (199, 0),
            (200, 4),
            (300, 4),
            (399, 4),
            (400, 8),
            (599, 8),
            (600, 12),
            (799, 12),
            (800, 16),
            (999, 16),
            (1000, 19),
            (1199, 19),
            (1200, 22),
            (1499, 22),
            (1500, 25),
            (2000, 25),
        ],
    )
    def test_length_tiers(self, length: int, expected: int) -> None:
        result = _score_detail_length("x" * length)
        assert result.points == expected
        assert result.max_points == 25
        assert result.name == "detail_length"


class TestScoreKeyPoints:
    """测试 key_points 数量评分"""

    @pytest.mark.parametrize(
        "key_points,expected",
        [
            ([], 0),
            ([""], 0),
            (["  "], 0),
            ([None], 0),  # type: ignore[list-item]
            (["a"], 7),
            (["a", "b"], 14),
            (["a", "b", "c"], 22),
            (["a", "b", "c", "d"], 26),
            (["a", "b", "c", "d", "e"], 30),
            (["a", "b", "c", "d", "e", "f"], 30),
        ],
    )
    def test_key_points_tiers(self, key_points: list, expected: int) -> None:
        result = _score_key_points(key_points)
        assert result.points == expected
        assert result.max_points == 30
        assert result.name == "key_points"

    def test_filters_empty_strings(self) -> None:
        """空字符串不计入有效 key_points"""
        result = _score_key_points(["", "  ", "valid", None])  # type: ignore[list-item]
        assert result.points == 7  # 只有 1 个有效


class TestScoreLearningValue:
    """测试学习价值关键词评分"""

    @pytest.mark.parametrize(
        "text,expected",
        [
            ("普通文本没有关键词", 1),  # "重点" in "没有关键词" → count=1 → 1分
            ("学习很重要", 1),
            ("学习和提升都需要方法", 3),
            ("学习和提升，改善和掌握都需要理解和应用", 9),  # count=6 → >=6: 9分
            ("学习提升改善掌握理解应用运用技能知识", 12),  # count=9 → >=8: 12分
            ("学习提升改善掌握理解应用运用技能知识能力方法策略技巧", 15),  # count=13 → >=10: 15分
            ("学习提升改善掌握理解应用运用技能知识能力方法策略技巧教训重点", 15),  # count=15 → >=10: 15分
        ],
    )
    def test_learning_tiers(self, text: str, expected: int) -> None:
        result = _score_learning_value(text)
        assert result.points == expected
        assert result.max_points == 15
        assert result.name == "learning_value"


class TestScoreInfoDensity:
    """测试信息密度关键词评分"""

    @pytest.mark.parametrize(
        "text,expected",
        [
            ("普通文本", 0),
            ("使用了API调用", 2),
            ("API和SDK的架构框架", 4),
            ("工具框架API SDK算法架构协议数据库缓存容器微服务中间件配置部署监控", 5),
        ],
    )
    def test_info_tiers(self, text: str, expected: int) -> None:
        result = _score_info_density(text)
        assert result.points == expected
        assert result.max_points == 5
        assert result.name == "info_density"


class TestScoreOneLine:
    """测试单行摘要质量评分"""

    @pytest.mark.parametrize(
        "text,expected",
        [
            ("", 0),
            ("hi", 0),
            ("hello", 1),
            ("这是一个简短的摘要", 1),
            ("这是一个十个字的摘要测试", 3),
            ("a" * 20, 5),  # 精确20字符
            ("a" * 30, 5),  # 30字符在最佳范围
            ("a" * 50, 5),  # 精确50字符
            ("a" * 51, 3),  # 超过50字符
        ],
    )
    def test_one_line_tiers(self, text: str, expected: int) -> None:
        result = _score_one_line(text)
        assert result.points == expected
        assert result.max_points == 5
        assert result.name == "one_line"


class TestScoreConcepts:
    """测试概念完整性评分"""

    @pytest.mark.parametrize(
        "concepts,expected",
        [
            ([], 0),
            ([""], 0),
            (["  "], 0),
            ([None], 0),  # type: ignore[list-item]
            (["a"], 2),
            (["a", "b"], 4),
            (["a", "b", "c"], 6),
            (["a", "b", "c", "d"], 8),
            (["a", "b", "c", "d", "e"], 10),
            (["a"] * 10, 10),
        ],
    )
    def test_concepts_tiers(self, concepts: list, expected: int) -> None:
        result = _score_concepts(concepts)
        assert result.points == expected
        assert result.max_points == 10
        assert result.name == "concepts"

    def test_filters_empty_strings(self) -> None:
        result = _score_concepts(["", "  ", "valid", None])  # type: ignore[list-item]
        assert result.points == 2  # 只有 1 个有效


class TestDetectTemplate:
    """测试模板文字检测"""

    def test_clean_text(self) -> None:
        result = _detect_template("这是一段正常的学习笔记")
        assert result.points == 0
        assert result.name == "template"

    @pytest.mark.parametrize(
        "text",
        [
            "这里是一个摘要的内容",
            "这是一个概括的文本",
            "this is a summary of",
            "概括了主要内容",
            "总结一下要点",
        ],
    )
    def test_template_detected(self, text: str) -> None:
        result = _detect_template(text)
        assert result.points == -10
        assert result.detail == "detected=True"


# ============================================================
# 公共 API 测试
# ============================================================


class TestScoreSummaryQualityV4:
    """测试质量评分主函数"""

    def test_non_dict_returns_zero(self) -> None:
        assert score_summary_quality_v4("not a dict") == 0

    def test_none_returns_zero(self) -> None:
        assert score_summary_quality_v4(None) == 0

    def test_empty_dict_returns_zero(self) -> None:
        assert score_summary_quality_v4({}) == 0

    def test_perfect_score(self) -> None:
        """各项都达到最高分：25+30+15+5+5+10=90"""
        # 构造包含 10+ 个不同学习关键词 + 5+ 个信息密度关键词的文本
        learning_kw = "学习提升改善掌握理解应用运用技能知识能力方法"
        info_kw = "工具框架API SDK算法架构协议数据库缓存容器"
        summary = {
            "detailed_summary": (learning_kw + info_kw) * 35,  # >=1500 字符
            "key_points": ["要点1", "要点2", "要点3", "要点4", "要点5"],
            "one_line": "a" * 25,
            "concepts": ["概念1", "概念2", "概念3", "概念4", "概念5"],
        }
        result = score_summary_quality_v4(summary)
        assert result == 90

    def test_max_score_is_100(self) -> None:
        summary = {
            "detailed_summary": "学习" * 200 + "方法" * 100,
            "key_points": ["要点"] * 10,
            "one_line": "完美长度的摘要",
            "concepts": ["概念"] * 10,
        }
        assert score_summary_quality_v4(summary) <= 100

    def test_min_score_is_0(self) -> None:
        summary = {
            "detailed_summary": "这里是一个summary概括总结",
            "key_points": [],
            "concepts": [],
        }
        assert score_summary_quality_v4(summary) >= 0

    def test_template_penalty(self) -> None:
        """模板检测应扣10分"""
        summary_clean = {
            "detailed_summary": "x" * 1000,
            "key_points": ["要点1", "要点2", "要点3"],
            "concepts": ["概念1", "概念2"],
        }
        summary_template = {
            "detailed_summary": "这里是一个摘要概括的文档内容。" + "x" * 1000,
            "key_points": ["要点1", "要点2", "要点3"],
            "concepts": ["概念1", "概念2"],
        }
        clean = score_summary_quality_v4(summary_clean)
        template = score_summary_quality_v4(summary_template)
        assert template < clean
        assert clean - template >= 10

    def test_overlength_penalty(self) -> None:
        """超过3000字的摘要应被扣分"""
        summary_normal = {
            "detailed_summary": "x" * 1500,
            "key_points": ["a"] * 5,
            "concepts": ["c"] * 5,
        }
        summary_long = {
            "detailed_summary": "x" * 4000,
            "key_points": ["a"] * 5,
            "concepts": ["c"] * 5,
        }
        normal = score_summary_quality_v4(summary_normal)
        long_ = score_summary_quality_v4(summary_long)
        assert long_ < normal  # 超长应被扣分

    def test_null_fields(self) -> None:
        """None 字段应被安全处理"""
        summary = {
            "detailed_summary": None,
            "key_points": None,
            "one_line": None,
            "concepts": None,
        }
        assert score_summary_quality_v4(summary) == 0


class TestScoreSummaryQualityV4Report:
    """测试带报告版本的评分函数"""

    def test_none_returns_zero_report(self) -> None:
        report = score_summary_quality_v4_report(None)
        assert report.total == 0
        assert report.dimensions == []
        assert report.template_detected is False

    def test_report_structure(self) -> None:
        summary = {
            "detailed_summary": "x" * 1000,
            "key_points": ["a", "b", "c"],
            "concepts": ["c1", "c2"],
        }
        report = score_summary_quality_v4_report(summary)
        assert isinstance(report, QualityReport)
        assert report.total > 0
        assert len(report.dimensions) == 7
        assert all(isinstance(d, DimensionScore) for d in report.dimensions)
        assert report.template_detected is False

    def test_report_matches_score(self) -> None:
        """report.total 应与 score_summary_quality_v4 返回值一致"""
        summary = {
            "detailed_summary": "学习" * 200 + "工具框架API SDK算法架构协议",
            "key_points": ["a", "b", "c", "d"],
            "one_line": "这是一个正好二十个字符的摘要测",
            "concepts": ["c1", "c2", "c3"],
        }
        score = score_summary_quality_v4(summary)
        report = score_summary_quality_v4_report(summary)
        assert score == report.total

    def test_template_detected_in_report(self) -> None:
        summary = {
            "detailed_summary": "这里是一个摘要" + "x" * 500,
            "key_points": ["a"],
            "concepts": [],
        }
        report = score_summary_quality_v4_report(summary)
        assert report.template_detected is True


class TestGetQualityThreshold:
    """测试质量阈值函数"""

    def test_returns_int(self) -> None:
        result = get_quality_threshold()
        assert isinstance(result, int)

    def test_default_threshold(self) -> None:
        result = get_quality_threshold()
        assert result == 85
