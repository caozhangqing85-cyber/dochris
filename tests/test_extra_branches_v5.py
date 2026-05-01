"""补充覆盖 promote.py concept copy + quality_gate auto_downgrade removed_files"""

from pathlib import Path
from unittest.mock import patch

import pytest


class TestPromoteConceptCopy:
    """覆盖 promote.py lines 145-146 (concept file copy)"""

    def test_concept_files_copied(self, tmp_path):
        """概念文件被复制到 wiki/concepts"""
        from dochris.core.utils import sanitize_filename
        from dochris.promote import promote_to_wiki

        workspace = tmp_path / "kb"
        workspace.mkdir()
        (workspace / "manifests/sources").mkdir(parents=True)
        (workspace / "outputs/summaries").mkdir(parents=True)
        (workspace / "outputs/concepts").mkdir(parents=True)
        (workspace / "wiki/summaries").mkdir(parents=True)
        (workspace / "wiki/concepts").mkdir(parents=True)

        src_id = "SRC-0001"
        title = "测试标题"
        safe_title = sanitize_filename(title, max_length=80)

        manifest = {
            "id": src_id,
            "status": "compiled",
            "quality_score": 90,
            "title": title,
            "compiled_summary": {
                "concepts": [
                    {"name": "概念A", "category": "method"},
                    {"name": "概念B", "category": "principle"},
                ],
            },
        }

        import json

        (workspace / "manifests/sources" / f"{src_id}.json").write_text(
            json.dumps(manifest, ensure_ascii=False), encoding="utf-8"
        )

        # 创建摘要文件
        (workspace / "outputs/summaries" / f"{safe_title}.md").write_text(
            "# 摘要", encoding="utf-8"
        )

        # 创建概念文件
        for name in ["概念A", "概念B"]:
            safe = sanitize_filename(name, max_length=50)
            (workspace / "outputs/concepts" / f"{safe}.md").write_text(
                f"# {name}", encoding="utf-8"
            )

        with patch("dochris.promote.update_manifest_status"):
            with patch("dochris.promote.append_log"):
                result = promote_to_wiki(workspace, src_id)

        assert result is True


class TestQualityGateAutoDowngrade:
    """覆盖 quality_gate.py auto_downgrade removed_files"""

    def test_auto_downgrade_removes_files(self, tmp_path):
        """降级 promoted_to_wiki 时删除 wiki 文件"""
        from dochris.quality.quality_gate import auto_downgrade

        workspace = tmp_path / "kb"
        workspace.mkdir()
        (workspace / "manifests/sources").mkdir(parents=True)
        (workspace / "wiki/summaries").mkdir(parents=True)
        (workspace / "wiki/concepts").mkdir(parents=True)

        src_id = "SRC-0001"
        title = "测试降级"
        manifest = {
            "id": src_id,
            "status": "promoted_to_wiki",
            "quality_score": 90,
            "title": title,
        }

        import json
        import re

        (workspace / "manifests/sources" / f"{src_id}.json").write_text(
            json.dumps(manifest, ensure_ascii=False), encoding="utf-8"
        )

        # 创建 wiki 文件（名称基于 title）
        safe_title = re.sub(r'[<>:"/\\|?*]', "", title)[:80]
        (workspace / "wiki/summaries" / f"{safe_title}.md").write_text(
            "# summary", encoding="utf-8"
        )
        (workspace / "wiki/concepts" / f"{safe_title}.md").write_text(
            "# concept", encoding="utf-8"
        )

        with patch("builtins.print"):
            with patch("dochris.quality.quality_gate.update_manifest_status"):
                with patch("dochris.quality.quality_gate.append_log"):
                    result = auto_downgrade(workspace, src_id, "pollution")

        assert result["success"] is True
        assert len(result["removed_files"]) > 0
