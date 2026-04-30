# Performance Benchmarks

使用 pytest-benchmark 运行基准测试。

## 运行

```bash
pip install pytest-benchmark
pytest benchmark/ --benchmark-only
```

## 基准

- `bench_parsers.py` — 文件解析性能
- `bench_quality.py` — 质量评分性能
- `bench_query.py` — 查询性能
