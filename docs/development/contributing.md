# 贡献指南

感谢你对 dochris 项目的关注！本文档介绍如何参与贡献。

## 开发环境搭建

```bash
# 克隆仓库
git clone https://github.com/caozhangqing85-cyber/dochris.git
cd dochris

# 创建虚拟环境
python -m venv .venv
source .venv/bin/activate

# 安装开发依赖
pip install -e ".[dev]"

# 验证安装
kb --help
kb doctor
```

## 开发工具

项目使用以下工具保证代码质量：

| 工具 | 用途 | 命令 |
|------|------|------|
| pytest | 测试 | `pytest tests/ -v` |
| ruff | 代码规范 | `ruff check src/` |
| mypy | 类型检查 | `mypy src/dochris/` |

## 代码规范

- **类型注解**：所有公共函数必须有参数和返回类型
- **Docstring**：所有公共函数和模块必须有 Google 风格 docstring
- **错误处理**：使用 `dochris.exceptions` 中的具体异常类型，不要 bare `except`
- **日志**：使用 `logging.getLogger(__name__)`，不要 `print()`
- **路径**：使用 `pathlib.Path`，不要字符串拼接
- **编码**：文件操作始终指定 `encoding='utf-8'`

## 提交规范

使用 Conventional Commits 格式：

```
<type>: <description>

<optional body>
```

类型：

| 类型 | 说明 |
|------|------|
| `feat` | 新功能 |
| `fix` | Bug 修复 |
| `refactor` | 代码重构 |
| `docs` | 文档更新 |
| `test` | 测试相关 |
| `chore` | 构建/工具 |
| `perf` | 性能优化 |
| `ci` | CI 配置 |

## Pull Request 流程

1. Fork 仓库
2. 创建特性分支：`git checkout -b feat/my-feature`
3. 编写代码和测试
4. 确保所有检查通过：
   ```bash
   pytest tests/ -v
   ruff check src/
   mypy src/dochris/
   ```
5. 提交 PR，描述改动内容和动机

## 测试要求

- 新功能必须包含测试
- 测试覆盖率目标：80%+
- 使用 `tmp_path` fixture 创建临时文件
- 使用 `monkeypatch` 修改环境变量
- 不要修改真实环境或 `~/.openclaw/` 下的文件

## 报告问题

在 [GitHub Issues](https://github.com/caozhangqing85-cyber/dochris/issues) 中提交，包含：

- 问题描述和复现步骤
- `kb doctor` 的输出
- 相关日志（`logs/` 目录）
- 系统环境信息
