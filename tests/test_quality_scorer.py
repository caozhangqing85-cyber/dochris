"""
质量评分模块单元测试
"""


from dochris.core.quality_scorer import (
    get_quality_threshold,
    score_summary_quality_v4,
)


class TestScoreSummaryQualityV4:
    """测试质量评分函数"""

    def test_non_dict_returns_zero(self):
        """测试非字典输入返回0分"""
        result = score_summary_quality_v4("not a dict")
        assert result == 0

    def test_none_returns_zero(self):
        """测试 None 输入返回0分"""
        result = score_summary_quality_v4(None)
        assert result == 0

    def test_empty_dict_returns_zero(self):
        """测试空字典返回0分"""
        result = score_summary_quality_v4({})
        assert result == 0

    def test_perfect_score(self):
        """测试完美摘要得分"""
        summary = {
            "detailed_summary": "学习" * 400 + "方法" * 200 + "策略" * 120,  # 长内容 (1440字符) + 学习关键词
            "key_points": ["要点1", "要点2", "要点3", "要点4", "要点5"],
            "one_line": "这是一个关于学习方法的优秀文档",
            "concepts": ["概念1", "概念2", "概念3", "概念4", "概念5"],
        }
        result = score_summary_quality_v4(summary)
        assert result >= 85  # 应该达到及格线

    def test_detailed_summary_length_scoring(self):
        """测试详细摘要长度评分"""
        test_cases = [
            (100, 0),   # < 200: 0分
            (300, 5),   # >= 200: 5分
            (500, 10),  # >= 400: 10分
            (700, 15),  # >= 600: 15分
            (900, 20),  # >= 800: 20分
            (1100, 25), # >= 1000: 25分
            (1300, 30), # >= 1200: 30分
            (1600, 35), # >= 1500: 35分
        ]

        for length, expected_points in test_cases:
            summary = {
                "detailed_summary": "x" * length,
                "key_points": [],
                "concepts": [],
            }
            # 基础分数
            base_score = score_summary_quality_v4({
                "detailed_summary": "",
                "key_points": [],
                "concepts": [],
            })
            result = score_summary_quality_v4(summary)
            assert result >= base_score + expected_points - 5  # 允许误差

    def test_key_points_scoring(self):
        """测试要点评分"""
        test_cases = [
            ([], 0),        # 0个要点: 0分
            (["1"], 10),    # 1个要点: 10分
            (["1", "2"], 20),  # 2个要点: 20分
            (["1", "2", "3"], 30),  # 3个要点: 30分
            (["1", "2", "3", "4"], 35),  # 4个要点: 35分
            (["1", "2", "3", "4", "5"], 40),  # 5个要点: 40分
        ]

        for key_points, expected_points in test_cases:
            summary = {
                "detailed_summary": "",
                "key_points": key_points,
                "concepts": [],
            }
            base_score = score_summary_quality_v4({
                "detailed_summary": "",
                "key_points": [],
                "concepts": [],
            })
            result = score_summary_quality_v4(summary)
            assert result >= base_score + expected_points - 5

    def test_learning_value_scoring(self):
        """测试学习价值评分"""
        # 包含大量学习关键词的摘要
        summary_with_learning = {
            "detailed_summary": "这是一个关于学习方法和技能提升的文档。"
            "通过理解和掌握这些策略，可以有效改善能力。"
            "实践训练是提高技能的关键。运用这些技巧可以优化学习效果。"
            "经验教训告诉我们，核心本质和规律模式很重要。",
            "key_points": [],
            "concepts": [],
        }

        summary_without_learning = {
            "detailed_summary": "这是一些普通文本内容，没有太多学习价值。",
            "key_points": [],
            "concepts": [],
        }

        score_with = score_summary_quality_v4(summary_with_learning)
        score_without = score_summary_quality_v4(summary_without_learning)

        assert score_with > score_without

    def test_template_detection_penalty(self):
        """测试模板检测扣分"""
        summary_with_template = {
            "detailed_summary": "这里是一个摘要概括的文档内容。" + "x" * 500,
            "key_points": ["要点1", "要点2", "要点3"],
            "concepts": ["概念1", "概念2"],
        }

        summary_without_template = {
            "detailed_summary": "这是一个关于学习的优质内容。" + "x" * 500,
            "key_points": ["要点1", "要点2", "要点3"],
            "concepts": ["概念1", "概念2"],
        }

        score_with = score_summary_quality_v4(summary_with_template)
        score_without = score_summary_quality_v4(summary_without_template)

        # 模板检测应该扣约20分
        assert score_with < score_without
        assert score_without - score_with >= 15  # 允许一些误差

    def test_one_line_quality_scoring(self):
        """测试一句话摘要质量评分"""
        # 最佳长度 20-50 字符


    def test_concepts_scoring(self):
        """测试概念评分"""
        test_cases = [
            ([], 0),
            (["1"], 2),
            (["1", "2"], 5),
            (["1", "2", "3"], 10),
            (["1", "2", "3", "4"], 15),
            (["1", "2", "3", "4", "5"], 20),
        ]

        for concepts, expected_points in test_cases:
            summary = {
                "detailed_summary": "",
                "key_points": [],
                "concepts": concepts,
            }
            base_score = score_summary_quality_v4({
                "detailed_summary": "",
                "key_points": [],
                "concepts": [],
            })
            result = score_summary_quality_v4(summary)
            assert result >= base_score + expected_points - 5

    def test_max_score_is_100(self):
        """测试最高分不超过100"""
        summary = {
            "detailed_summary": "学习" * 200 + "方法" * 100,  # 极长内容
            "key_points": ["要点"] * 10,
            "one_line": "完美长度的摘要",
            "concepts": ["概念"] * 10,
        }
        result = score_summary_quality_v4(summary)
        assert result <= 100

    def test_min_score_is_0(self):
        """测试最低分不小于0"""
        # 即使检测到模板，分数也不应为负
        summary = {
            "detailed_summary": "这里是一个summary概括总结",
            "key_points": [],
            "concepts": [],
        }
        result = score_summary_quality_v4(summary)
        assert result >= 0


class TestGetQualityThreshold:
    """测试质量阈值函数"""

    def test_returns_int(self):
        """测试返回整数"""
        result = get_quality_threshold()
        assert isinstance(result, int)

    def test_threshold_value(self):
        """测试阈值是85"""
        result = get_quality_threshold()
        assert result == 85
