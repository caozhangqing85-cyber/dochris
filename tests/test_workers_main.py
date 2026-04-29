"""
测试 workers/__main__.py 模块
"""

from pathlib import Path
from unittest.mock import patch


class TestWorkersMain:
    """测试 workers 模块导入测试"""

    @patch('builtins.print')
    def test_workers_compiler_worker_import(self, mock_print):
        """测试 compiler_worker 导入"""
        # 这个测试实际上运行 __main__.py 的导入检查
        # 由于 __main__.py 只是一个测试脚本，我们测试它的组件

        from dochris.workers import compiler_worker

        assert hasattr(compiler_worker, 'CompilerWorker')
        assert hasattr(compiler_worker.CompilerWorker, '__init__')

    @patch('builtins.print')
    def test_workers_monitor_worker_import(self, mock_print):
        """测试 monitor_worker 导入"""
        from dochris.workers import monitor_worker

        assert hasattr(monitor_worker, 'MonitorWorker')
        assert hasattr(monitor_worker.MonitorWorker, '__init__')

    def test_compiler_worker_class_exists(self):
        """测试 CompilerWorker 类存在"""
        from dochris.workers.compiler_worker import CompilerWorker

        assert CompilerWorker is not None

    def test_monitor_worker_class_exists(self):
        """测试 MonitorWorker 类存在"""
        from dochris.workers.monitor_worker import MonitorWorker

        assert MonitorWorker is not None

    def test_compiler_worker_has_compile_method(self):
        """测试 CompilerWorker 有 compile_document 方法"""
        from dochris.workers.compiler_worker import CompilerWorker

        assert hasattr(CompilerWorker, 'compile_document')

    def test_monitor_worker_has_generate_report_method(self):
        """测试 MonitorWorker 有 generate_progress_report 方法"""
        from dochris.workers.monitor_worker import MonitorWorker

        assert hasattr(MonitorWorker, 'generate_progress_report')

    def test_monitor_worker_has_print_report_method(self):
        """测试 MonitorWorker 有 print_report 方法"""
        from dochris.workers.monitor_worker import MonitorWorker

        assert hasattr(MonitorWorker, 'print_report')

    def test_compiler_worker_initialization(self):
        """测试 CompilerWorker 初始化"""
        from dochris.workers.compiler_worker import CompilerWorker

        worker = CompilerWorker("test-key", "https://api.test.com", "test-model")

        assert worker is not None

    def test_monitor_worker_initialization(self):
        """测试 MonitorWorker 初始化"""
        from dochris.workers.monitor_worker import MonitorWorker

        worker = MonitorWorker()

        assert worker is not None


class TestWorkersMainModuleStructure:
    """测试 workers 模块结构"""

    def test_workers_package_has_init(self):
        """测试 workers 包有 __init__.py"""
        import workers
        assert hasattr(workers, '__file__')

    def test_workers_compiler_module_exists(self):
        """测试 workers/compiler_worker.py 存在"""
        scripts_dir = Path(__file__).parent.parent / "src" / "dochris" / "workers"
        assert (scripts_dir / "compiler_worker.py").exists()

    def test_workers_monitor_module_exists(self):
        """测试 workers/monitor_worker.py 存在"""
        scripts_dir = Path(__file__).parent.parent / "src" / "dochris" / "workers"
        assert (scripts_dir / "monitor_worker.py").exists()

    def test_workers_main_module_exists(self):
        """测试 workers/__main__.py 存在"""
        scripts_dir = Path(__file__).parent.parent / "src" / "dochris" / "workers"
        assert (scripts_dir / "__main__.py").exists()


class TestWorkersMainExecution:
    """测试 workers 主模块执行"""

    @patch('sys.argv', ['__main__.py'])
    @patch('builtins.print')
    def test_main_module_execution(self, mock_print):
        """测试主模块执行"""
        # 由于 __main__.py 会直接导入和打印，我们测试导入不会报错
        import importlib

        # 这会执行 __main__.py 的内容
        try:
            importlib.import_module('workers.__main__')
        except SystemExit:
            pass  # 可能会退出，这是正常的

    def test_compiler_worker_instantiation_with_params(self):
        """测试带参数实例化 CompilerWorker"""
        from dochris.workers.compiler_worker import CompilerWorker

        worker = CompilerWorker(
            api_key="test-api-key",
            base_url="https://test.api.com",
            model="test-model"
        )

        assert worker is not None

    def test_monitor_worker_workspace_property(self):
        """测试 MonitorWorker 的 workspace 属性"""
        from dochris.workers.monitor_worker import MonitorWorker

        worker = MonitorWorker()

        assert hasattr(worker, 'workspace')
        assert worker.workspace is not None
