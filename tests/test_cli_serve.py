"""测试 cli_serve.py — 启动 API 服务器"""

from unittest.mock import MagicMock, patch


class TestCmdServe:
    """测试 cmd_serve 函数"""

    def test_cmd_serve_missing_uvicorn(self):
        """没有 uvicorn 时返回 1"""
        from dochris.cli.cli_serve import cmd_serve

        args = MagicMock(spec=[], host="0.0.0.0", port=8000, reload=False)

        with patch.dict("sys.modules", {"uvicorn": None}):
            with patch("builtins.__import__", side_effect=ImportError("no uvicorn")):
                result = cmd_serve(args)

        assert result == 1

    @patch("uvicorn.run")
    def test_cmd_serve_default_args(self, mock_run):
        """默认参数传递给 uvicorn"""
        from dochris.cli.cli_serve import cmd_serve

        args = MagicMock(spec=[], host="127.0.0.1", port=8000, reload=False)

        with patch("builtins.print"):
            result = cmd_serve(args)

        mock_run.assert_called_once_with(
            "dochris.api.app:app",
            host="127.0.0.1",
            port=8000,
            reload=False,
        )
        assert result == 0

    @patch("uvicorn.run")
    def test_cmd_serve_custom_args(self, mock_run):
        """自定义 host/port/reload 参数"""
        from dochris.cli.cli_serve import cmd_serve

        args = MagicMock(spec=[], host="127.0.0.1", port=9000, reload=True)

        with patch("builtins.print"):
            result = cmd_serve(args)

        mock_run.assert_called_once_with(
            "dochris.api.app:app",
            host="127.0.0.1",
            port=9000,
            reload=True,
        )
        assert result == 0

    @patch("uvicorn.run")
    def test_cmd_serve_missing_attrs_uses_defaults(self, mock_run):
        """args 缺少属性时使用默认值"""
        from dochris.cli.cli_serve import cmd_serve

        args = object()

        with patch("builtins.print"):
            result = cmd_serve(args)

        mock_run.assert_called_once_with(
            "dochris.api.app:app",
            host="127.0.0.1",
            port=8000,
            reload=False,
        )
        assert result == 0

    @patch("uvicorn.run")
    def test_cmd_serve_public_host_requires_api_key(self, mock_run, monkeypatch):
        """监听公网地址时必须显式配置 API key"""
        from dochris.cli.cli_serve import cmd_serve

        monkeypatch.delenv("DOCHRIS_API_KEY", raising=False)
        args = MagicMock(spec=[], host="0.0.0.0", port=8000, reload=False)

        with patch("builtins.print"):
            result = cmd_serve(args)

        assert result == 1
        mock_run.assert_not_called()

    @patch("uvicorn.run")
    def test_cmd_serve_web_uses_mounted_app(self, mock_run):
        """Web UI 使用 Gradio 返回的 mounted app 启动"""
        from dochris.cli.cli_serve import cmd_serve

        fastapi_app = MagicMock(name="fastapi_app")
        gradio_app = MagicMock(name="gradio_app")
        mounted_app = MagicMock(name="mounted_app")
        args = MagicMock(spec=[], host="127.0.0.1", web_port=7860, web=True)

        with (
            patch("dochris.api.app.create_app", return_value=fastapi_app),
            patch("dochris.web.app.create_web_app", return_value=gradio_app),
            patch("gradio.mount_gradio_app", return_value=mounted_app) as mock_mount,
            patch("builtins.print"),
        ):
            result = cmd_serve(args)

        mock_mount.assert_called_once_with(
            fastapi_app,
            gradio_app,
            path="/ui",
            server_name="127.0.0.1",
            server_port=7860,
        )
        mock_run.assert_called_once_with(mounted_app, host="127.0.0.1", port=7860)
        assert result == 0
