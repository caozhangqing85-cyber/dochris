"""补充测试 vault/bridge.py — 覆盖 _search_obsidian_notes + promote_to_obsidian 分支"""

import re
from unittest.mock import patch


class TestSearchObsidianNotes:
    """覆盖 _search_obsidian_notes 的 vault=None/vault missing + keyword + content match"""

    def test_search_no_vault(self):
        """vault 未配置返回空列表"""
        from dochris.vault.bridge import _search_obsidian_notes

        with patch("dochris.vault.bridge._get_obsidian_vault", return_value=None):
            result = _search_obsidian_notes("测试主题")

        assert result == []

    def test_search_vault_not_exists(self, tmp_path):
        """vault 路径不存在返回空列表"""
        from dochris.vault.bridge import _search_obsidian_notes

        fake_vault = tmp_path / "nonexistent"
        with patch("dochris.vault.bridge._get_obsidian_vault", return_value=fake_vault):
            result = _search_obsidian_notes("测试主题")

        assert result == []

    def test_search_with_content_match(self, tmp_path):
        """文件内容匹配关键词"""
        from dochris.vault.bridge import _search_obsidian_notes

        vault = tmp_path / "vault"
        vault.mkdir()
        md = vault / "notes.md"
        md.write_text("# 笔记\n\n这里有一些关于机器学习的内容", encoding="utf-8")

        with patch("dochris.vault.bridge._get_obsidian_vault", return_value=vault):
            result = _search_obsidian_notes("机器学习")

        assert len(result) == 1
        assert result[0]["match_type"] == "content"

    def test_search_short_keyword_fallback(self, tmp_path):
        """短关键词回退到完整 topic"""
        from dochris.vault.bridge import _search_obsidian_notes

        vault = tmp_path / "vault"
        vault.mkdir()
        md = vault / "测试.md"
        md.write_text("# 测试笔记\n\na的内容", encoding="utf-8")

        with patch("dochris.vault.bridge._get_obsidian_vault", return_value=vault):
            result = _search_obsidian_notes("a")

        assert isinstance(result, list)

    def test_search_filename_match_before_content(self, tmp_path):
        """文件名匹配优先于内容匹配"""
        from dochris.vault.bridge import _search_obsidian_notes

        vault = tmp_path / "vault"
        vault.mkdir()
        md = vault / "机器学习笔记.md"
        md.write_text("# ML\n\n这是机器学习笔记", encoding="utf-8")

        with patch("dochris.vault.bridge._get_obsidian_vault", return_value=vault):
            result = _search_obsidian_notes("机器学习")

        assert len(result) >= 1
        assert result[0]["match_type"] == "filename"


class TestPromoteToObsidian:
    """覆盖 promote_to_obsidian 的各种失败/成功路径"""

    def test_promote_manifest_not_found(self, tmp_path):
        """manifest 不存在"""
        from dochris.vault.bridge import promote_to_obsidian

        workspace = tmp_path / "ws"
        workspace.mkdir()

        with patch("dochris.vault.bridge.get_manifest", return_value=None):
            with patch("builtins.print"):
                result = promote_to_obsidian(workspace, "SRC-0001")

        assert result is False

    def test_promote_wrong_status(self, tmp_path):
        """manifest 状态不正确"""
        from dochris.vault.bridge import promote_to_obsidian

        workspace = tmp_path / "ws"
        workspace.mkdir()

        manifest = {"status": "compiled", "title": "Test"}
        with patch("dochris.vault.bridge.get_manifest", return_value=manifest):
            with patch("builtins.print"):
                result = promote_to_obsidian(workspace, "SRC-0001")

        assert result is False

    def test_promote_no_title(self, tmp_path):
        """manifest 缺少 title"""
        from dochris.vault.bridge import promote_to_obsidian

        workspace = tmp_path / "ws"
        workspace.mkdir()

        manifest = {"status": "promoted", "title": ""}
        with patch("dochris.vault.bridge.get_manifest", return_value=manifest):
            with patch("builtins.print"):
                result = promote_to_obsidian(workspace, "SRC-0001")

        assert result is False

    def test_promote_no_source_file(self, tmp_path):
        """找不到产物文件 - workspace 没有候选目录"""
        from dochris.vault.bridge import promote_to_obsidian

        workspace = tmp_path / "ws"
        workspace.mkdir()

        manifest = {"status": "promoted", "title": "Nonexistent Title"}
        with patch("dochris.vault.bridge.get_manifest", return_value=manifest):
            with patch("builtins.print"):
                result = promote_to_obsidian(workspace, "SRC-0001")

        assert result is False

    def test_promote_read_error(self, tmp_path):
        """读取产物文件失败"""
        from dochris.vault.bridge import promote_to_obsidian

        workspace = tmp_path / "ws"
        (workspace / "wiki" / "summaries").mkdir(parents=True)

        title = "Test Title"
        safe_title = re.sub(r'[<>:"/\\|?*]', "", title)[:80]
        source_file = workspace / "wiki" / "summaries" / f"{safe_title}.md"
        source_file.write_text("content", encoding="utf-8")

        manifest = {"status": "promoted", "title": title}

        with patch("dochris.vault.bridge.get_manifest", return_value=manifest):
            with patch("pathlib.Path.read_text", side_effect=OSError("read error")):
                with patch("builtins.print"):
                    result = promote_to_obsidian(workspace, "SRC-0001")

        assert result is False

    def test_promote_vault_missing(self, tmp_path):
        """Obsidian vault 不存在"""
        from dochris.vault.bridge import promote_to_obsidian

        workspace = tmp_path / "ws"
        (workspace / "wiki" / "summaries").mkdir(parents=True)

        title = "Test Title"
        safe_title = re.sub(r'[<>:"/\\|?*]', "", title)[:80]
        source_file = workspace / "wiki" / "summaries" / f"{safe_title}.md"
        source_file.write_text("content", encoding="utf-8")

        manifest = {"status": "promoted", "title": title}

        with patch("dochris.vault.bridge.get_manifest", return_value=manifest):
            with patch("dochris.vault.bridge._get_obsidian_vault", return_value=None):
                with patch("builtins.print"):
                    result = promote_to_obsidian(workspace, "SRC-0001")

        assert result is False

    def test_promote_rename_conflict(self, tmp_path):
        """目标文件已存在时重命名"""
        from dochris.vault.bridge import promote_to_obsidian

        workspace = tmp_path / "ws"
        (workspace / "wiki" / "summaries").mkdir(parents=True)

        vault = tmp_path / "vault"
        vault.mkdir()
        target_dir = vault / "06-知识库"
        target_dir.mkdir(parents=True)

        title = "Unique Title X"
        safe_title = re.sub(r'[<>:"/\\|?*]', "", title)[:80]
        source_file = workspace / "wiki" / "summaries" / f"{safe_title}.md"
        source_file.write_text("new content", encoding="utf-8")

        # 创建已存在的同名文件
        (target_dir / f"{safe_title}.md").write_text("existing", encoding="utf-8")

        manifest = {"status": "promoted", "title": title}

        with patch("dochris.vault.bridge.get_manifest", return_value=manifest):
            with patch("dochris.vault.bridge._get_obsidian_vault", return_value=vault):
                with patch("dochris.manifest.update_manifest_status"):
                    with patch("dochris.log.append_log"):
                        with patch("builtins.print"):
                            result = promote_to_obsidian(workspace, "SRC-0001")

        assert result is True
        assert (target_dir / f"{safe_title}_1.md").exists()
