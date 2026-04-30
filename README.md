# Dochris

> **Doc + Chris** — 用 LLM 锻造你的个人知识库

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![CI](https://img.shields.io/github/actions/workflow/status/caozhangqing85-cyber/dochris/ci.yml?branch=main)](https://github.com/caozhangqing85-cyber/dochris/actions)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![PyPI](https://img.shields.io/pypi/v/dochris)](https://pypi.org/project/dochris/)

**"Doc"** 代表文档，**"Chris"** 是作者的名字。Dochris 意味着：**让文档为 Chris 服务** — 将海量信息锻造为可用的知识。

Dochris 是一个 AI 驱动的知识库编译系统，通过**四阶段流水线**和**四层信任模型**，将散落的文件转化为结构化、可搜索、可验证的知识库，并支持与 Obsidian 双向同步。

## 为什么选择 Dochris？

- **结构化输出**：自动提取摘要、关键点、概念，不再是零散的文件
- **质量把关**：多维度评分系统（0-100 分），确保只有高质量内容进入知识库
- **信任分层**：四层信任模型，从 LLM 生成到人工精选，逐步提升可信度
- **多格式支持**：PDF、音频、视频、电子书、文章，一个系统全搞定
- **Obsidian 联动**：支持双向同步，高质量内容可推送回 Obsidian 笔记库

## 系统架构

```mermaid
graph TB
    subgraph Input["📥 输入层"]
        A[原始文件<br/>PDF / MD / TXT / 音频] --> B[Phase 1: 摄入]
    end

    subgraph Process["⚙️ 处理层"]
        B --> C[文本提取<br/>PDF→MD / 音频→TXT]
        C --> D[Phase 2: 编译]
        D --> E[LLM 摘要生成]
        E --> F[Phase 2.5: 补偿]
        F --> G[失败重试<br/>降级处理]
    end

    subgraph Storage["💾 存储层"]
        D --> H[(Manifests<br/>元数据索引)]
        E --> I[(Wiki<br/>结构化知识)]
        D --> J[(ChromaDB<br/>向量索引)]
    end

    subgraph Output["📤 输出层"]
        I --> K[Phase 3: 查询]
        J --> K
        K --> L[知识检索 + LLM 回答]
        I --> M[Obsidian 双向同步]
    end
```

```
┌─────────────────────────────────────────────────────────────────────┐
│                         四阶段流水线                                  │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐      │
│  │ Phase 1  │───▶│ Phase 2  │───▶│ Phase 3  │───▶│ Phase 4  │      │
│  │  摄入    │    │  编译    │    │  审核    │    │  分发    │      │
│  └──────────┘    └──────────┘    └──────────┘    └──────────┘      │
│       │               │               │               │             │
│       ▼               ▼               ▼               ▼             │
│   扫描文件       LLM 提取       质量评分        晋升信任层          │
│   创建去重       结构化内容       污染检测        同步 Obsidian       │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│                         四层信任模型                                  │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  Layer 3: locked/    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━  锁定  │
│           │                                                         │
│           ▼                                                         │
│  Layer 2: curated/    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━  人工精选│
│           │                                                         │
│           ▼                                                         │
│  Layer 1: wiki/       ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━  质量审核│
│           │                  (score ≥ 85)                         │
│           ▼                                                         │
│  Layer 0: outputs/    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━  LLM 生成│
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

## 功能特性

### 四阶段流水线

| 阶段 | 功能 | 输出 |
|------|------|------|
| **Phase 1 摄入** | 扫描文件、去重、创建 manifest | `manifests/sources/SRC-NNNN.json` |
| **Phase 2 编译** | LLM 提取结构化内容 | `outputs/` (摘要+概念) |
| **Phase 3 审核** | 质量评分、污染检测 | 质量分数 0-100 |
| **Phase 4 分发** | 晋升信任层、同步 Obsidian | `wiki/` → `curated/` → Obsidian |

### 四层信任模型

```
Layer 0: outputs/     — LLM 生成，不可信（默认）
Layer 1: wiki/        — 质量分 ≥ 85，半可信
Layer 2: curated/     — 人工精选，可信
Layer 3: locked/      — 锁定保护，不可修改
```

### 质量评分系统

总分 100 分，85 分及格：

| 维度 | 分值 | 说明 |
|------|------|------|
| 摘要长度 | 0-35 | 800-1500 字最优 |
| 关键点完整性 | 0-40 | 4-5 个独立要点 |
| 学习价值 | 0-25 | 方法/策略/技巧密度 |
| 信息密度 | 0-10 | 具体技术/工具密度 |
| 概念完整性 | 0-20 | 3-5 个完整概念 |

## 快速开始

### 系统要求

- Python 3.11+
- 4GB+ RAM（推荐 8GB）
- OpenAI 兼容的 API Key

### 安装

```bash
# 克隆项目
git clone https://github.com/caozhangqing85-cyber/dochris.git
cd dochris

# 创建虚拟环境
python3.11 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 安装依赖
pip install -e .

# 创建配置文件
cp .env.example .env
# 编辑 .env 填入你的 API Key
```

### 配置

在 `.env` 文件中添加：

```bash
# LLM API 配置（必需）
OPENAI_API_KEY=your_api_key_here
OPENAI_API_BASE=https://open.bigmodel.cn/api/paas/v4
MODEL=glm-5.1

# 查询专用模型（可选，默认 glm-4-flash）
QUERY_MODEL=glm-4-flash

# 工作区路径（可选，默认 ~/.knowledge-base）
WORKSPACE=~/.knowledge-base

# 本地 LLM 配置（可选，用于兜底）
LOCAL_LLM_BASE_URL=http://localhost:11434/v1
LOCAL_LLM_MODEL=qwen:14b
```

### 使用流程

```bash
# 1. 查看系统状态
kb status

# 2. 摄入文件（扫描源文件并创建 manifest）
kb ingest

# 3. 编译（LLM 提取结构化内容）
kb compile 10          # 编译前 10 个文件
kb compile --concurrency 4  # 使用 4 个并发

# 4. 查询知识库
kb query "费曼技巧"

# 5. 质量检查与晋升
kb quality --report
kb promote SRC-0001 --to wiki
kb promote SRC-0001 --to obsidian
```

### 5 分钟快速体验

```bash
# 1. 创建测试目录
mkdir -p ~/test-kb/raw/pdfs
cp your-file.pdf ~/test-kb/raw/pdfs/

# 2. 设置工作区
export WORKSPACE=~/test-kb

# 3. 摄入文件
kb ingest

# 4. 编译
kb compile

# 5. 查看结果
cat ~/test-kb/outputs/summaries/SRC-0001.md
```

## 目录结构

```
knowledge-base/
├── src/dochris/              # 主包
│   ├── cli/                      # CLI 命令
│   ├── core/                     # 核心模块
│   │   ├── llm_client.py         # LLM 异步客户端
│   │   ├── summary_generator.py  # 基础摘要生成器
│   │   ├── hierarchical_summarizer.py  # 分层摘要器（Map-Reduce）
│   │   ├── quality_scorer.py     # 质量评分
│   │   ├── text_chunker.py       # 文本分块
│   │   ├── cache.py              # 缓存管理
│   │   └── utils.py              # 通用工具
│   ├── parsers/                  # 文件解析器
│   │   ├── pdf_parser.py         # PDF 解析
│   │   ├── doc_parser.py         # 文档解析
│   │   └── code_parser.py        # 代码解析
│   ├── phases/                   # 流水线阶段
│   │   ├── phase1_ingestion.py   # 摄入阶段
│   │   ├── phase2_compilation.py # 编译阶段
│   │   ├── phase3_query.py       # 查询阶段
│   │   ├── query_engine.py       # 查询引擎
│   │   └── query_utils.py        # 查询工具
│   ├── workers/                  # 工作进程
│   │   ├── compiler_worker.py    # 编译 worker
│   │   └── monitor_worker.py     # 监控 worker
│   ├── quality/                  # 质量管理
│   │   ├── quality_gate.py       # 质量门禁
│   │   └── quality_monitor.py    # 质量监控
│   ├── compensate/               # 失败补偿
│   ├── admin/                    # 管理工具
│   ├── vault/                    # Obsidian 集成
│   ├── settings.py               # 配置管理
│   ├── exceptions.py             # 异常定义
│   ├── manifest.py               # Manifest 管理
│   ├── promote.py                # 晋升机制
│   └── log.py                    # 日志工具
├── tests/                        # 测试文件
├── docs/                         # 文档
├── manifests/                    # Manifest 存储
├── raw/                          # 原始文件（符号链接）
├── outputs/                      # Layer 0: LLM 产物
├── wiki/                         # Layer 1: 经审核
├── curated/                      # Layer 2: 人工精选
└── logs/                         # 编译日志
```

## CLI 命令参考

| 命令 | 说明 |
|------|------|
| `kb status` | 显示系统状态概览 |
| `kb ingest [path]` | Phase 1: 摄入文件 |
| `kb compile [limit]` | Phase 2: 编译文档 |
| `kb query "关键词"` | Phase 3: 查询知识库 |
| `kb promote <id> --to <target>` | 晋升到信任层 |
| `kb quality [--report]` | 质量检查 |
| `kb vault seed "主题"` | 从 Obsidian 拉取笔记 |
| `kb config` | 显示当前配置 |
| `kb version` | 显示版本信息 |

## 常见问题

### Q: 编译时出现 API 内容过滤错误（400, error 1301）

A: 这是智谱 API 的内容审核机制。系统会自动清洗敏感词，如仍遇到问题，可尝试使用其他 API 提供商。

### Q: 质量评分总是 10 分

A: 这是评分算法与模型输出不匹配的问题。重试编译通常会获得正确分数。

### Q: 如何加快编译速度

A: 修改 `MAX_CONCURRENCY` 参数提高并发数（默认 3），或使用 `nohup` 后台运行。

## 开发

### 运行测试

```bash
# 安装测试依赖
pip install -e ".[dev]"

# 运行测试
pytest tests/ -v

# 查看覆盖率
pytest tests/ --cov=dochris --cov-report=term-missing
```

### 代码规范

- 遵循 PEP 8
- 使用类型注解
- Docstring 使用中文
- 单行长度不超过 100 字符
- 使用 Ruff 进行代码检查和格式化

## 贡献

欢迎提交 Issue 和 Pull Request！详见 [CONTRIBUTING.md](CONTRIBUTING.md)

## 安全

如发现安全漏洞，请查看 [SECURITY.md](SECURITY.md) 了解报告流程。

## 许可证

MIT License — 详见 [LICENSE](LICENSE)

## 致谢

- [markitdown](https://github.com/microsoft/markitdown) — 多格式文件解析
- [ChromaDB](https://www.trychroma.com/) — 向量数据库
- [BAAI/bge-small-zh-v1.5](https://huggingface.co/BAAI/bge-small-zh-v1.5) — 中文语义嵌入

---

**Made with ❤️ for personal knowledge management**
