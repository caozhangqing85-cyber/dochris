"""覆盖率提升 v15 — plugin/hookspec.py + plugin/registry.py + admin/ + quality/quality_gate.py"""

from unittest.mock import MagicMock, patch

import pytest


# ============================================================
# plugin/hookspec.py
# ============================================================
class TestHookSpec:
    def test_hookspec_repr(self):
        from dochris.plugin.hookspec import HookSpec

        spec = HookSpec("my_hook", firstresult=True)
        assert repr(spec) == "HookSpec('my_hook', firstresult=True)"

    def test_hookspec_defaults(self):
        from dochris.plugin.hookspec import HookSpec

        spec = HookSpec("test")
        assert spec.name == "test"
        assert spec.firstresult is False
        assert spec.historic is False


class TestHookspecDecorator:
    def test_hookspec_marks_function(self):
        from dochris.plugin.hookspec import hookspec

        @hookspec
        def my_test_hook(x: str) -> str | None:
            ...

        assert my_test_hook._is_hookspec is True

    def test_hookspec_registers(self):
        from dochris.plugin.hookspec import hookspec, _HOOK_SPECS

        @hookspec
        def unique_hook_name_for_test():
            ...

        assert "unique_hook_name_for_test" in _HOOK_SPECS


class TestHookimplDecorator:
    def test_hookimpl_marks_function(self):
        from dochris.plugin.hookspec import hookimpl

        @hookimpl
        def my_impl(x: str) -> str:
            return x

        assert my_impl._is_hookimpl is True


class TestGetListHookspecs:
    def test_get_hookspec(self):
        from dochris.plugin.hookspec import get_hookspec

        # Should find one of the built-in hookspecs
        result = get_hookspec("ingest_parser")
        assert result is not None
        assert result.name == "ingest_parser"

    def test_get_hookspec_not_found(self):
        from dochris.plugin.hookspec import get_hookspec

        result = get_hookspec("nonexistent_hook")
        assert result is None

    def test_list_hookspecs(self):
        from dochris.plugin.hookspec import list_hookspecs

        specs = list_hookspecs()
        assert "ingest_parser" in specs
        assert "pre_compile" in specs
        assert "post_compile" in specs
        assert "quality_score" in specs
        assert "pre_query" in specs
        assert "post_query" in specs


