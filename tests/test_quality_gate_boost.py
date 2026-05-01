"""quality_gate.py 覆盖率提升测试 — 覆盖 main() 和复杂分支"""

from unittest.mock import patch

import pytest


class TestCheckPollutionBranches:
    """污染检测的边界情况"""

    def test_no_wiki_dirs(self, tmp_path):
        """workspace 没有 wiki 目录"""
        from dochris.quality.quality_gate import check_pollution

        result = check_pollution(tmp_path)
        assert result["polluted"] is False
        assert result["polluted_count"] == 0

    def test_empty_manifests_clean(self, tmp_path):
        """manifest 为空，wiki 中有文件 = 全部污染"""
        from dochris.quality.quality_gate import check_pollution

        (tmp_path / "wiki" / "summaries").mkdir(parents=True)
        (tmp_path / "wiki" / "concepts").mkdir(parents=True)
        (tmp_path / "wiki" / "summaries" / "orphan.md").write_text("test")

        with patch("dochris.quality.quality_gate.get_all_manifests", return_value=[]):
            result = check_pollution(tmp_path)
            assert result["polluted"] is True
            assert result["polluted_count"] == 1

    def test_all_promoted_clean(self, tmp_path):
        """所有文件都已 promote = 干净"""
        from dochris.quality.quality_gate import check_pollution

        (tmp_path / "wiki" / "summaries").mkdir(parents=True)
        (tmp_path / "wiki" / "concepts").mkdir(parents=True)
        (tmp_path / "wiki" / "summaries" / "test.md").write_text("test")

        manifest = {
            "status": "promoted_to_wiki",
            "title": "test",
            "compiled_summary": {
                "concepts": []
            },
        }
        with patch("dochris.quality.quality_gate.get_all_manifests", return_value=[manifest]):
            result = check_pollution(tmp_path)
            assert result["polluted"] is False

    def test_mixed_status_only_promoted_counted(self, tmp_path):
        """只统计 promoted 和 promoted_to_wiki 状态"""
        from dochris.quality.quality_gate import check_pollution

        (tmp_path / "wiki" / "summaries").mkdir(parents=True)
        (tmp_path / "wiki" / "summaries" / "compiled_only.md").write_text("x")

        manifest = {
            "status": "compiled",  # 不应该被计入 promoted
            "title": "compiled_only",
        }
        with patch("dochris.quality.quality_gate.get_all_manifests", return_value=[manifest]):
            result = check_pollution(tmp_path)
            assert result["polluted"] is True

    def test_concept_extraction_from_manifest(self, tmp_path):
        """测试从 manifest 的 compiled_summary 中提取概念"""
        from dochris.quality.quality_gate import check_pollution

        (tmp_path / "wiki" / "summaries").mkdir(parents=True)
        (tmp_path / "wiki" / "concepts").mkdir(parents=True)
        (tmp_path / "wiki" / "concepts" / "AI Agent.md").write_text("x")

        manifest = {
            "status": "promoted",
            "title": "test doc",
            "compiled_summary": {
                "concepts": [
                    {"name": "AI Agent"},
                    "string_concept",  # 非dict形式
                ]
            },
        }
        with patch("dochris.quality.quality_gate.get_all_manifests", return_value=[manifest]):
            result = check_pollution(tmp_path)
            assert result["polluted"] is False

    def test_title_with_special_chars(self, tmp_path):
        """标题包含特殊字符被清理"""
        from dochris.quality.quality_gate import check_pollution

        (tmp_path / "wiki" / "summaries").mkdir(parents=True)
        (tmp_path / "wiki" / "summaries" / "testspecial.md").write_text("x")

        manifest = {
            "status": "promoted",
            "title": 'test<>"special',
            "compiled_summary": {"concepts": []},
        }
        with patch("dochris.quality.quality_gate.get_all_manifests", return_value=[manifest]):
            result = check_pollution(tmp_path)
            assert result["polluted"] is False


