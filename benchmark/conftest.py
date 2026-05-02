"""基准测试配置

共享 fixtures：样本文本、样例嵌入向量等。
"""

import pytest

pytest_plugins = ["pytest_benchmark"]


@pytest.fixture
def sample_text_short() -> str:
    """短文本样例（~500 字符）"""
    return "这是一段测试文本。" * 50


@pytest.fixture
def sample_text_medium() -> str:
    """中等文本样例（~5000 字符）"""
    paragraphs = []
    for i in range(50):
        paragraphs.append(
            f"## 第 {i + 1} 节\n\n"
            f"这是第 {i + 1} 节的内容，包含了一些技术关键词如算法、策略、模型、优化。"
            f"每个段落大约 100 个字符。\n"
        )
    return "\n\n".join(paragraphs)


@pytest.fixture
def sample_text_large() -> str:
    """大文本样例（~50000 字符）"""
    paragraphs = []
    for i in range(500):
        paragraphs.append(
            f"# 章节 {i + 1}\n\n"
            f"这是第 {i + 1} 章的详细内容。"
            f"包含了多种技术概念：机器学习、深度学习、自然语言处理、知识图谱。\n"
            f"段落中包含具体的方法论、实施策略和最佳实践。\n"
        )
    return "\n\n".join(paragraphs)


@pytest.fixture
def sample_embedding() -> list[float]:
    """样例嵌入向量（128 维）"""
    return [float(i) / 128.0 for i in range(128)]


@pytest.fixture
def sample_embeddings() -> list[list[float]]:
    """样例嵌入向量列表（10 个 128 维向量）"""
    return [[float(i * 10 + j) / 1280.0 for j in range(128)] for i in range(10)]
