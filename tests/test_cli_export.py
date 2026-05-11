"""测试 kb export manifest 匹配"""

import json


def test_build_manifest_matches_src_id_output(tmp_path):
    """导出 SRC-ID 命名产物时能匹配 manifest 状态"""
    from dochris.cli.cli_export import _build_manifest

    workspace = tmp_path / "workspace"
    manifests = workspace / "manifests" / "sources"
    summaries = workspace / "outputs" / "summaries"
    manifests.mkdir(parents=True)
    summaries.mkdir(parents=True)

    (manifests / "SRC-0001.json").write_text(
        json.dumps(
            {
                "id": "SRC-0001",
                "title": "测试文档.pdf",
                "file_path": "raw/pdfs/source.pdf",
                "status": "compiled",
                "quality_score": 91,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    output = summaries / "SRC-0001.md"
    output.write_text("# 测试", encoding="utf-8")

    rows = _build_manifest([("outputs/summaries/SRC-0001.md", output)], workspace)

    assert rows[0]["status"] == "compiled"
    assert rows[0]["quality_score"] == "91"
