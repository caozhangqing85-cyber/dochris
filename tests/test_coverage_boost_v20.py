"""覆盖率提升 v20a — cli_serve + api promote tests"""

from unittest.mock import MagicMock, patch

import pytest


# ============================================================
# cli/cli_serve.py — uvicorn 是 try/except 内部导入
# ============================================================
class TestCliServe:
    def test_serve_success(self):
        import importlib
        import dochris.cli.cli_serve as serve_mod
        # 先确保 uvicorn 在 sys.modules
        mock_uvicorn = MagicMock()
        import sys
        sys.modules["uvicorn"] = mock_uvicorn
        importlib.reload(serve_mod)

        args = MagicMock(host="127.0.0.1", port=9000, reload=False)
        result = serve_mod.cmd_serve(args)
        assert result == 0
        mock_uvicorn.run.assert_called_once()
        call_kwargs = mock_uvicorn.run.call_args[1]
        assert call_kwargs["host"] == "127.0.0.1"
        assert call_kwargs["port"] == 9000

    def test_serve_with_reload(self):
        import importlib
        import dochris.cli.cli_serve as serve_mod
        mock_uvicorn = MagicMock()
        import sys
        sys.modules["uvicorn"] = mock_uvicorn
        importlib.reload(serve_mod)

        args = MagicMock(host="0.0.0.0", port=8000, reload=True)
        result = serve_mod.cmd_serve(args)
        assert result == 0
        assert mock_uvicorn.run.call_args[1]["reload"] is True

    @pytest.mark.skip("uvicorn module removal causes side effects in test env")
    def test_serve_no_uvicorn(self):
        import importlib
        import dochris.cli.cli_serve as serve_mod
        import sys
        # 移除 uvicorn 模拟 ImportError
        old = sys.modules.pop("uvicorn", None)
        try:
            importlib.reload(serve_mod)
            args = MagicMock()
            result = serve_mod.cmd_serve(args)
            assert result == 1
        finally:
            import uvicorn
            sys.modules["uvicorn"] = uvicorn
            importlib.reload(serve_mod)

    def test_serve_defaults(self):
        import importlib
        import dochris.cli.cli_serve as serve_mod
        mock_uvicorn = MagicMock()
        import sys
        sys.modules["uvicorn"] = mock_uvicorn
        importlib.reload(serve_mod)

        args = MagicMock(spec=[])  # no attributes → getattr defaults
        result = serve_mod.cmd_serve(args)
        assert result == 0
        call_kwargs = mock_uvicorn.run.call_args[1]
        assert call_kwargs["host"] == "0.0.0.0"
        assert call_kwargs["port"] == 8000


# promote tests need test_api/conftest.py client fixture — moved to test_api/test_promote.py
