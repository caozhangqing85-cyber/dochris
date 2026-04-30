# 贡献指南

感谢你对 Dochris (知识库编译系统) 的关注！我们欢迎各种形式的贡献。

## 开发环境设置

### 前置要求

- Python 3.11+ 
- Git
- 虚拟环境工具（venv 或 conda）

### 克隆项目

```bash
git clone https://github.com/caozhangqing85-cyber/dochris.git
cd dochris
```

### 创建虚拟环境

```bash
# 使用 venv
python3.11 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 或使用 conda
conda create -n dochris python=3.11
conda activate dochris
```

### 安装依赖

```bash
# 安装核心依赖
pip install -e .

# 安装开发依赖（包含测试工具）
pip install -e ".[dev]"

# 或安装所有依赖（包含 PDF、OCR 支持）
pip install -e ".[all]"
```

### 配置环境变量

创建 `.env` 文件：

```bash
cp .env.example .env
# 编辑 .env 填入你的 API Key
```

## 代码规范

### Python 代码风格

遵循 [PEP 8](https://pep8.org/) 规范：

```python
# 好的示例
def compile_manifest(workspace: str, src_id: str) -> dict:
    """编译指定的 manifest。

    Args:
        workspace: 工作区路径
        src_id: 源 ID，格式如 SRC-0001

    Returns:
        包含编译结果的字典

    Raises:
        ManifestNotFoundError: 如果 manifest 不存在
        CompilationError: 如果编译失败
    """
    manifest = get_manifest(workspace, src_id)
    # ... 实现
```

### 规范要点

1. **类型注解**
   - 所有公共函数必须有类型注解
   - 使用 `typing` 模块的类型

2. **Docstring**
   - 使用 Google 风格的 docstring
   - 包含功能描述、参数说明、返回值、异常

3. **命名规范**
   - 函数/变量：`snake_case`
   - 类：`PascalCase`
   - 常量：`UPPER_SNAKE_CASE`
   - 私有成员：`_leading_underscore`

4. **代码长度**
   - 单行不超过 100 字符
   - 函数不超过 50 行
   - 文件不超过 800 行

### 代码格式化工具

项目使用 Ruff 进行代码检查和格式化：

```bash
# 检查代码
ruff check src/ tests/

# 格式化代码
ruff format src/ tests/
```

### 提交前检查

提交代码前请运行：

```bash
# 1. 运行代码检查
ruff check src/ tests/

# 2. 运行测试
pytest tests/ -v

# 3. 检查测试覆盖率
pytest tests/ --cov=dochris --cov-report=term-missing
```

## 测试要求

### 测试覆盖

- 新功能必须有测试覆盖
- 目标测试覆盖率：60%+
- Bug 修复需要添加回归测试

### 测试编写

使用 `pytest` 框架：

```python
# tests/core/test_quality_scorer.py
import pytest
from dochris.core.quality_scorer import score_summary_quality_v4

def test_score_summary_quality_v4_valid_input():
    """测试正常输入的评分"""
    summary = {
        "detailed_summary": "这是一段详细摘要" * 100,
        "key_points": ["要点1", "要点2", "要点3", "要点4"],
        "one_line": "这是一句话摘要",
        "concepts": [{"name": "概念1", "explanation": "解释"}],
    }
    score = score_summary_quality_v4(summary)
    assert 0 <= score <= 100

def test_score_summary_quality_v4_none_input():
    """测试 None 输入的容错"""
    score = score_summary_quality_v4(None)
    assert score == 0
```

### 运行测试

```bash
# 运行所有测试
pytest tests/ -v

# 运行特定文件
pytest tests/test_quality_scorer.py -v

# 运行特定测试函数
pytest tests/test_quality_scorer.py::test_score_summary_quality_v4 -v

# 运行带标记的测试
pytest tests/ -m "unit"           # 单元测试
pytest tests/ -m "integration"    # 集成测试
pytest tests/ -m "not slow"       # 排除慢速测试
```

### 测试覆盖率

```bash
# 生成覆盖率报告
pytest tests/ --cov=dochris --cov-report=term-missing

# 生成 HTML 覆盖率报告
pytest tests/ --cov=dochris --cov-report=html
# 报告位于 htmlcov/index.html
```

## 项目结构

项目使用标准 src layout：

```
dochris/
├── src/dochris/        # 主包
│   ├── __init__.py
│   ├── __main__.py
│   ├── cli/                # CLI 命令
│   │   ├── main.py
│   │   ├── cli_ingest.py
│   │   ├── cli_compile.py
│   │   └── ...
│   ├── core/               # 核心模块
│   │   ├── llm_client.py
│   │   ├── quality_scorer.py
│   │   ├── retry_manager.py
│   │   ├── text_chunker.py
│   │   ├── cache.py
│   │   └── utils.py
│   ├── parsers/            # 文件解析器
│   │   ├── pdf_parser.py
│   │   ├── doc_parser.py
│   │   └── code_parser.py
│   ├── phases/             # 流水线阶段
│   │   ├── phase1_ingestion.py
│   │   ├── phase2_compilation.py
│   │   └── phase3_query.py
│   ├── workers/            # 工作进程
│   │   ├── compiler_worker.py
│   │   └── monitor_worker.py
│   ├── vault/              # Obsidian 集成
│   ├── quality/            # 质量门禁
│   ├── settings.py         # 配置管理
│   ├── exceptions.py       # 异常定义
│   ├── log.py              # 日志工具
│   └── log_utils.py        # 日志工具
├── tests/                  # 测试文件
│   ├── test_*.py
│   └── fixtures/           # 测试数据
├── docs/                   # 额外文档
├── pyproject.toml
├── README.md
└── LICENSE
```

### 添加新功能时的位置选择

| 功能类型 | 位置 |
|---------|------|
| 共享工具函数 | `src/dochris/core/` |
| 特定文件类型处理 | `src/dochris/parsers/` |
| 新的流水线阶段 | `src/dochris/phases/` |
| CLI 命令 | `src/dochris/cli/` |
| 工作进程 | `src/dochris/workers/` |
| 配置/常量 | `src/dochris/settings.py` |
| 异常定义 | `src/dochris/exceptions.py` |

## 提交规范

### Conventional Commits

使用 [Conventional Commits](https://www.conventionalcommits.org/) 格式：

```
<type>: <description>

[optional body]
```

### 类型（Type）

- `feat`: 新功能
- `fix`: Bug 修复
- `refactor`: 代码重构（不改变功能）
- `docs`: 文档更新
- `test`: 测试相关
- `chore`: 构建/工具相关
- `perf`: 性能优化
- `ci`: CI 配置

### 示例

```bash
feat: 添加 PDF 并发编译支持
- 支持最多 4 个并发任务
- 添加进度条显示

fix: 修复质量评分总是 10 分的问题
- 调整学习价值关键词权重
- 修复 None 值处理逻辑

docs: 更新 README 安装说明

refactor: 统一日志系统
- 添加 get_logger() 函数
- 合并 log.py 和 log_utils.py
```

## Pull Request 流程

### 1. Fork 项目

点击 GitHub 页面右上角的 "Fork" 按钮。

### 2. 创建功能分支

```bash
git checkout -b feat/your-feature-name
# 或
git checkout -b fix/your-bug-fix
```

### 3. 提交代码

```bash
git add .
git commit -m "feat: 添加新功能描述"
```

### 4. 推送到你的 Fork

```bash
git push origin feat/your-feature-name
```

### 5. 创建 Pull Request

在 GitHub 上创建 Pull Request，填写：

- **标题**：简洁描述改动
- **内容**：
  - 改动说明
  - 相关 Issue
  - 测试情况
  - 截图（如适用）

### PR 检查清单

提交 PR 前确认：

- [ ] 代码通过 `ruff check` 检查
- [ ] 所有测试通过 `pytest tests/ -v`
- [ ] 测试覆盖率保持或提升
- [ ] 添加了必要的测试用例
- [ ] 更新了相关文档
- [ ] Commit 遵循 Conventional Commits 规范

## Code Review

### PR 审查要点

1. **功能正确性**
   - 代码是否实现预期功能
   - 边界条件是否处理

2. **代码质量**
   - 是否遵循代码规范
   - 是否有足够的测试
   - 是否有必要的文档

3. **向后兼容**
   - 是否破坏现有功能
   - 是否需要更新文档

### 审查流程

1. 自动检查通过（CI/CD）
2. 至少一名维护者审查
3. 所有审查意见被解决
4. 合并到主分支

## 行为准则

- 尊重所有贡献者
- 建设性的讨论和反馈
- 接受不同的观点和经验

## 沟通渠道

- **GitHub Issues**: Bug 报告、Feature Request
- **GitHub PRs**: 代码审查
- **GitHub Discussions**: 一般讨论、问题求助

## 许可证

贡献的代码将使用 [MIT License](LICENSE) 发布。

---

再次感谢你的贡献！
