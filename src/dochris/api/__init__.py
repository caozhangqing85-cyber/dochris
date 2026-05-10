"""dochris REST API — FastAPI 层

提供知识库的 HTTP API 接口。

用法:
    pip install dochris[api]
    kb serve --host 0.0.0.0 --port 8000
"""

from dochris.api.app import create_app

__all__ = ["create_app"]

try:
    from dochris.api.app import app  # noqa: F401
except ImportError:
    app = None  # type: ignore[assignment]
