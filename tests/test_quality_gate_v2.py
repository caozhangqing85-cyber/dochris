"""Layer 0 Provenance + Layer 1 Lint 单元测试"""

import json
import sys
from pathlib import Path

# 确保项目 src 可导入
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from dochris.quality.lint import (
    LintSeverity,
    lint_compile_result,
    lint_result_to_dict,
)
from dochris.quality.provenance import (
    ProvenanceLabel,
    _classify_concept,
    _find_in_source,
    compute_provenance,
    provenance_to_dict,
)

# ============================================================
# Layer 0: Provenance Tests
# ============================================================


class TestFindInSource:
    """源文本匹配测试"""

    def test_exact_match(self) -> None:
        result = _find_in_source("Transformer", "深度学习中的Transformer架构")
        assert result is not None
        assert "Transformer" in result

    def test_no_match(self) -> None:
        result = _find_in_source("量子计算", "深度学习中的Transformer架构")
        assert result is None

    def test_fuzzy_match_stripped(self) -> None:
        """去标点后能匹配"""
        result = _find_in_source("注意力机制", "自注意力机制。是一种重要方法")
        assert result is not None

    def test_short_text_no_match(self) -> None:
        """过短的文本不做模糊匹配"""
        result = _find_in_source("AB", "XYZ")
        assert result is None

    def test_empty_input(self) -> None:
        assert _find_in_source("", "source") is None
        assert _find_in_source("text", "") is None


class TestClassifyConcept:
    """概念分类测试"""

    def test_extracted_exact(self) -> None:
        cp = _classify_concept("Transformer", "一种架构", "Transformer是2017年提出的架构")
        assert cp.label == ProvenanceLabel.EXTRACTED
        assert cp.source_match is not None

    def test_inferred_partial(self) -> None:
        cp = _classify_concept("自注意力与编码器", "", "注意力机制和编码器-解码器结构")
        assert cp.label in (ProvenanceLabel.INFERRED, ProvenanceLabel.EXTRACTED)

    def test_ambiguous_no_match(self) -> None:
        cp = _classify_concept("量子纠缠", "量子物理现象", "这是一篇关于深度学习的文档")
        assert cp.label == ProvenanceLabel.AMBIGUOUS


