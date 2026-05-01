# dochris

> AI 驱动的个人知识库编译系统

**将碎片化的学习资料编译成结构化的知识库，支持 Obsidian Wiki 晋升。**

```bash
pip install dochris
kb init          # 初始化工作区
kb ingest        # 摄入文件
kb compile       # AI 编译
kb query "费曼技巧"  # 智能查询
```

## ✨ 特性

- **多格式支持**：PDF、Markdown、Word、音频、代码等
- **AI 编译**：自动提取概念、生成摘要、建立关联
- **质量评估**：自动评分，低于阈值重新编译
- **Wiki 晋升**：一键推送到 Obsidian Vault
- **插件系统**：6 个扩展点，自定义编译流程
- **多 LLM 支持**：智谱 GLM、OpenAI 兼容、Ollama 本地模型
- **多向量库**：ChromaDB、FAISS

## 📊 项目状态

| 指标 | 数值 |
|------|------|
| 测试 | 2402 passing |
| 覆盖率 | 76.03% |
| 类型检查 | mypy 0 errors |
| 代码规范 | ruff 0 errors |
| Python | 3.11+ |
| 许可证 | MIT |

## 🔗 链接

- [PyPI](https://pypi.org/project/dochris/)
- [GitHub](https://github.com/caozhangqing85-cyber/dochris)
- [贡献指南](CONTRIBUTING.md)
- [变更日志](CHANGELOG.md)
