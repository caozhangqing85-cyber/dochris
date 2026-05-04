"""测试 dochris.__init__.py 模块"""

import pytest


class TestInitModuleAttributes:
    """测试 __init__.py 模块属性"""

    def test_version_exists(self):
        """测试版本号存在"""
        import dochris

        assert hasattr(dochris, "__version__")
        assert dochris.__version__ == "1.4.0"

    def test_author_exists(self):
        """测试作者信息存在"""
        import dochris

        assert hasattr(dochris, "__author__")
        assert "caozhangqing85-cyber" in dochris.__author__


class TestInitModuleLazyImport:
    """测试延迟导入功能"""

    def test_getattr_llm_client(self):
        """测试延迟导入 LLMClient"""
        import dochris

        client = dochris.LLMClient
        assert client is not None

    def test_getattr_settings(self):
        """测试延迟导入 Settings"""
        import dochris

        settings = dochris.Settings
        assert settings is not None

    def test_getattr_get_settings(self):
        """测试延迟导入 get_settings"""
        import dochris

        get_settings = dochris.get_settings
        assert callable(get_settings)

    def test_getattr_file_status(self):
        """测试延迟导入 FileStatus"""
        import dochris

        status = dochris.FileStatus
        assert status is not None

    def test_getattr_file_type(self):
        """测试延迟导入 FileType"""
        import dochris

        file_type = dochris.FileType
        assert file_type is not None

    def test_getattr_manifest_entry(self):
        """测试延迟导入 ManifestEntry"""
        import dochris

        entry = dochris.ManifestEntry
        assert entry is not None

    def test_getattr_compilation_result(self):
        """测试延迟导入 CompilationResult"""
        import dochris

        result = dochris.CompilationResult
        assert result is not None

    def test_getattr_query_result(self):
        """测试延迟导入 QueryResult"""
        import dochris

        query_result = dochris.QueryResult
        assert query_result is not None

    def test_getattr_quality_report(self):
        """测试延迟导入 QualityReport"""
        import dochris

        report = dochris.QualityReport
        assert report is not None

    def test_getattr_invalid_attribute(self):
        """测试访问不存在的属性抛出 AttributeError"""
        import dochris

        with pytest.raises(AttributeError):
            _ = dochris.NonExistentAttribute


class TestInitModuleAll:
    """测试 __all__ 导出列表"""

    def test_all_contains_version(self):
        """测试 __all__ 包含版本号"""
        import dochris

        assert "__version__" in dochris.__all__

    def test_all_contains_author(self):
        """测试 __all__ 包含作者"""
        import dochris

        assert "__author__" in dochris.__all__

    def test_all_contains_core_exports(self):
        """测试 __all__ 包含核心导出"""
        import dochris

        expected_exports = [
            "get_settings",
            "Settings",
            "LLMClient",
            "FileStatus",
            "FileType",
        ]
        for export in expected_exports:
            assert export in dochris.__all__