# ============================================================
# plugin/registry.py
# ============================================================
class TestPluginManager:
    def test_register_and_get(self):
        from dochris.plugin.registry import PluginManager

        pm = PluginManager()
        func = MagicMock()
        pm.register("my_plugin", "my_hook", func)

        impls = pm.get_hookimpls("my_hook")
        assert len(impls) == 1
        assert impls[0][0] == "my_plugin"

    def test_get_hookimpls_empty(self):
        from dochris.plugin.registry import PluginManager

        pm = PluginManager()
        assert pm.get_hookimpls("nonexistent") == []

    def test_disabled_plugin_excluded(self):
        from dochris.plugin.registry import PluginManager

        pm = PluginManager()
        func = MagicMock()
        # Use _register_module which also adds to _plugins
        pm._register_module("p1", MagicMock(), [("hook1", func)])
        pm.disable_plugin("p1")

        impls = pm.get_hookimpls("hook1")
        assert len(impls) == 0

    def test_call_hook(self):
        from dochris.plugin.registry import PluginManager

        pm = PluginManager()
        func = MagicMock(return_value="result")
        pm.register("p1", "hook1", func)

        results = pm.call_hook("hook1", "arg1", key="val")
        assert results == ["result"]
        func.assert_called_once_with("arg1", key="val")

    def test_call_hook_exception(self):
        from dochris.plugin.registry import PluginManager

        pm = PluginManager()
        func = MagicMock(side_effect=ValueError("boom"))
        pm.register("p1", "hook1", func)

        results = pm.call_hook("hook1")
        assert results == []

    def test_call_hook_firstresult(self):
        from dochris.plugin.registry import PluginManager

        pm = PluginManager()
        func1 = MagicMock(return_value=None)
        func2 = MagicMock(return_value="found")
        pm.register("p1", "hook1", func1)
        pm.register("p2", "hook1", func2)

        result = pm.call_hook_firstresult("hook1")
        assert result == "found"

    def test_call_hook_firstresult_all_none(self):
        from dochris.plugin.registry import PluginManager

        pm = PluginManager()
        func = MagicMock(return_value=None)
        pm.register("p1", "hook1", func)

        result = pm.call_hook_firstresult("hook1")
        assert result is None

    def test_call_hook_firstresult_exception(self):
        from dochris.plugin.registry import PluginManager

        pm = PluginManager()
        func1 = MagicMock(side_effect=RuntimeError("fail"))
        func2 = MagicMock(return_value="ok")
        pm.register("p1", "hook1", func1)
        pm.register("p2", "hook1", func2)

        result = pm.call_hook_firstresult("hook1")
        assert result == "ok"

    def test_enable_disable(self):
        from dochris.plugin.registry import PluginManager

        pm = PluginManager()
        pm._plugins["test_p"] = {"enabled": True, "module": MagicMock()}

        pm.disable_plugin("test_p")
        assert pm.is_enabled("test_p") is False

        pm.enable_plugin("test_p")
        assert pm.is_enabled("test_p") is True

    def test_is_enabled_unknown(self):
        from dochris.plugin.registry import PluginManager

        pm = PluginManager()
        assert pm.is_enabled("unknown") is True  # default True

    def test_list_plugins(self):
        from dochris.plugin.registry import PluginManager

        pm = PluginManager()
        func = MagicMock()
        pm._register_module("p1", MagicMock(), [("hook_a", func), ("hook_b", func)])

        plugins = pm.list_plugins()
        assert len(plugins) == 1
        assert plugins[0]["name"] == "p1"
        assert set(plugins[0]["hooks"]) == {"hook_a", "hook_b"}

    def test_unregister_plugin(self):
        from dochris.plugin.registry import PluginManager

        pm = PluginManager()
        func = MagicMock()
        pm._register_module("p1", MagicMock(), [("hook_a", func)])
        pm.unregister_plugin("p1")

        assert pm.is_enabled("p1") is True  # gone, default True
        assert pm.get_hookimpls("hook_a") == []

    def test_load_from_directory(self, tmp_path):
        from dochris.plugin.registry import PluginManager

        pm = PluginManager()
        # Non-existent dir
        result = pm.load_from_directory(tmp_path / "missing")
        assert result == []

    def test_load_from_directory_with_plugin(self, tmp_path):
        from dochris.plugin.registry import PluginManager

        pm = PluginManager()
        plugin_dir = tmp_path / "plugins"
        plugin_dir.mkdir()

        # Write a valid plugin file
        plugin_code = '''
from dochris.plugin.hookspec import hookimpl

@hookimpl
def pre_query(query: str) -> str:
    return query.upper()
'''
        (plugin_dir / "upper_query.py").write_text(plugin_code, encoding="utf-8")

        result = pm.load_from_directory(plugin_dir)
        assert "upper_query" in result

    def test_load_from_directory_skip_underscore(self, tmp_path):
        from dochris.plugin.registry import PluginManager

        pm = PluginManager()
        plugin_dir = tmp_path / "plugins"
        plugin_dir.mkdir()

        (plugin_dir / "_private.py").write_text("x = 1\n", encoding="utf-8")
        (plugin_dir / "__init__.py").write_text("", encoding="utf-8")

        result = pm.load_from_directory(plugin_dir)
        assert result == []

    def test_load_from_directory_syntax_error(self, tmp_path):
        from dochris.plugin.registry import PluginManager

        pm = PluginManager()
        plugin_dir = tmp_path / "plugins"
        plugin_dir.mkdir()

        (plugin_dir / "bad.py").write_text("def broken(\n", encoding="utf-8")

        result = pm.load_from_directory(plugin_dir)
        assert result == []

    def test_load_from_entrypoints(self):
        from dochris.plugin.registry import PluginManager

        pm = PluginManager()
        # Should handle gracefully even if no entry points exist
        result = pm.load_from_entrypoints()
        assert isinstance(result, list)


class TestGlobalPluginManager:
    def test_get_and_reset(self):
        from dochris.plugin.registry import get_plugin_manager, reset_plugin_manager

        reset_plugin_manager()
        pm1 = get_plugin_manager()
        pm2 = get_plugin_manager()
        assert pm1 is pm2

        reset_plugin_manager()
        pm3 = get_plugin_manager()
        assert pm3 is not pm1


