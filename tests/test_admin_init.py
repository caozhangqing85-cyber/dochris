"""测试 dochris.admin.__init__.py 模块"""


class TestAdminInitModule:
    """测试 admin 包初始化模块"""

    def test_admin_module_exists(self):
        """测试 admin 模块可以导入"""
        import dochris.admin

        assert dochris.admin is not None

    def test_admin_all_exists(self):
        """测试 __all__ 属性存在"""
        import dochris.admin

        assert hasattr(dochris.admin, "__all__")

    def test_admin_all_is_list(self):
        """测试 __all__ 是列表"""
        import dochris.admin

        assert isinstance(dochris.admin.__all__, list)

    def test_admin_module_docstring(self):
        """测试模块有文档字符串"""
        import dochris.admin

        assert dochris.admin.__doc__ is not None
        assert len(dochris.admin.__doc__) > 0
        assert "Admin" in dochris.admin.__doc__ or "管理" in dochris.admin.__doc__
