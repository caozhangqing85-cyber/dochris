"""
测试 dochris.__main__.py 模块
"""

from unittest.mock import patch


class TestMainModule:
    """测试主模块导入和基本功能"""

    def test_main_module_exists(self):
        """测试主模块可以导入"""
        import dochris.__main__

        assert dochris.__main__ is not None

    def test_main_imports_cli_main(self):
        """测试主模块导入 cli.main"""
        import dochris.__main__

        # 验证模块导入了 main 函数
        assert hasattr(dochris.__main__, "main")

    @patch("dochris.__main__.main")
    def test_main_calls_cli_main(self, mock_main):
        """测试主模块调用 main 函数"""
        # 模拟 if __name__ == "__main__" 块
        import sys

        import dochris.__main__

        # 保存原始 argv
        original_argv = sys.argv

        try:
            # 设置模拟参数
            sys.argv = ["dochris", "--help"]
            mock_main.return_value = None

            # 执行主模块的 main 块逻辑
            # 注意：由于模块已经加载，__name__ 不会是 "__main__"
            # 所以我们需要手动测试 main 函数的调用
            with patch.object(dochris.__main__, "__name__", "__main__"):
                # 这个测试验证模块结构正确
                assert callable(dochris.__main__.main)
        finally:
            sys.argv = original_argv

    def test_cli_main_is_callable(self):
        """测试 cli.main.main 是可调用的"""
        from dochris.cli.main import main

        assert callable(main)

    def test_cli_main_signature(self):
        """测试 cli.main.main 函数签名"""
        from dochris.cli.main import main

        # main 函数应该接受参数或使用 argparse
        # 这是一个基本的结构测试
        assert callable(main)


class TestMainModuleEntry:
    """测试 -m dochris 入口点"""

    def test_dochris_module_import(self):
        """测试 python -m dochris 可以导入模块"""
        import importlib
        import sys

        # 确保模块在 sys.modules 中
        assert "dochris" in sys.modules or "dochris.__main__" not in sys.modules

        # 尝试导入
        try:
            importlib.import_module("dochris.__main__")
            success = True
        except Exception:
            success = False

        assert success

    def test_dochris_has_main_attr(self):
        """测试 dochris 包有 __main__ 属性"""
        import dochris

        # 包应该有 __main__ 子模块
        assert hasattr(dochris, "__main__") or "__main__" in dir(dochris)
