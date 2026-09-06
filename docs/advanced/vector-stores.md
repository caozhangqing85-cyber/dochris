# 向量数据库

dochris 支持多种向量数据库后端用于语义搜索。

## 支持的后端

### ChromaDB（默认）

轻量级嵌入式向量数据库，无需额外服务。

```bash
# 默认使用，无需配置
kb query "关键词"
```

### FAISS

Meta 开源的高性能向量搜索库。

```bash
# 配置使用 FAISS
VECTOR_STORE=faiss
```

### LEANN（实验性）

超低存储占用的向量索引，安装 `pip install "dochris[leann]"` 后以 `VECTOR_STORE=leann` 启用。

**DEBT-03 评估结论（2026-09-06，维持实验性）**：

- 依赖体积与安装成本明显高于 ChromaDB/FAISS（引入额外编译依赖），对"个人知识库、
  中小语料"的默认用户是净负担，故不进入 `standard` extra；
- 适合磁盘极受限、语料量大且可接受更高查询延迟的场景；
- 在真实语料召回对比（见 [发布就绪 · RAG 质量门槛](../RELEASE.md)）中未参与评测，
  收益未经证明前不建议作为默认后端；
- 升级维护依赖上游 `leann` 包的活跃度，作为可选集成保留。

## 向量存储抽象

```
VectorStore (Protocol)
├── ChromaDBStore  ← 默认，嵌入式
└── FAISSStore     ← 高性能
```

## 配置

```env
VECTOR_STORE=chromadb  # 或 faiss
EMBEDDING_MODEL=BAAI/bge-small-zh-v1.5
```
