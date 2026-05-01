# 项目架构

## 目录结构

```
dochris/
├── src/dochris/
│   ├── __init__.py          # 版本信息
│   ├── cli/                 # CLI 命令
│   │   ├── main.py          # 主入口
│   │   ├── cli_compile.py   # 编译命令
│   │   ├── cli_query.py     # 查询命令
│   │   └── ...
│   ├── core/                # 核心逻辑
│   │   ├── llm_client.py    # LLM 客户端
│   │   ├── text_chunker.py  # 文本分块
│   │   ├── quality_scorer.py # 质量评分
│   │   ├── cache.py         # 缓存
│   │   └── retry_manager.py # 重试管理
│   ├── phases/              # 编译阶段
│   │   ├── phase1_ingestion.py  # 摄入
│   │   ├── phase2_compilation.py # 编译
│   │   └── phase3_query.py      # 查询
│   ├── parsers/             # 文件解析器
│   │   ├── pdf_parser.py    # PDF
│   │   ├── doc_parser.py    # Word
│   │   └── code_parser.py   # 代码
│   ├── plugin/              # 插件系统
│   │   ├── registry.py      # 插件注册
│   │   ├── loader.py        # 插件加载
│   │   └── hookspec.py      # Hook 定义
│   ├── llm/                 # LLM 提供商
│   │   ├── base.py          # 抽象接口
│   │   ├── openai_compat.py # OpenAI 兼容
│   │   └── ollama.py        # Ollama
│   ├── vector/              # 向量存储
│   │   ├── base.py          # 抽象接口
│   │   ├── chromadb_store.py # ChromaDB
│   │   └── faiss_store.py   # FAISS
│   ├── settings/            # 配置管理
│   ├── admin/               # 管理工具
│   ├── quality/             # 质量管理
│   ├── vault/               # Obsidian 集成
│   ├── types.py             # 类型定义
│   ├── protocols.py         # 协议定义
│   ├── exceptions.py        # 异常类型
│   └── constants.py         # 常量
├── tests/                   # 测试
├── examples/                # 示例
├── benchmark/               # 性能基准
└── docs/                    # 文档
```

## 编译流程

```
Phase 1: Ingestion
  扫描源目录 → 创建 manifest → 链接文件到 raw/

Phase 2: Compilation
  提取文本 → 分块 → LLM 编译 → 质量评分 → 保存结果

Phase 3: Query
  搜索 manifest → 加载编译结果 → LLM 回答
```

## 设计原则

- **模块化**：每个阶段独立，可单独运行
- **可扩展**：插件系统支持自定义流程
- **多后端**：LLM 和向量库均可替换
- **类型安全**：mypy 严格模式，PEP 544 协议
- **质量优先**：自动评分，低质量自动重编译
