# 结构化日志

dochris 支持结构化日志输出，便于日志分析和监控。

## 日志格式

### 文本格式（默认）

```bash
kb compile --log-format text
```

输出人类可读的彩色日志。

### JSON 格式

```bash
kb compile --log-format json
```

输出结构化 JSON，便于 ELK/Datadog 集成：

```json
{
  "timestamp": "2026-05-01T12:00:00",
  "level": "INFO",
  "message": "编译完成",
  "context": {
    "source_id": "SRC-0001",
    "quality_score": 92
  }
}
```

## 配置

```bash
# CLI 参数
kb --log-format json compile

# 或环境变量
LOG_FORMAT=json
```

## 日志级别

- `DEBUG` — 详细调试信息
- `INFO` — 一般操作信息
- `WARNING` — 警告
- `ERROR` — 错误
- `CRITICAL` — 严重错误

使用 `--verbose` 切换到 DEBUG 级别。
