# dochris

**AI 驱动的个人知识库编译系统**

将碎片化的学习资料（PDF、音频、视频、电子书、Markdown）编译成结构化的知识库，支持 Obsidian Wiki 晋升。

## 快速开始

```bash
pip install dochris
kb init                    # 初始化工作区
kb ingest                  # 摄入文件
kb compile                 # AI 编译
kb query "费曼技巧"        # 智能查询
```

## 特性

- :material-file-document-multiple: **多格式支持** — PDF、Markdown、Word、音频、视频、代码、EPUB
- :material-brain: **AI 编译** — 自动提取概念、生成摘要、建立知识关联
- :material-check-decagram: **质量评估** — 自动评分（0-100），低于阈值自动重编译
- :material-arrow-up-bold: **Wiki 晋升** — 一键推送到 Obsidian Vault
- :material-puzzle: **插件系统** — 6 个扩展点，自定义编译流程
- :material-robot: **多 LLM 支持** — 智谱 GLM、OpenAI 兼容、Ollama 本地模型
- :material-database: **多向量库** — ChromaDB、FAISS
- :material-graph: **知识图谱** — 自动构建概念关联图谱
- :material-web: **Web UI** — Gradio 可视化界面
- :material-api: **REST API** — FastAPI HTTP 接口

## 四阶段流水线

```
源文件 → Phase 1 摄入 → Phase 2 编译 → Phase 3 查询 → Phase 4 分发
```

| 阶段 | 功能 | 命令 |
|------|------|------|
| Phase 1 | 文件扫描、去重、Manifest 生成 | `kb ingest` |
| Phase 2 | 文本提取、LLM 编译、质量评分 | `kb compile` |
| Phase 3 | 语义搜索、LLM 增强查询 | `kb query` |
| Phase 4 | Wiki 晋升、Obsidian 同步 | `kb promote` |

## 四层信任模型

| 层级 | 目录 | 信任度 |
|------|------|--------|
| L0 | `outputs/` | 未验证（LLM 原始输出） |
| L1 | `wiki/` | 半可信（质量≥85） |
| L2 | `curated/` | 可信（人工审核） |
| L3 | `locked/` | 不可变（锁定） |

## 项目状态

| 指标 | 数值 |
|------|------|
| 测试 | 2402 passing |
| 覆盖率 | 76.03% |
| 类型检查 | mypy 0 errors |
| 代码规范 | ruff 0 errors |
| Python | 3.11+ |
| 许可证 | MIT |

## 链接

- [PyPI](https://pypi.org/project/dochris/)
- [GitHub](https://github.com/caozhangqing85-cyber/dochris)
- [贡献指南](development/contributing.md)
- [API 参考](api/overview.md)