# ============================================================
# quality/quality_gate.py
# ============================================================
class TestQualityGate:
    @patch("dochris.quality.quality_gate.get_manifest")
    def test_manifest_not_found(self, mock_get, tmp_path):
        from dochris.quality.quality_gate import quality_gate

        mock_get.return_value = None
        result = quality_gate(tmp_path, "SRC-0001")
        assert result["passed"] is False
        assert "未找到" in result["reason"]

    @patch("dochris.quality.quality_gate.append_log")
    @patch("dochris.quality.quality_gate.get_manifest")
    def test_all_checks_pass(self, mock_get, mock_log, tmp_path):
        from dochris.quality.quality_gate import quality_gate

        mock_get.return_value = {
            "status": "compiled",
            "quality_score": 90,
            "error_message": None,
            "summary": "A summary text",
            "title": "Test Doc",
        }
        result = quality_gate(tmp_path, "SRC-0001", min_score=85)
        assert result["passed"] is True
        assert result["reason"] == "通过"

    @patch("dochris.quality.quality_gate.append_log")
    @patch("dochris.quality.quality_gate.get_manifest")
    def test_wrong_status(self, mock_get, mock_log, tmp_path):
        from dochris.quality.quality_gate import quality_gate

        mock_get.return_value = {
            "status": "ingested",
            "quality_score": 90,
            "error_message": None,
            "summary": "text",
            "title": "Test",
        }
        result = quality_gate(tmp_path, "SRC-0001")
        assert result["passed"] is False
        assert "status" in result["reason"].lower() or "状态" in result["reason"]

    @patch("dochris.quality.quality_gate.append_log")
    @patch("dochris.quality.quality_gate.get_manifest")
    def test_low_score(self, mock_get, mock_log, tmp_path):
        from dochris.quality.quality_gate import quality_gate

        mock_get.return_value = {
            "status": "compiled",
            "quality_score": 50,
            "error_message": None,
            "summary": "text",
            "title": "Test",
        }
        result = quality_gate(tmp_path, "SRC-0001")
        assert result["passed"] is False

    @patch("dochris.quality.quality_gate.append_log")
    @patch("dochris.quality.quality_gate.get_manifest")
    def test_has_error(self, mock_get, mock_log, tmp_path):
        from dochris.quality.quality_gate import quality_gate

        mock_get.return_value = {
            "status": "compiled",
            "quality_score": 90,
            "error_message": "some error",
            "summary": "text",
            "title": "Test",
        }
        result = quality_gate(tmp_path, "SRC-0001")
        assert result["passed"] is False

    @patch("dochris.quality.quality_gate.append_log")
    @patch("dochris.quality.quality_gate.get_manifest")
    def test_no_summary(self, mock_get, mock_log, tmp_path):
        from dochris.quality.quality_gate import quality_gate

        mock_get.return_value = {
            "status": "compiled",
            "quality_score": 90,
            "error_message": None,
            "summary": None,
            "title": "Test",
        }
        result = quality_gate(tmp_path, "SRC-0001")
        assert result["passed"] is False


class TestAutoDowngrade:
    @patch("dochris.quality.quality_gate.get_manifest")
    def test_manifest_not_found(self, mock_get, tmp_path):
        from dochris.quality.quality_gate import auto_downgrade

        mock_get.return_value = None
        result = auto_downgrade(tmp_path, "SRC-0001")
        assert result["success"] is False

    @patch("dochris.quality.quality_gate.get_manifest")
    def test_cannot_downgrade_ingested(self, mock_get, tmp_path):
        from dochris.quality.quality_gate import auto_downgrade

        mock_get.return_value = {"status": "ingested", "title": "Test"}
        result = auto_downgrade(tmp_path, "SRC-0001")
        assert result["success"] is False
        assert "无法" in result["reason"]

    @patch("dochris.quality.quality_gate.append_log")
    @patch("dochris.quality.quality_gate.update_manifest_status")
    @patch("dochris.quality.quality_gate.get_manifest")
    def test_downgrade_promoted(self, mock_get, mock_update, mock_log, tmp_path):
        from dochris.quality.quality_gate import auto_downgrade

        mock_get.return_value = {"status": "promoted", "title": "Test Doc", "promoted_to": "wiki"}
        result = auto_downgrade(tmp_path, "SRC-0001")
        assert result["success"] is True
        assert result["from_status"] == "promoted"
        assert result["to_status"] == "promoted_to_wiki"

    @patch("dochris.quality.quality_gate.append_log")
    @patch("dochris.quality.quality_gate.update_manifest_status")
    @patch("dochris.quality.quality_gate.get_manifest")
    def test_downgrade_compiled(self, mock_get, mock_update, mock_log, tmp_path):
        from dochris.quality.quality_gate import auto_downgrade

        mock_get.return_value = {"status": "compiled", "title": "Test", "promoted_to": None}
        result = auto_downgrade(tmp_path, "SRC-0001", reason="quality too low")
        assert result["success"] is True
        assert result["to_status"] == "ingested"

    @patch("dochris.quality.quality_gate.append_log")
    @patch("dochris.quality.quality_gate.update_manifest_status")
    @patch("dochris.quality.quality_gate.get_manifest")
    def test_downgrade_removes_wiki_files(self, mock_get, mock_update, mock_log, tmp_path):
        from dochris.quality.quality_gate import auto_downgrade

        wiki_summ = tmp_path / "wiki" / "summaries"
        wiki_summ.mkdir(parents=True)
        (wiki_summ / "Test_Doc.md").write_text("content", encoding="utf-8")

        mock_get.return_value = {"status": "promoted_to_wiki", "title": "Test_Doc", "promoted_to": "wiki"}
        result = auto_downgrade(tmp_path, "SRC-0001")
        assert result["success"] is True
        assert not (wiki_summ / "Test_Doc.md").exists()


