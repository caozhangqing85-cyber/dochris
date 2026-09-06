# 测试策略

## 测试结构

```
tests/
├── unit/              # 单元测试
│   ├── test_quality_scorer.py
│   ├── test_text_chunker.py
│   └── ...
├── integration/       # 集成测试
│   ├── test_compilation.py
│   └── ...
└── conftest.py        # 共享 fixtures
```

## 运行测试

```bash
# 运行全部测试
pytest tests/ -v

# 运行特定模块
pytest tests/unit/test_quality_scorer.py -v

# 运行并生成覆盖率报告
pytest tests/ --cov=dochris --cov-report=term-missing

# 运行标记的测试
pytest tests/ -m "not slow" -v
```

## 编写测试

### AAA 模式

使用 Arrange-Act-Assert 结构：

```python
def test_quality_score_calculation():
    # Arrange
    summary = "这是一篇关于深度学习的文章..."
    concepts = [{"name": "深度学习", "definition": "..."}]

    # Act
    score = QualityScorer().score(summary, concepts)

    # Assert
    assert score >= 0
    assert score <= 100
```

### 测试安全规则

!!! warning "测试安全"
    - **禁止**写入 `~/.openclaw/` 下的真实文件
    - **必须**使用 `tmp_path` 创建临时文件
    - **必须**使用 `monkeypatch` 修改环境变量
    - **必须**在 teardown 中清理副作用

### Fixture 使用

```python
# conftest.py
import pytest
from pathlib import Path

@pytest.fixture
def workspace(tmp_path):
    """创建临时工作区"""
    ws = tmp_path / "workspace"
    ws.mkdir()
    (ws / "raw").mkdir()
    (ws / "manifests").mkdir()
    (ws / "outputs").mkdir()
    return ws

@pytest.fixture
def mock_env(monkeypatch):
    """设置测试环境变量"""
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("WORKSPACE", "/tmp/test-workspace")
```

### Mock LLM 调用

```python
from unittest.mock import patch, MagicMock

def test_compilation_with_mock_llm():
    with patch("dochris.core.llm_client.LLMClient.compile") as mock_compile:
        mock_compile.return_value = {
            "summary": "测试摘要",
            "concepts": [],
            "quality_score": 90
        }
        # 测试逻辑...
```

## 覆盖率目标

| 模块 | 目标覆盖率 |
|------|-----------|
| `core/` | 90% |
| `phases/` | 80% |
| `parsers/` | 85% |
| `cli/` | 70% |
| 整体 | 80% |

## CI 集成

测试在 GitHub Actions 中自动运行：

- 每次 push 到 `main`
- 每个 Pull Request
- 覆盖率报告上传到 Codecov

## coverage_boost 套件审计（DEBT-04/05，2026-09-06）

对 21 个 `test_coverage_boost*.py`（约 7,988 行、560 个测试函数）的 AST 级审计结论：

- **无 `assert True` / 纯 mock 空转**的垃圾测试（此类为 0）；
- 9 处主动 skip、3 个"不崩即过"的冒烟测试（已全部补上真实断言：
  `test_main_no_progress`、`test_main_with_severe_alerts`、`test_cleanup_empty`）；
- 断言密度整体可接受：绝大多数测试函数含 assert 或 patch 结构化上下文。

处置决定：**保留该套件**，不再按领域拆分迁移（DEBT-05）——迁移的收益（文件名可读性）
低于大规模移动带来的回归风险；后续新增测试一律按领域命名，存量文件随触碰随整理。
