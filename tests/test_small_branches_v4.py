"""补充覆盖多个模块的小分支"""

from unittest.mock import MagicMock, patch

import pytest


class TestApiInitException:
    """覆盖 api/__init__.py lines 16-17 (Exception 分支)"""

    def test_app_none_on_exception(self):
        """app import 抛异常时 app = None"""
        import importlib
        import sys

        # 确保 api.app 模块已加载
        import dochris.api  # noqa: F401

        api_app_mod = sys.modules["dochris.api.app"]
        api_init_mod = sys.modules["dochris.api"]
        original_app = api_app_mod.app

        try:
            # 删除 app 属性，让 from dochris.api.app import app 抛 AttributeError
            delattr(api_app_mod, "app")

            # 删除 api 包缓存，强制重新执行 __init__.py
            del sys.modules["dochris.api"]

            # 重新加载 api 包 — 此时 import app 会失败
            new_api_mod = importlib.import_module("dochris.api")
            assert new_api_mod.app is None
        finally:
            # 恢复
            api_app_mod.app = original_app
            api_init_mod.app = original_app
            sys.modules["dochris.api"] = api_init_mod


class TestPluginLoaderNoSpec:
    """覆盖 plugin/loader.py line 67 (spec is None)"""

    def test_spec_none_raises_import_error(self, tmp_path):
        """spec_from_file_location 返回 None 时抛 ImportError"""
        from dochris.plugin.loader import load_plugin_module

        # spec_from_file_location 对 .py 扩展名且存在的文件不会返回 None
        # 但对特殊扩展名可能返回 None — 用 .so 或无效后缀
        fake_path = tmp_path / "plugin.xyz"
        fake_path.write_text("not a module")

        with patch(
            "dochris.plugin.loader.importlib.util.spec_from_file_location", return_value=None
        ):
            with pytest.raises(ImportError, match="Cannot create spec"):
                load_plugin_module(fake_path, "fake_plugin")


class TestDocParserShortContent:
    """覆盖 doc_parser.py lines 87-88 (清理后内容过短)"""

    def test_cleaned_content_too_short(self, tmp_path):
        """markitdown 清理 base64 后内容过短"""
        from dochris.parsers.doc_parser import parse_office_document

        doc = tmp_path / "test.docx"
        doc.write_bytes(b"PK fake docx")

        # MarkItDown 是延迟导入，需要 patch markitdown 模块
        mock_md_module = MagicMock()
        mock_instance = MagicMock()
        # 内容 > 50 字符但 base64 被清理后 < 50 字符
        mock_instance.convert.return_value = MagicMock(
            text_content="![img](data:image/png;base64," + "A" * 100 + ") short"
        )
        mock_md_module.MarkItDown.return_value = mock_instance

        with patch.dict("sys.modules", {"markitdown": mock_md_module}):
            result = parse_office_document(doc)
            assert result is None


class TestVectorFaissImportError:
    """覆盖 vector/__init__.py lines 26-27 (FAISS ImportError)"""

    def test_faiss_import_error(self):
        """FAISS store ImportError 时跳过注册"""
        import importlib
        import sys

        import dochris.vector

        # 保存原始状态
        original_stores = dict(dochris.vector.STORES)

        # patch faiss_store 导入失败
        with patch.dict("sys.modules", {"dochris.vector.faiss_store": None}):
            # 删除 vector 缓存重新加载
            del sys.modules["dochris.vector"]
            importlib.import_module("dochris.vector")
            new_mod = sys.modules["dochris.vector"]
            assert "faiss" not in new_mod.STORES

        # 恢复原始状态
        dochris.vector.STORES.clear()
        dochris.vector.STORES.update(original_stores)
        sys.modules["dochris.vector"] = dochris.vector