class TestQualityGateBranches:
    """质量门禁的各种分支"""

    def test_manifest_not_found(self, tmp_path):
        from dochris.quality.quality_gate import quality_gate

        with patch("dochris.quality.quality_gate.get_manifest", return_value=None):
            result = quality_gate(tmp_path, "nonexistent")
            assert result["passed"] is False
            assert "未找到" in result["reason"]

    def test_all_checks_pass(self, tmp_path):
        from dochris.quality.quality_gate import quality_gate

        manifest = {
            "status": "compiled",
            "quality_score": 90,
            "error_message": None,
            "summary": "test summary",
            "title": "Test Doc",
        }
        with patch("dochris.quality.quality_gate.get_manifest", return_value=manifest):
            result = quality_gate(tmp_path, "src_001")
            assert result["passed"] is True
            assert result["reason"] == "通过"

    def test_status_not_compiled(self, tmp_path):
        from dochris.quality.quality_gate import quality_gate

        manifest = {
            "status": "ingested",
            "quality_score": 90,
            "error_message": None,
            "summary": "test",
        }
        with patch("dochris.quality.quality_gate.get_manifest", return_value=manifest):
            result = quality_gate(tmp_path, "src_001")
            assert result["passed"] is False
            assert "状态" in result["reason"]

    def test_score_below_threshold(self, tmp_path):
        from dochris.quality.quality_gate import quality_gate

        manifest = {
            "status": "compiled",
            "quality_score": 50,
            "error_message": None,
            "summary": "test",
        }
        with patch("dochris.quality.quality_gate.get_manifest", return_value=manifest):
            result = quality_gate(tmp_path, "src_001", min_score=85)
            assert result["passed"] is False
            assert "分数" in result["reason"]

    def test_has_error_message(self, tmp_path):
        from dochris.quality.quality_gate import quality_gate

        manifest = {
            "status": "compiled",
            "quality_score": 90,
            "error_message": "timeout",
            "summary": "test",
        }
        with patch("dochris.quality.quality_gate.get_manifest", return_value=manifest):
            result = quality_gate(tmp_path, "src_001")
            assert result["passed"] is False
            assert "错误" in result["reason"]

    def test_missing_summary(self, tmp_path):
        from dochris.quality.quality_gate import quality_gate

        manifest = {
            "status": "compiled",
            "quality_score": 90,
            "error_message": None,
            "summary": None,
        }
        with patch("dochris.quality.quality_gate.get_manifest", return_value=manifest):
            result = quality_gate(tmp_path, "src_001")
            assert result["passed"] is False
            assert "summary" in result["reason"]

    def test_multiple_failures(self, tmp_path):
        """多项检查同时失败"""
        from dochris.quality.quality_gate import quality_gate

        manifest = {
            "status": "ingested",
            "quality_score": 30,
            "error_message": "failed",
            "summary": None,
        }
        with patch("dochris.quality.quality_gate.get_manifest", return_value=manifest):
            result = quality_gate(tmp_path, "src_001")
            assert result["passed"] is False
            assert len(result["reason"].split(";")) >= 3


class TestAutoDowngradeBranches:
    """自动降级的各种分支"""

    def test_manifest_not_found(self, tmp_path):
        from dochris.quality.quality_gate import auto_downgrade

        with patch("dochris.quality.quality_gate.get_manifest", return_value=None):
            result = auto_downgrade(tmp_path, "nonexistent")
            assert result["success"] is False

    def test_invalid_status(self, tmp_path):
        from dochris.quality.quality_gate import auto_downgrade

        manifest = {"status": "ingested", "title": "test"}
        with patch("dochris.quality.quality_gate.get_manifest", return_value=manifest):
            result = auto_downgrade(tmp_path, "src_001")
            assert result["success"] is False
            assert "无法从" in result["reason"]

    def test_downgrade_promoted_to_wiki(self, tmp_path):
        """promoted → promoted_to_wiki，移除 wiki 文件"""
        from dochris.quality.quality_gate import auto_downgrade

        (tmp_path / "wiki" / "summaries").mkdir(parents=True)
        (tmp_path / "wiki" / "concepts").mkdir(parents=True)
        (tmp_path / "curated" / "promoted").mkdir(parents=True)
        (tmp_path / "wiki" / "summaries" / "Test Doc.md").write_text("x")

        manifest = {"status": "promoted", "title": "Test Doc", "promoted_to": "wiki"}
        with patch("dochris.quality.quality_gate.get_manifest", return_value=manifest), \
             patch("dochris.quality.quality_gate.update_manifest_status"):
            result = auto_downgrade(tmp_path, "src_001")
            assert result["success"] is True
            assert result["from_status"] == "promoted"
            assert result["to_status"] == "promoted_to_wiki"
            assert len(result["removed_files"]) >= 1

    def test_downgrade_promoted_to_wiki_to_compiled(self, tmp_path):
        """promoted_to_wiki → compiled，移除 wiki 文件"""
        from dochris.quality.quality_gate import auto_downgrade

        (tmp_path / "wiki" / "summaries").mkdir(parents=True)
        (tmp_path / "wiki" / "summaries" / "Test Doc.md").write_text("x")

        manifest = {"status": "promoted_to_wiki", "title": "Test Doc"}
        with patch("dochris.quality.quality_gate.get_manifest", return_value=manifest), \
             patch("dochris.quality.quality_gate.update_manifest_status"):
            result = auto_downgrade(tmp_path, "src_001")
            assert result["success"] is True
            assert result["to_status"] == "compiled"

    def test_downgrade_compiled_to_ingested(self, tmp_path):
        """compiled → ingested，不移除 wiki 文件"""
        from dochris.quality.quality_gate import auto_downgrade

        manifest = {"status": "compiled", "title": "Test Doc"}
        with patch("dochris.quality.quality_gate.get_manifest", return_value=manifest), \
             patch("dochris.quality.quality_gate.update_manifest_status"):
            result = auto_downgrade(tmp_path, "src_001")
            assert result["success"] is True
            assert result["to_status"] == "ingested"
            assert len(result["removed_files"]) == 0


