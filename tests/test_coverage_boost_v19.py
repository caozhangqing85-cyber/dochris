"""覆盖率提升 v19 — settings/config edge cases + quality_gate CLI + faiss_store + batch_promote CLI"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


# ============================================================
# settings/config.py — uncovered: 20-27, 232-233, 244, 246, 416, 421-422
# ============================================================
class TestConfigFromEnv:
    """Test Settings.from_env edge cases"""

    def test_from_env_loads_custom_env_file(self, tmp_path, monkeypatch):
        """from_env loads a custom .env file (line 232-233)"""
        env_file = tmp_path / ".env"
        env_file.write_text("OPENAI_API_KEY=test-key-xyz\nMODEL=test-model\n", encoding="utf-8")

        for k in ["OPENAI_API_KEY", "MODEL", "WORKSPACE", "SOURCE_PATH",
                   "OBSIDIAN_VAULTS", "OBSIDIAN_VAULT", "PLUGIN_DIRS",
                   "PLUGINS_ENABLED", "PLUGINS_DISABLED"]:
            monkeypatch.delenv(k, raising=False)

        from dochris.settings.config import Settings

        s = Settings.from_env(env_file=env_file)
        assert s.api_key == "test-key-xyz"

    def test_from_env_workspace_from_cwd_scripts(self, tmp_path, monkeypatch):
        """from_env detects workspace via cwd/scripts/config.py (line 244)"""
        scripts = tmp_path / "scripts"
        scripts.mkdir()
        (scripts / "config.py").write_text("# test\n", encoding="utf-8")

        for k in ["WORKSPACE", "OPENAI_API_KEY", "SOURCE_PATH",
                   "OBSIDIAN_VAULTS", "OBSIDIAN_VAULT", "PLUGIN_DIRS",
                   "PLUGINS_ENABLED", "PLUGINS_DISABLED"]:
            monkeypatch.delenv(k, raising=False)

        with patch("pathlib.Path.cwd", return_value=tmp_path):
            from dochris.settings.config import Settings

            s = Settings.from_env()
            assert s.workspace == tmp_path

    def test_from_env_workspace_from_parent_scripts(self, tmp_path, monkeypatch):
        """from_env detects workspace via cwd.parent/scripts/config.py (line 246)"""
        parent = tmp_path / "parent"
        child = parent / "subdir"
        child.mkdir(parents=True)
        scripts = parent / "scripts"
        scripts.mkdir()
        (scripts / "config.py").write_text("# t\n", encoding="utf-8")

        for k in ["WORKSPACE", "OPENAI_API_KEY", "SOURCE_PATH",
                   "OBSIDIAN_VAULTS", "OBSIDIAN_VAULT", "PLUGIN_DIRS",
                   "PLUGINS_ENABLED", "PLUGINS_DISABLED"]:
            monkeypatch.delenv(k, raising=False)

        with patch("pathlib.Path.cwd", return_value=child):
            from dochris.settings.config import Settings

            s = Settings.from_env()
            assert s.workspace == parent


class TestConfigValidateEdge:
    """Test Settings.validate edge cases"""

    def test_validate_empty_workspace_path(self):
        """validate raises ValueError for empty workspace (line 416)"""
        from dochris.settings.config import Settings

        s = Settings(workspace=Path(""))
        with pytest.raises(ValueError, match="workspace"):
            s.validate()

    def test_validate_workspace_oserror(self):
        """validate raises ValueError when mkdir fails (lines 421-422)"""
        from dochris.settings.config import Settings

        s = Settings(workspace=Path("/no/such/root/dir"))
        with patch.object(Path, "mkdir", side_effect=OSError("No space")):
            with pytest.raises(ValueError, match="workspace"):
                s.validate()


# ============================================================
# quality/quality_gate.py CLI — uncovered: 426-433, 474-476, 491
# ============================================================
class TestQualityGateCLI:
    """Test CLI main function"""

    def test_main_no_args(self):
        """main() with no args exits (lines 426-433)"""
        from dochris.quality.quality_gate import main

        with patch("sys.argv", ["qg.py"]):
            with pytest.raises(SystemExit) as e:
                main()
            assert e.value.code == 1

    @patch("dochris.quality.quality_gate.append_log")
    @patch("dochris.quality.quality_gate.get_all_manifests")
    def test_main_scan_wiki(self, mock_m, mock_log, tmp_path):
        """main() scan-wiki (line 491)"""
        mock_m.return_value = [{"status": "compiled", "quality_score": 90}]
        for d in ["wiki/summaries", "wiki/concepts"]:
            (tmp_path / d).mkdir(parents=True)

        from dochris.quality.quality_gate import main

        with patch("sys.argv", ["qg.py", str(tmp_path), "scan-wiki"]):
            with pytest.raises(SystemExit) as e:
                main()
            assert e.value.code == 0

    @patch("dochris.quality.quality_gate.append_log")
    @patch("dochris.quality.quality_gate.update_manifest_status")
    @patch("dochris.quality.quality_gate.get_manifest")
    def test_main_auto_downgrade_reason(self, mock_get, mock_upd, mock_log, tmp_path):
        """main() auto-downgrade --reason (lines 474-476)"""
        mock_get.return_value = {"status": "compiled", "title": "T", "promoted_to": None}
        from dochris.quality.quality_gate import main

        with patch("sys.argv", ["qg.py", str(tmp_path), "auto-downgrade", "SRC-0001", "--reason", "r"]):
            with pytest.raises(SystemExit) as e:
                main()
            assert e.value.code == 0

    @patch("dochris.quality.quality_gate.check_pollution")
    def test_main_check_pollution_clean(self, mock_p, tmp_path):
        """main() check-pollution clean"""
        mock_p.return_value = {"polluted": False, "details": "ok", "polluted_files": []}
        from dochris.quality.quality_gate import main

        with patch("sys.argv", ["qg.py", str(tmp_path), "check-pollution"]):
            with pytest.raises(SystemExit) as e:
                main()
            assert e.value.code == 0

    @patch("dochris.quality.quality_gate.check_pollution")
    def test_main_check_pollution_dirty(self, mock_p, tmp_path):
        """main() check-pollution dirty"""
        mock_p.return_value = {"polluted": True, "details": "bad", "polluted_files": ["f.md"]}
        from dochris.quality.quality_gate import main

        with patch("sys.argv", ["qg.py", str(tmp_path), "check-pollution"]):
            with pytest.raises(SystemExit) as e:
                main()
            assert e.value.code == 1

    @patch("dochris.quality.quality_gate.append_log")
    @patch("dochris.quality.quality_gate.get_manifest")
    def test_main_quality_gate_pass(self, mock_get, mock_log, tmp_path):
        """main() quality-gate pass"""
        mock_get.return_value = {
            "status": "compiled", "quality_score": 90,
            "error_message": None, "summary": "s", "title": "T",
        }
        from dochris.quality.quality_gate import main

        with patch("sys.argv", ["qg.py", str(tmp_path), "quality-gate", "SRC-0001"]):
            with pytest.raises(SystemExit) as e:
                main()
            assert e.value.code == 0

    def test_main_quality_gate_no_srcid(self, tmp_path):
        """main() quality-gate without src-id"""
        from dochris.quality.quality_gate import main

        with patch("sys.argv", ["qg.py", str(tmp_path), "quality-gate"]):
            with pytest.raises(SystemExit) as e:
                main()
            assert e.value.code == 1

    def test_main_auto_downgrade_no_srcid(self, tmp_path):
        """main() auto-downgrade without src-id"""
        from dochris.quality.quality_gate import main

        with patch("sys.argv", ["qg.py", str(tmp_path), "auto-downgrade"]):
            with pytest.raises(SystemExit) as e:
                main()
            assert e.value.code == 1

    @patch("dochris.quality.quality_gate.append_log")
    @patch("dochris.quality.quality_gate.get_all_manifests")
    def test_main_report(self, mock_m, mock_log, tmp_path):
        """main() report"""
        mock_m.return_value = []
        for d in ["wiki/summaries", "wiki/concepts"]:
            (tmp_path / d).mkdir(parents=True)

        from dochris.quality.quality_gate import main

        with patch("sys.argv", ["qg.py", str(tmp_path), "report"]):
            main()

    def test_main_unknown_cmd(self, tmp_path):
        """main() unknown command"""
        from dochris.quality.quality_gate import main

        with patch("sys.argv", ["qg.py", str(tmp_path), "bogus"]):
            with pytest.raises(SystemExit) as e:
                main()
            assert e.value.code == 1


# ============================================================
# vector/faiss_store.py — uncovered: 112, 123-124, 133-137, 147-148, 217, 253-254
# ============================================================
class TestFAISSLoadErrors:
    def test_load_reads_index(self, tmp_path):
        """_load_collection reads faiss index file (line 112)"""
        fm = MagicMock()
        fm.read_index.return_value = MagicMock()
        coll = tmp_path / "c1"
        coll.mkdir()
        (coll / "index.faiss").write_bytes(b"x")
        (coll / "metadata.json").write_text('{"documents":{"i1":"d1"},"metadatas":{"i1":{}}}', encoding="utf-8")

        with patch.dict("sys.modules", {"faiss": fm}):
            from dochris.vector.faiss_store import FAISSStore

            s = FAISSStore(persist_directory=tmp_path)
            s._load_collection("c1")
        assert s._documents["c1"]["i1"] == "d1"

    def test_load_no_metadata(self, tmp_path):
        """_load_collection no metadata.json (lines 123-124)"""
        fm = MagicMock()
        coll = tmp_path / "c2"
        coll.mkdir()
        (coll / "index.faiss").write_bytes(b"x")

        with patch.dict("sys.modules", {"faiss": fm}):
            from dochris.vector.faiss_store import FAISSStore

            s = FAISSStore(persist_directory=tmp_path)
            s._load_collection("c2")
        assert s._documents["c2"] == {}

    def test_load_exception(self, tmp_path):
        """_load_collection generic exception (lines 133-137)"""
        fm = MagicMock()
        fm.read_index.side_effect = RuntimeError("err")
        coll = tmp_path / "c3"
        coll.mkdir()
        (coll / "index.faiss").write_bytes(b"x")

        with patch.dict("sys.modules", {"faiss": fm}):
            from dochris.vector.faiss_store import FAISSStore

            s = FAISSStore(persist_directory=tmp_path)
            s._load_collection("c3")
        assert s._indexes["c3"] is None


class TestFAISSSaveErrors:
    def test_save_no_faiss(self, tmp_path):
        """_save_collection early return without faiss (lines 147-148)"""
        (tmp_path / "c4").mkdir()
        with patch.dict("sys.modules", {"faiss": None}):
            from dochris.vector.faiss_store import FAISSStore

            s = FAISSStore(persist_directory=tmp_path)
            s._documents["c4"] = {"x": "y"}
            s._save_collection("c4")  # no crash


class TestFAISSAddErrors:
    def test_add_metadata_mismatch(self, tmp_path):
        """add_documents metadatas length mismatch (line 217)"""
        with patch.dict("sys.modules", {"faiss": MagicMock()}):
            from dochris.vector.faiss_store import FAISSStore

            s = FAISSStore(persist_directory=tmp_path)
            with pytest.raises(ValueError, match="metadatas"):
                s.add_documents("c", ["d1", "d2"], ["i1", "i2"], metadatas=[{}])


class TestFAISSQueryErrors:
    def test_query_no_faiss(self, tmp_path):
        """query ImportError (lines 253-254)"""
        with patch.dict("sys.modules", {"faiss": None}):
            from dochris.vector.faiss_store import FAISSStore

            s = FAISSStore(persist_directory=tmp_path)
            with pytest.raises(ImportError):
                s.query("c", "q")


# ============================================================
# admin/batch_promote.py CLI — uncovered: 68, 124, 134, 147, 198, 208, 221, 241-247
# ============================================================
class TestBatchPromoteExtra:
    @patch("dochris.admin.batch_promote.get_all_manifests")
    @patch("dochris.admin.batch_promote.promote_to_wiki")
    @patch("dochris.admin.batch_promote.append_log")
    def test_wiki_dry_many(self, mock_log, mock_p, mock_m, tmp_path, capsys):
        """wiki dry_run >20 (line 68)"""
        mock_m.return_value = [{"id": f"SRC-{i:04d}", "quality_score": 90, "title": f"D{i}"} for i in range(25)]
        from dochris.admin.batch_promote import batch_promote_to_wiki

        r = batch_promote_to_wiki(tmp_path, dry_run=True)
        assert r["total"] == 25
        assert "还有 5" in capsys.readouterr().out

    @patch("dochris.admin.batch_promote.get_all_manifests")
    @patch("dochris.admin.batch_promote.promote_to_curated")
    @patch("dochris.admin.batch_promote.append_log")
    def test_curated_dry_many(self, mock_log, mock_p, mock_m, tmp_path, capsys):
        """curated dry_run >20 (line 134)"""
        mock_m.return_value = [{"id": f"SRC-{i:04d}", "quality_score": 95, "title": f"D{i}"} for i in range(25)]
        from dochris.admin.batch_promote import batch_promote_to_curated

        r = batch_promote_to_curated(tmp_path, dry_run=True)
        assert r["total"] == 25

    @patch("dochris.admin.batch_promote.get_all_manifests")
    @patch("dochris.admin.batch_promote.promote_to_curated")
    @patch("dochris.admin.batch_promote.append_log")
    def test_curated_fail(self, mock_log, mock_p, mock_m, tmp_path):
        """curated with failures (line 147)"""
        mock_m.return_value = [
            {"id": "SRC-0001", "quality_score": 95, "title": "A"},
            {"id": "SRC-0002", "quality_score": 96, "title": "B"},
        ]
        mock_p.side_effect = [True, False]
        from dochris.admin.batch_promote import batch_promote_to_curated

        r = batch_promote_to_curated(tmp_path)
        assert r["success"] == 1
        assert r["failed"] == 1

    @patch("dochris.admin.batch_promote.get_all_manifests")
    @patch("dochris.vault.bridge.promote_to_obsidian")
    @patch("dochris.admin.batch_promote.append_log")
    def test_obsidian_dry(self, mock_log, mock_p, mock_m, tmp_path):
        """obsidian dry run (lines 198-208)"""
        mock_m.return_value = [{"id": "SRC-0001", "quality_score": 98, "title": "X"}]
        from dochris.admin.batch_promote import batch_promote_to_obsidian

        r = batch_promote_to_obsidian(tmp_path, dry_run=True)
        assert r["total"] == 1
        mock_p.assert_not_called()

    @patch("dochris.admin.batch_promote.get_all_manifests")
    @patch("dochris.vault.bridge.promote_to_obsidian")
    @patch("dochris.admin.batch_promote.append_log")
    def test_obsidian_limit(self, mock_log, mock_p, mock_m, tmp_path):
        """obsidian with limit (line 208)"""
        mock_m.return_value = [{"id": f"SRC-{i:04d}", "quality_score": 98, "title": f"D{i}"} for i in range(5)]
        mock_p.return_value = True
        from dochris.admin.batch_promote import batch_promote_to_obsidian

        r = batch_promote_to_obsidian(tmp_path, limit=2)
        assert r["total"] == 2

    @patch("dochris.admin.batch_promote.get_all_manifests")
    @patch("dochris.vault.bridge.promote_to_obsidian")
    @patch("dochris.admin.batch_promote.append_log")
    def test_obsidian_fail(self, mock_log, mock_p, mock_m, tmp_path):
        """obsidian with failures (line 221)"""
        mock_m.return_value = [{"id": "SRC-0001", "quality_score": 98, "title": "X"}]
        mock_p.return_value = False
        from dochris.admin.batch_promote import batch_promote_to_obsidian

        r = batch_promote_to_obsidian(tmp_path)
        assert r["failed"] == 1


class TestBatchPromoteCLI:
    def test_main_no_args(self):
        from dochris.admin.batch_promote import main

        with patch("sys.argv", ["bp.py"]):
            with pytest.raises(SystemExit) as e:
                main()
            assert e.value.code == 1

    @patch("dochris.admin.batch_promote.batch_promote_to_wiki")
    @patch("dochris.admin.batch_promote.get_settings")
    def test_main_wiki(self, mock_s, mock_w):
        mock_s.return_value = MagicMock(min_quality_score=85)
        from dochris.admin.batch_promote import main

        with patch("sys.argv", ["bp.py", "/tmp", "wiki"]):
            main()
        mock_w.assert_called_once()

    @patch("dochris.admin.batch_promote.batch_promote_to_curated")
    @patch("dochris.admin.batch_promote.get_settings")
    def test_main_curated(self, mock_s, mock_c):
        mock_s.return_value = MagicMock(min_quality_score=85)
        from dochris.admin.batch_promote import main

        with patch("sys.argv", ["bp.py", "/tmp", "curated"]):
            main()
        mock_c.assert_called_once()

    @patch("dochris.admin.batch_promote.batch_promote_to_wiki")
    @patch("dochris.admin.batch_promote.get_settings")
    def test_main_flags(self, mock_s, mock_w):
        mock_s.return_value = MagicMock(min_quality_score=85)
        from dochris.admin.batch_promote import main

        with patch("sys.argv", ["bp.py", "/tmp", "wiki", "--min-score", "90", "--limit", "5", "--dry-run"]):
            main()
        mock_w.assert_called_once_with(Path("/tmp"), 90, 5, True)

    def test_main_unknown(self):
        from dochris.admin.batch_promote import main

        with patch("sys.argv", ["bp.py", "/tmp", "bad"]):
            with pytest.raises(SystemExit) as e:
                main()
            assert e.value.code == 1


# ============================================================
# admin/recompile.py — uncovered: 39-53, 94, 164-165
# ============================================================
class TestRecompileExtra:
    def test_setup_logging(self, tmp_path):
        """setup_logging (lines 39-53)"""
        with patch("dochris.admin.recompile.get_settings") as ms:
            s = MagicMock()
            s.logs_dir = tmp_path / "logs"
            s.log_date_format = "%Y%m%d_%H%M%S"
            s.log_format = "%(message)s"
            ms.return_value = s

            from dochris.admin.recompile import setup_logging

            lg = setup_logging("t")
            assert lg is not None
            assert (tmp_path / "logs").exists()

    def test_text_mode_excludes_no_text_pdf(self, tmp_path):
        """text mode excludes pdf no_text (line 94)"""
        from dochris.admin.recompile import get_recoverable_failed_docs

        with patch("dochris.admin.recompile.get_all_manifests", return_value=[
            {"id": "S1", "error_message": "no_text", "type": "pdf"},
            {"id": "S2", "error_message": "llm_failed", "type": "article"},
        ]):
            r = get_recoverable_failed_docs(tmp_path, mode="text")
        assert len(r) == 1
        assert r[0]["id"] == "S2"

    def test_recompile_no_api_key(self, tmp_path):
        """recompile exits without API key (lines 164-165)"""
        with patch("dochris.admin.recompile.get_settings") as ms:
            s = MagicMock()
            s.workspace = tmp_path
            s.api_key = None
            s.api_base = "http://x"
            s.model = "m"
            s.batch_size = 10
            ms.return_value = s

            with patch("dochris.admin.recompile.get_recoverable_failed_docs", return_value=[
                {"id": "S1", "error_message": "llm_failed"},
            ]):
                import asyncio

                from dochris.admin.recompile import recompile

                with pytest.raises(SystemExit):
                    asyncio.run(recompile(mode="all"))
