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