class TestScanWikiAndReport:
    """扫描和报告生成"""

    def test_scan_empty_workspace(self, tmp_path):
        from dochris.quality.quality_gate import scan_wiki

        with patch("dochris.quality.quality_gate.get_all_manifests", return_value=[]):
            result = scan_wiki(tmp_path)
            assert result["wiki_summaries"] == 0
            assert result["wiki_concepts"] == 0
            assert result["manifest_total"] == 0

    def test_scan_with_files(self, tmp_path):
        from dochris.quality.quality_gate import scan_wiki

        (tmp_path / "wiki" / "summaries").mkdir(parents=True)
        (tmp_path / "wiki" / "concepts").mkdir(parents=True)
        (tmp_path / "wiki" / "summaries" / "a.md").write_text("x")
        (tmp_path / "wiki" / "summaries" / "b.md").write_text("x")
        (tmp_path / "wiki" / "concepts" / "c.md").write_text("x")

        manifests = [
            {"status": "compiled"},
            {"status": "compiled"},
            {"status": "promoted"},
        ]
        with patch("dochris.quality.quality_gate.get_all_manifests", return_value=manifests):
            result = scan_wiki(tmp_path)
            assert result["wiki_summaries"] == 2
            assert result["wiki_concepts"] == 1
            assert result["wiki_total"] == 3
            assert result["manifest_total"] == 3

    def test_generate_report(self, tmp_path):
        from dochris.quality.quality_gate import generate_report

        manifests = [
            {"status": "compiled", "quality_score": 90, "title": "A"},
            {"status": "compiled", "quality_score": 50, "title": "B"},
            {"status": "compiled", "quality_score": 30, "title": "C"},
            {"status": "compiled", "quality_score": 70, "title": "D"},
        ]
        with patch("dochris.quality.quality_gate.get_all_manifests", return_value=manifests):
            report = generate_report(tmp_path)
            assert report["trust_model"] == "四层信任模型"
            assert "layers" in report
            assert report["score_distribution"]["0-40"] == 1
            assert report["score_distribution"]["41-60"] == 1
            assert report["score_distribution"]["61-84"] == 1
            assert report["score_distribution"]["85-100"] == 1
            assert report["promotable_count"] >= 1

    def test_generate_report_promotable(self, tmp_path):
        """只统计满足 promote 条件的 manifest"""
        from dochris.quality.quality_gate import generate_report

        manifests = [
            {"status": "compiled", "quality_score": 90, "title": "Good"},
            {"status": "compiled", "quality_score": 30, "title": "Bad"},
            {"status": "ingested", "quality_score": 95, "title": "NotCompiled"},
        ]
        with patch("dochris.quality.quality_gate.get_all_manifests", return_value=manifests):
            report = generate_report(tmp_path)
            assert report["promotable_count"] == 1