class TestComputeProvenance:
    """综合溯源测试"""

    def _make_source(self, length: int = 500) -> str:
        return (
            "深度学习技术已经彻底改变了自然语言处理领域。"
            "Transformer架构引入了自注意力机制。"
            "BERT是一种双向编码器表示的预训练语言模型。"
        ) * max(1, length // 100)

    def _make_result(self) -> dict:
        return {
            "one_line": "深度学习在NLP中的应用",
            "key_points": ["Transformer架构", "自注意力机制", "BERT预训练"],
            "detailed_summary": "Transformer架构引入了自注意力机制，BERT是一种预训练模型。",
            "concepts": [
                {"name": "Transformer", "explanation": "一种架构"},
                {"name": "BERT", "explanation": "预训练模型"},
                {"name": "自注意力", "explanation": "注意力机制"},
            ],
        }

    def test_short_file_extracted(self) -> None:
        """短文件、概念在源文中 → extracted"""
        source = self._make_source(500)
        result = compute_provenance(self._make_result(), source)
        assert result.overall_label == ProvenanceLabel.EXTRACTED
        assert result.confidence == 0.9

    def test_long_file_merged(self) -> None:
        """长文件 → merged 倾向"""
        source = self._make_source(30000)  # > 20K
        result = compute_provenance(self._make_result(), source)
        # 长文件编译模式为 map_reduce，标签倾向 merged
        assert result.overall_label in (ProvenanceLabel.MERGED, ProvenanceLabel.EXTRACTED)

    def test_no_concepts_ambiguous(self) -> None:
        """无有效概念 → ambiguous"""
        result = compute_provenance({"one_line": "test", "detailed_summary": "x"}, "some source")
        assert result.overall_label == ProvenanceLabel.AMBIGUOUS

    def test_template_detected_ambiguous(self) -> None:
        """模板文字 → ambiguous"""
        result_dict = self._make_result()
        result_dict["detailed_summary"] = "本文档主要介绍了深度学习的概念。"
        source = self._make_source(500)
        prov = compute_provenance(result_dict, source)
        assert prov.overall_label == ProvenanceLabel.AMBIGUOUS

    def test_provenance_signals_populated(self) -> None:
        """信号列表不为空"""
        source = self._make_source(500)
        result = compute_provenance(self._make_result(), source)
        assert len(result.signals) > 0

    def test_to_dict_serializable(self) -> None:
        """to_dict 输出可 JSON 序列化"""
        source = self._make_source(500)
        result = compute_provenance(self._make_result(), source)
        d = provenance_to_dict(result)
        json_str = json.dumps(d, ensure_ascii=False)
        assert "overall_label" in json_str
        assert "confidence" in json_str


# ============================================================
# Layer 1: Lint Tests
# ============================================================


class TestLintCompleteness:
    """完整性检查测试"""

    def test_all_fields_present(self) -> None:
        result = lint_compile_result(
            {
                "one_line": "这是一个关于深度学习的摘要",
                "key_points": ["要点1", "要点2", "要点3"],
                "detailed_summary": "这是详细摘要，包含了多个要点和分析。" * 3,
                "concepts": [{"name": "深度学习"}, {"name": "NLP"}],
            }
        )
        assert result.passed
        assert result.error_count == 0

    def test_missing_one_line(self) -> None:
        result = lint_compile_result(
            {
                "key_points": ["要点1"],
                "detailed_summary": "内容" * 20,
            }
        )
        assert not result.passed
        assert any(
            i.rule == "completeness" and i.severity == LintSeverity.ERROR for i in result.issues
        )

    def test_missing_key_points(self) -> None:
        result = lint_compile_result(
            {
                "one_line": "测试摘要",
                "detailed_summary": "内容" * 20,
            }
        )
        assert not result.passed

    def test_missing_detailed_summary(self) -> None:
        result = lint_compile_result(
            {
                "one_line": "测试",
                "key_points": ["要点1"],
            }
        )
        assert not result.passed

    def test_one_line_too_short(self) -> None:
        result = lint_compile_result(
            {
                "one_line": "短",
                "key_points": ["要点1", "要点2"],
                "detailed_summary": "内容" * 20,
                "concepts": [{"name": "ML"}],
            }
        )
        assert any(i.rule == "completeness" and "过短" in i.message for i in result.issues)

    def test_empty_input(self) -> None:
        result = lint_compile_result({})
        assert not result.passed
        assert result.error_count >= 3  # at least 3 missing fields


class TestLintConceptDedup:
    """概念去重测试"""

    def test_case_insensitive_dup(self) -> None:
        result = lint_compile_result(
            {
                "one_line": "测试",
                "key_points": ["要点1"],
                "detailed_summary": "内容" * 20,
                "concepts": [
                    {"name": "Machine Learning"},
                    {"name": "machine learning"},
                ],
            }
        )
        dedup_issues = [i for i in result.issues if i.rule == "concept_dedup"]
        assert len(dedup_issues) == 1

    def test_whitespace_dup(self) -> None:
        result = lint_compile_result(
            {
                "one_line": "测试",
                "key_points": ["要点1"],
                "detailed_summary": "内容" * 20,
                "concepts": [
                    {"name": "深度学习"},
                    {"name": "深 度 学 习"},
                ],
            }
        )
        dedup_issues = [i for i in result.issues if i.rule == "concept_dedup"]
        assert len(dedup_issues) == 1

    def test_no_dup(self) -> None:
        result = lint_compile_result(
            {
                "one_line": "测试",
                "key_points": ["要点1"],
                "detailed_summary": "内容" * 20,
                "concepts": [
                    {"name": "Transformer"},
                    {"name": "BERT"},
                    {"name": "GPT"},
                ],
            }
        )
        dedup_issues = [i for i in result.issues if i.rule == "concept_dedup"]
        assert len(dedup_issues) == 0


class TestLintSelfReference:
    """自引用检测测试"""

    def test_self_ref_detected(self) -> None:
        result = lint_compile_result(
            {
                "one_line": "测试",
                "key_points": ["要点1"],
                "detailed_summary": "本文档介绍了深度学习的基础知识。",
                "concepts": [{"name": "DL"}],
            }
        )
        self_ref_issues = [i for i in result.issues if i.rule == "self_reference"]
        assert len(self_ref_issues) == 1

    def test_no_self_ref(self) -> None:
        result = lint_compile_result(
            {
                "one_line": "测试",
                "key_points": ["要点1"],
                "detailed_summary": "深度学习是机器学习的一个重要分支。",
                "concepts": [{"name": "DL"}],
            }
        )
        self_ref_issues = [i for i in result.issues if i.rule == "self_reference"]
        assert len(self_ref_issues) == 0


class TestLintCoverage:
    """覆盖率检查测试（仅大文件）"""

    def test_small_file_no_coverage_check(self) -> None:
        """小文件不检查覆盖率"""
        result = lint_compile_result(
            {"one_line": "测试", "key_points": ["要点1"], "detailed_summary": "内容" * 20},
            source_text="短文本",
        )
        coverage_issues = [i for i in result.issues if i.rule == "coverage"]
        assert len(coverage_issues) == 0

    def test_large_file_low_coverage(self) -> None:
        """大文件低覆盖率"""
        source = "\n\n".join([f"第{i}段内容，关于主题{i}的详细描述" * 5 for i in range(200)])
        result = lint_compile_result(
            {
                "one_line": "摘要",
                "key_points": ["要点1"],
                "detailed_summary": "完全不相关的摘要内容" * 10,
                "concepts": [{"name": "X"}],
            },
            source_text=source,
        )
        coverage_issues = [i for i in result.issues if i.rule == "coverage"]
        assert len(coverage_issues) >= 1


class TestLintConceptQuality:
    """概念质量检查测试"""

    def test_too_short_concept(self) -> None:
        result = lint_compile_result(
            {
                "one_line": "测试",
                "key_points": ["要点1"],
                "detailed_summary": "内容" * 20,
                "concepts": [{"name": "A"}],  # 1 字符
            }
        )
        quality_issues = [i for i in result.issues if i.rule == "concept_quality"]
        assert any("过短" in i.message for i in quality_issues)

    def test_default_explanation(self) -> None:
        result = lint_compile_result(
            {
                "one_line": "测试",
                "key_points": ["要点1"],
                "detailed_summary": "内容" * 20,
                "concepts": [{"name": "ML", "explanation": "详细解释请参阅原文"}],
            }
        )
        quality_issues = [i for i in result.issues if i.rule == "concept_quality"]
        assert any("默认解释" in i.message for i in quality_issues)
        # 默认解释应标记为 WARNING 级别（阻止晋升）
        default_issues = [i for i in quality_issues if "默认解释" in i.message]
        assert all(i.severity == LintSeverity.WARNING for i in default_issues)


class TestLintScore:
    """评分计算测试"""

    def test_perfect_score(self) -> None:
        result = lint_compile_result(
            {
                "one_line": "这是一个完整的单行摘要描述",
                "key_points": ["要点1", "要点2", "要点3"],
                "detailed_summary": "这是一段详细的摘要文本，包含了丰富的内容。" * 5,
                "concepts": [{"name": "概念A"}, {"name": "概念B"}],
            }
        )
        assert result.score == 1.0

    def test_error_reduces_score(self) -> None:
        result = lint_compile_result({})
        assert result.score < 0.5

    def test_warning_reduces_score(self) -> None:
        result = lint_compile_result(
            {
                "one_line": "短",
                "key_points": ["要点1"],
                "detailed_summary": "内容" * 20,
                "concepts": [
                    {"name": "ML"},
                    {"name": "ml"},  # 重复
                ],
            }
        )
        assert result.score < 1.0
        assert result.score > 0.0


class TestLintResultToDict:
    """序列化测试"""

    def test_json_roundtrip(self) -> None:
        result = lint_compile_result(
            {
                "one_line": "测试摘要",
                "key_points": ["要点1"],
                "detailed_summary": "内容" * 20,
                "concepts": [{"name": "ML"}, {"name": "ml"}],
            }
        )
        d = lint_result_to_dict(result)
        json_str = json.dumps(d, ensure_ascii=False)
        parsed = json.loads(json_str)
        assert parsed["passed"] == result.passed
        assert parsed["score"] == result.score
        assert len(parsed["issues"]) == len(result.issues)

    def test_non_dict_input(self) -> None:
        result = lint_compile_result("not a dict")  # type: ignore
        assert not result.passed
        assert result.error_count == 1


# ============================================================
# Integration: Provenance + Lint together
# ============================================================


class TestIntegration:
    """溯源 + Lint 联合测试"""

    def test_full_pipeline(self) -> None:
        """完整流水线：provenance + lint 正常工作"""
        source = (
            "深度学习是机器学习的一个重要分支。"
            "卷积神经网络（CNN）在图像识别中表现优异。"
            "循环神经网络（RNN）适合处理序列数据。"
            "Transformer架构通过自注意力机制实现了并行化。"
        ) * 10

        compile_result = {
            "one_line": "深度学习核心架构综述",
            "key_points": [
                "CNN在图像识别中的优势",
                "RNN处理序列数据的能力",
                "Transformer的自注意力机制",
            ],
            "detailed_summary": (
                "深度学习包括CNN、RNN和Transformer等核心架构。"
                "CNN通过卷积操作提取图像特征。"
                "RNN通过隐藏状态处理时序信息。"
                "Transformer通过自注意力实现全局建模。"
            ),
            "concepts": [
                {"name": "CNN", "explanation": "卷积神经网络"},
                {"name": "RNN", "explanation": "循环神经网络"},
                {"name": "Transformer", "explanation": "自注意力架构"},
            ],
        }

        # Provenance
        prov = compute_provenance(compile_result, source)
        assert prov.overall_label == ProvenanceLabel.EXTRACTED
        assert len(prov.concepts) == 3

        # Lint
        lint = lint_compile_result(compile_result, source)
        assert lint.passed
        assert lint.score == 1.0

        # Serialization
        prov_dict = provenance_to_dict(prov)
        lint_dict = lint_result_to_dict(lint)
        json.dumps({"provenance": prov_dict, "lint": lint_dict}, ensure_ascii=False)

    def test_large_file_merged_provenance(self) -> None:
        """大文件 → merged 标签"""
        # 30K 源文本
        source = ("深度学习技术综述。" * 100 + "\n\n") * 50

        compile_result = {
            "one_line": "深度学习综述",
            "key_points": ["技术1", "技术2"],
            "detailed_summary": "综合了多种深度学习技术的综述。",
            "concepts": [{"name": "深度学习"}],
        }

        prov = compute_provenance(compile_result, source)
        assert prov.overall_label in (ProvenanceLabel.MERGED, ProvenanceLabel.EXTRACTED)