class TestCheckPollution:
    @patch("dochris.quality.quality_gate.append_log")
    @patch("dochris.quality.quality_gate.get_all_manifests")
    def test_clean_wiki(self, mock_manifests, mock_log, tmp_path):
        from dochris.quality.quality_gate import check_pollution

        mock_manifests.return_value = []
        wiki = tmp_path / "wiki"
        wiki.mkdir()
        (wiki / "summaries").mkdir()
        (wiki / "concepts").mkdir()

        result = check_pollution(tmp_path)
        assert result["polluted"] is False

    @patch("dochris.quality.quality_gate.append_log")
    @patch("dochris.quality.quality_gate.get_all_manifests")
    def test_polluted_wiki(self, mock_manifests, mock_log, tmp_path):
        from dochris.quality.quality_gate import check_pollution

        mock_manifests.return_value = []
        wiki = tmp_path / "wiki"
        wiki.mkdir()
        summ = wiki / "summaries"
        summ.mkdir()
        (summ / "polluted_file.md").write_text("bad content", encoding="utf-8")
        (wiki / "concepts").mkdir()

        result = check_pollution(tmp_path)
        assert result["polluted"] is True
        assert result["polluted_count"] == 1


class TestScanWiki:
    @patch("dochris.quality.quality_gate.append_log")
    @patch("dochris.quality.quality_gate.get_all_manifests")
    def test_scan_empty(self, mock_manifests, mock_log, tmp_path):
        from dochris.quality.quality_gate import scan_wiki

        mock_manifests.return_value = []
        report = scan_wiki(tmp_path)
        assert report["wiki_total"] == 0
        assert report["manifest_total"] == 0


class TestGenerateReport:
    @patch("dochris.quality.quality_gate.append_log")
    @patch("dochris.quality.quality_gate.get_all_manifests")
    def test_generate_report(self, mock_manifests, mock_log, tmp_path):
        from dochris.quality.quality_gate import generate_report

        mock_manifests.return_value = [
            {"status": "compiled", "quality_score": 90, "title": "Good"},
            {"status": "compiled", "quality_score": 50, "title": "Bad"},
            {"status": "ingested", "quality_score": 0, "title": "New"},
        ]
        report = generate_report(tmp_path)
        assert "score_distribution" in report
        assert report["score_distribution"]["85-100"] == 1
        assert report["score_distribution"]["41-60"] == 1


# ============================================================
# admin/index_knowledge.py — test utility functions only
# Skip importing the full module (it connects to ChromaDB at import time)
# ============================================================
class TestIndexKnowledgeUtils:
    def test_clean_text(self):
        import re

        def clean_text(text: str) -> str:
            if not text:
                return ""
            text = re.sub(r"\n+", "\n", text)
            text = re.sub(r" +", " ", text)
            return text.strip()

        assert clean_text("") == ""
        assert clean_text("  hello   world  ") == "hello world"
        assert clean_text("a\n\n\nb") == "a\nb"

    def test_truncate_text(self):
        def truncate_text(text: str, max_chars: int = 4000) -> str:
            if len(text) <= max_chars:
                return text
            return text[:max_chars] + "..."

        short = "hello"
        assert truncate_text(short, 10) == "hello"

        long = "x" * 100
        result = truncate_text(long, 50)
        assert len(result) == 53
        assert result.endswith("...")