class TestMainCLI:
    """CLI main() 函数的分支覆盖"""

    def test_no_args(self, tmp_path):
        from dochris.quality.quality_gate import main

        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 1

    def test_unknown_command(self, tmp_path):
        from dochris.quality.quality_gate import main

        with patch("sys.argv", ["quality_gate.py", str(tmp_path), "unknown"]):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 1

    def test_check_pollution_clean(self, tmp_path):
        from dochris.quality.quality_gate import main

        (tmp_path / "wiki" / "summaries").mkdir(parents=True)
        (tmp_path / "wiki" / "concepts").mkdir(parents=True)

        with patch("sys.argv", ["quality_gate.py", str(tmp_path), "check-pollution"]), \
             patch("dochris.quality.quality_gate.get_all_manifests", return_value=[]), \
             patch("dochris.quality.quality_gate.append_log"):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 0

    def test_check_pollution_dirty(self, tmp_path):
        from dochris.quality.quality_gate import main

        (tmp_path / "wiki" / "summaries").mkdir(parents=True)
        (tmp_path / "wiki" / "summaries" / "orphan.md").write_text("x")

        with patch("sys.argv", ["quality_gate.py", str(tmp_path), "check-pollution"]), \
             patch("dochris.quality.quality_gate.get_all_manifests", return_value=[]), \
             patch("dochris.quality.quality_gate.append_log"):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 1

    def test_quality_gate_pass(self, tmp_path):
        from dochris.quality.quality_gate import main

        manifest = {
            "status": "compiled",
            "quality_score": 90,
            "error_message": None,
            "summary": "test",
            "title": "Test",
        }
        with patch("sys.argv", ["quality_gate.py", str(tmp_path), "quality-gate", "src_001"]), \
             patch("dochris.quality.quality_gate.get_manifest", return_value=manifest), \
             patch("dochris.quality.quality_gate.append_log"):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 0

    def test_quality_gate_reject(self, tmp_path):
        from dochris.quality.quality_gate import main

        manifest = {
            "status": "compiled",
            "quality_score": 30,
            "error_message": None,
            "summary": "test",
        }
        with patch("sys.argv", ["quality_gate.py", str(tmp_path), "quality-gate", "src_001"]), \
             patch("dochris.quality.quality_gate.get_manifest", return_value=manifest), \
             patch("dochris.quality.quality_gate.append_log"):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 1

    def test_quality_gate_missing_src_id(self, tmp_path):
        from dochris.quality.quality_gate import main

        with patch("sys.argv", ["quality_gate.py", str(tmp_path), "quality-gate"]):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 1

    def test_auto_downgrade_success(self, tmp_path):
        from dochris.quality.quality_gate import main

        manifest = {"status": "compiled", "title": "Test"}
        with patch("sys.argv", ["quality_gate.py", str(tmp_path), "auto-downgrade", "src_001"]), \
             patch("dochris.quality.quality_gate.get_manifest", return_value=manifest), \
             patch("dochris.quality.quality_gate.update_manifest_status"), \
             patch("dochris.quality.quality_gate.append_log"):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 0

    def test_auto_downgrade_fail(self, tmp_path):
        from dochris.quality.quality_gate import main

        with patch("sys.argv", ["quality_gate.py", str(tmp_path), "auto-downgrade", "src_001"]), \
             patch("dochris.quality.quality_gate.get_manifest", return_value=None):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 1

    def test_auto_downgrade_with_reason(self, tmp_path):
        from dochris.quality.quality_gate import main

        manifest = {"status": "compiled", "title": "Test"}
        with patch("sys.argv", ["quality_gate.py", str(tmp_path), "auto-downgrade", "src_001", "--reason", "manual review"]), \
             patch("dochris.quality.quality_gate.get_manifest", return_value=manifest), \
             patch("dochris.quality.quality_gate.update_manifest_status"), \
             patch("dochris.quality.quality_gate.append_log"):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 0

    def test_auto_downgrade_missing_src_id(self, tmp_path):
        from dochris.quality.quality_gate import main

        with patch("sys.argv", ["quality_gate.py", str(tmp_path), "auto-downgrade"]):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 1

    def test_scan_wiki(self, tmp_path):
        from dochris.quality.quality_gate import main

        (tmp_path / "wiki" / "summaries").mkdir(parents=True)
        (tmp_path / "wiki" / "concepts").mkdir(parents=True)

        with patch("sys.argv", ["quality_gate.py", str(tmp_path), "scan-wiki"]), \
             patch("dochris.quality.quality_gate.get_all_manifests", return_value=[]), \
             patch("dochris.quality.quality_gate.append_log"):
            main()  # scan-wiki doesn't sys.exit

    def test_report(self, tmp_path):
        from dochris.quality.quality_gate import main

        with patch("sys.argv", ["quality_gate.py", str(tmp_path), "report"]), \
             patch("dochris.quality.quality_gate.get_all_manifests", return_value=[]), \
             patch("dochris.quality.quality_gate.append_log"):
            main()  # report doesn't sys.exit
