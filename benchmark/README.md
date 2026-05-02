# Performance Benchmarks

使用 pytest-benchmark 运行基准测试。

## 运行

```bash
pip install pytest-benchmark
pytest benchmark/ --benchmark-only
```

## 基准文件

| 文件 | 测试内容 |
|------|---------|
| `bench_parsers.py` | 文件解析性能（Markdown、类型检测） |
| `bench_quality.py` | 质量评分性能 |
| `bench_query.py` | 查询引擎性能（关键词搜索、向量检索） |
| `bench_compilation.py` | 编译流水线性能（分块、评分） |
| `bench_vector.py` | 向量存储读写性能（增删查） |
| `bench_indexing.py` | 索引性能（manifest、缓存、哈希） |

## 共享 Fixtures

`conftest.py` 提供以下 fixtures：

- `sample_text_short` — ~500 字符
- `sample_text_medium` — ~5000 字符
- `sample_text_large` — ~50000 字符
- `sample_embedding` — 128 维向量
- `sample_embeddings` — 10 个 128 维向量

## 注意事项

- 所有 benchmark 使用 mock 避免真实 LLM API 调用
- 使用 `--benchmark-only` 只运行基准测试
- 使用 `make bench-report` 生成报告