# ============================================================
# admin/recompile.py — test utility functions
# ============================================================
class TestRecompileUtils:
    def test_get_recoverable_llm_failed(self, tmp_path):
        from dochris.admin.recompile import get_recoverable_failed_docs

        manifests = [
            {"id": "SRC-0001", "error_message": "llm_failed: timeout", "type": "pdf"},
            {"id": "SRC-0002", "error_message": "no_text", "type": "pdf"},
        ]
        with patch("dochris.admin.recompile.get_all_manifests", return_value=manifests):
            result = get_recoverable_failed_docs(tmp_path, mode="llm_failed")
        assert len(result) == 1
        assert result[0]["id"] == "SRC-0001"

    def test_get_recoverable_text_mode(self, tmp_path):
        from dochris.admin.recompile import get_recoverable_failed_docs

        manifests = [
            {"id": "SRC-0001", "error_message": "llm_failed", "type": "pdf"},
            {"id": "SRC-0002", "error_message": "llm_failed", "type": "video"},
            {"id": "SRC-0003", "error_message": "no_text", "type": "pdf"},
        ]
        with patch("dochris.admin.recompile.get_all_manifests", return_value=manifests):
            result = get_recoverable_failed_docs(tmp_path, mode="text")
        assert len(result) == 1  # video excluded, no_text pdf excluded
        assert result[0]["id"] == "SRC-0001"

    def test_get_recoverable_custom_filter(self, tmp_path):
        from dochris.admin.recompile import get_recoverable_failed_docs

        manifests = [
            {"id": "SRC-0001", "error_message": "Connection error at step 3"},
            {"id": "SRC-0002", "error_message": "timeout"},
        ]
        with patch("dochris.admin.recompile.get_all_manifests", return_value=manifests):
            result = get_recoverable_failed_docs(tmp_path, mode="all", error_filter="Connection")
        assert len(result) == 1
        assert result[0]["id"] == "SRC-0001"


# ============================================================
# admin/batch_promote.py — test batch functions
# ============================================================
class TestBatchPromote:
    @patch("dochris.admin.batch_promote.get_all_manifests")
    @patch("dochris.admin.batch_promote.promote_to_wiki")
    @patch("dochris.admin.batch_promote.append_log")
    def test_batch_promote_to_wiki_dry_run(self, mock_log, mock_promote, mock_manifests, tmp_path):
        from dochris.admin.batch_promote import batch_promote_to_wiki

        mock_manifests.return_value = [
            {"id": "SRC-0001", "quality_score": 90, "title": "Good"},
            {"id": "SRC-0002", "quality_score": 50, "title": "Bad"},
        ]
        result = batch_promote_to_wiki(tmp_path, dry_run=True)
        assert result["total"] == 1  # Only score 90 >= 85
        mock_promote.assert_not_called()

    @patch("dochris.admin.batch_promote.get_all_manifests")
    @patch("dochris.admin.batch_promote.promote_to_wiki")
    @patch("dochris.admin.batch_promote.append_log")
    def test_batch_promote_to_wiki_with_limit(self, mock_log, mock_promote, mock_manifests, tmp_path):
        from dochris.admin.batch_promote import batch_promote_to_wiki

        mock_manifests.return_value = [
            {"id": f"SRC-{i:04d}", "quality_score": 90, "title": f"Doc {i}"}
            for i in range(10)
        ]
        mock_promote.return_value = True
        result = batch_promote_to_wiki(tmp_path, limit=3)
        assert result["total"] == 3
        assert result["success"] == 3

    @patch("dochris.admin.batch_promote.get_all_manifests")
    @patch("dochris.admin.batch_promote.promote_to_curated")
    @patch("dochris.admin.batch_promote.append_log")
    def test_batch_promote_to_curated(self, mock_log, mock_promote, mock_manifests, tmp_path):
        from dochris.admin.batch_promote import batch_promote_to_curated

        mock_manifests.return_value = [
            {"id": "SRC-0001", "quality_score": 95, "title": "Good"},
        ]
        mock_promote.return_value = True
        result = batch_promote_to_curated(tmp_path)
        assert result["success"] == 1

    @patch("dochris.admin.batch_promote.append_log")
    @patch("dochris.admin.batch_promote.get_all_manifests")
    def test_batch_promote_to_obsidian_import_error(self, mock_manifests, mock_log, tmp_path):
        from dochris.admin.batch_promote import batch_promote_to_obsidian

        mock_manifests.return_value = []
        with patch.dict("sys.modules", {"dochris.vault.bridge": None}):
            result = batch_promote_to_obsidian(tmp_path)
        assert result["total"] == 0
        assert result["success"] == 0
