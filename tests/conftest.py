"""
pytest 配置和共享 fixtures
"""

from collections.abc import Generator
from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def reset_global_state(monkeypatch: pytest.MonkeyPatch) -> None:
    """每个测试后重置全局状态（防止测试间状态泄漏）

    Args:
        monkeypatch: pytest monkeypatch fixture
    """
    from dochris.settings import reset_settings

    yield

    # 测试结束后重置全局设置
    reset_settings()


@pytest.fixture
def temp_workspace(tmp_path: Path) -> Generator[Path, None, None]:
    """创建临时工作区

    Args:
        tmp_path: pytest 提供的临时路径

    Yields:
        临时工作区路径
    """
    workspace = tmp_path / "kb"
    workspace.mkdir()

    # 创建必要的子目录
    (workspace / "raw").mkdir()
    (workspace / "wiki").mkdir()
    (workspace / "wiki" / "summaries").mkdir(parents=True)
    (workspace / "wiki" / "concepts").mkdir(parents=True)
    (workspace / "outputs").mkdir()
    (workspace / "outputs" / "summaries").mkdir(parents=True)
    (workspace / "outputs" / "concepts").mkdir(parents=True)
    (workspace / "manifests").mkdir()
    (workspace / "manifests" / "sources").mkdir(parents=True)
    (workspace / "data").mkdir()
    (workspace / "logs").mkdir()
    (workspace / "cache").mkdir()

    yield workspace


@pytest.fixture
def mock_api_key(monkeypatch: pytest.MonkeyPatch) -> str:
    """模拟 API 密钥

    Args:
        monkeypatch: pytest monkeypatch fixture

    Returns:
        模拟的 API 密钥
    """
    api_key = "test-api-key-12345678"
    monkeypatch.setenv("OPENAI_API_KEY", api_key)
    return api_key


@pytest.fixture
def sample_text() -> str:
    """示例文本内容"""
    return """
    这是一个关于学习方法的文档。

    ## 要点
    - 费曼技巧是一种有效的学习方法
    - 通过教别人来学习，可以加深理解
    - 简化复杂概念是关键
    """
