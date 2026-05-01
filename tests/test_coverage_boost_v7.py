"""覆盖率提升 v7 — cli_review 延迟 import + retry_manager + summary_generator"""

from unittest.mock import MagicMock, patch


# ============================================================
# cli_review.py — 通过 patch 内部调用来覆盖分支
# ============================================================
class TestCliReviewPromote:
    def test_promote_gate_fail(self, tmp_path):
        from dochris.cli.cli_review import cmd_promote
        args = MagicMock(src_id="src_001", to="wiki")
        with patch("dochris.settings.get_default_workspace", return_value=tmp_path), \
             patch("dochris.quality.quality_gate.quality_gate", return_value={"passed": False, "reason": "low"}):
            assert cmd_promote(args) == 1

    def test_promote_wiki_ok(self, tmp_path):
        from dochris.cli.cli_review import cmd_promote
        args = MagicMock(src_id="src_001", to="wiki")
        with patch("dochris.settings.get_default_workspace", return_value=tmp_path), \
             patch("dochris.quality.quality_gate.quality_gate", return_value={"passed": True, "quality_score": 90}), \
             patch("dochris.promote.promote_to_wiki", return_value=True):
            assert cmd_promote(args) == 0

    def test_promote_wiki_fail(self, tmp_path):
        from dochris.cli.cli_review import cmd_promote
        args = MagicMock(src_id="src_001", to="wiki")
        with patch("dochris.settings.get_default_workspace", return_value=tmp_path), \
             patch("dochris.quality.quality_gate.quality_gate", return_value={"passed": True, "quality_score": 90}), \
             patch("dochris.promote.promote_to_wiki", return_value=False):
            assert cmd_promote(args) == 1

    def test_promote_curated_ok(self, tmp_path):
        from dochris.cli.cli_review import cmd_promote
        args = MagicMock(src_id="src_001", to="curated")
        with patch("dochris.settings.get_default_workspace", return_value=tmp_path), \
             patch("dochris.quality.quality_gate.quality_gate", return_value={"passed": True, "quality_score": 90}), \
             patch("dochris.promote.promote_to_curated", return_value=True):
            assert cmd_promote(args) == 0

    def test_promote_unknown_target(self, tmp_path):
        from dochris.cli.cli_review import cmd_promote
        args = MagicMock(src_id="src_001", to="invalid")
        with patch("dochris.settings.get_default_workspace", return_value=tmp_path), \
             patch("dochris.quality.quality_gate.quality_gate", return_value={"passed": True, "quality_score": 90}):
            assert cmd_promote(args) == 1


class TestCliReviewQuality:
    def test_quality_report(self, tmp_path):
        from dochris.cli.cli_review import cmd_quality
        args = MagicMock(report=True, check_pollution=False, src_id=None)
        with patch("dochris.settings.get_default_workspace", return_value=tmp_path), \
             patch("dochris.quality.quality_gate.generate_report", return_value={"total": 10}):
            assert cmd_quality(args) == 0

    def test_quality_pollution_yes(self, tmp_path):
        from dochris.cli.cli_review import cmd_quality
        args = MagicMock(report=False, check_pollution=True, src_id=None)
        with patch("dochris.settings.get_default_workspace", return_value=tmp_path), \
             patch("dochris.quality.quality_gate.check_pollution", return_value={"polluted": True, "details": "bad"}):
            assert cmd_quality(args) == 1

    def test_quality_pollution_no(self, tmp_path):
        from dochris.cli.cli_review import cmd_quality
        args = MagicMock(report=False, check_pollution=True, src_id=None)
        with patch("dochris.settings.get_default_workspace", return_value=tmp_path), \
             patch("dochris.quality.quality_gate.check_pollution", return_value={"polluted": False}):
            assert cmd_quality(args) == 0

    def test_quality_src_id_pass(self, tmp_path):
        from dochris.cli.cli_review import cmd_quality
        args = MagicMock(report=False, check_pollution=False, src_id="src_001")
        with patch("dochris.settings.get_default_workspace", return_value=tmp_path), \
             patch("dochris.quality.quality_gate.quality_gate", return_value={"passed": True, "src_id": "S1", "title": "T"}):
            assert cmd_quality(args) == 0

    def test_quality_src_id_fail(self, tmp_path):
        from dochris.cli.cli_review import cmd_quality
        args = MagicMock(report=False, check_pollution=False, src_id="src_001")
        with patch("dochris.settings.get_default_workspace", return_value=tmp_path), \
             patch("dochris.quality.quality_gate.quality_gate", return_value={"passed": False, "reason": "low"}):
            assert cmd_quality(args) == 1

    def test_quality_scan_wiki(self, tmp_path):
        from dochris.cli.cli_review import cmd_quality
        args = MagicMock(report=False, check_pollution=False, src_id=None)
        with patch("dochris.settings.get_default_workspace", return_value=tmp_path), \
             patch("dochris.quality.quality_gate.scan_wiki", return_value={"wiki_summaries": 5, "wiki_concepts": 3, "wiki_total": 8}):
            assert cmd_quality(args) == 0


# ============================================================
# summary_generator — generate_summary 覆盖
# ============================================================
# summary_generator 已有充分测试，此处不再重复
