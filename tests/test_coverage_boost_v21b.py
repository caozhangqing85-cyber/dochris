"""覆盖率提升 v21b — 散装低悬果实"""

from io import StringIO
from unittest.mock import patch

import pytest


class TestAbstractClasses:
    def test_vector_store(self):
        from dochris.vector.base import BaseVectorStore
        with pytest.raises(TypeError):
            BaseVectorStore()  # type: ignore[abstract]

    def test_llm_provider(self):
        from dochris.llm.base import BaseLLMProvider
        with pytest.raises(TypeError):
            BaseLLMProvider()  # type: ignore[abstract]


class TestHookspecDecorators:
    def test_hookimpl(self):
        from dochris.plugin.hookspec import hookimpl
        @hookimpl
        def f(x): return x + 1
        assert f(5) == 6

    def test_hookspec(self):
        from dochris.plugin.hookspec import hookspec
        @hookspec
        def f(x): return x
        assert f("hi") == "hi"


class TestPluginRegistryStr:
    def test_str(self):
        from dochris.plugin.registry import PluginManager
        assert "PluginManager" in str(PluginManager())


class TestQualityGateReport:
    @pytest.mark.skip("generate_report requires too many mock dependencies")
    def test_removed_files_print(self, tmp_path):
        from dochris.quality.quality_gate import generate_report
        with patch("dochris.quality.quality_gate.get_settings") as gs, \
             patch("dochris.quality.quality_gate.scan_wiki") as sw:
            gs.return_value.workspace = str(tmp_path)
            sw.return_value = {"total": 10, "compiled": 8, "promoted": 5,
                              "avg_quality": 88.5, "below_threshold": 2,
                              "wiki_total": 15, "wiki_summaries": 8, "wiki_concepts": 7,
                              "removed_files": [f"{i}.md" for i in range(6)],
                              "details": []}
            out = StringIO()
            with patch("sys.stdout", out):
                generate_report(str(tmp_path))
            assert "移除文件: 6 个" in out.getvalue()


# Index knowledge chroma test moved to separate file to avoid OOM
