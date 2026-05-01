# 插件系统

dochris 提供 6 个扩展点，支持自定义编译流程。

## 扩展点

| Hook | 触发时机 | 用途 |
|------|----------|------|
| `ingest_parser` | 文件摄入时 | 自定义文件解析器 |
| `pre_compile` | 编译前 | 预处理、过滤 |
| `post_compile` | 编译后 | 后处理、通知 |
| `quality_score` | 质量评分时 | 自定义评分维度 |
| `pre_query` | 查询前 | 查询预处理 |
| `post_query` | 查询后 | 结果后处理 |

## 编写插件

```python
# my_plugin.py
from dochris.plugin.hookspec import hookimpl

@hookimpl
def pre_compile(manifest: dict) -> dict:
    """编译前处理"""
    print(f"即将编译: {manifest['filename']}")
    return manifest

@hookimpl
def post_compile(manifest: dict, result: dict) -> None:
    """编译后通知"""
    score = result.get("quality_score", 0)
    print(f"编译完成，质量分: {score}")
```

## 加载插件

```bash
# CLI 加载
kb plugin load /path/to/my_plugin.py

# 列出已加载插件
kb plugin list

# 查看插件详情
kb plugin info my_plugin

# 启用/禁用
kb plugin enable my_plugin
kb plugin disable my_plugin
```

## 配置

在 `settings.json` 中配置自动加载：

```json
{
  "plugins": {
    "enabled": ["my_plugin"],
    "directories": ["/path/to/plugins/"]
  }
}
```

## 示例插件

查看 `examples/` 目录：

- `01_basic_ingest.py` — 基础摄入
- `06_plugin_hooks.py` — 完整插件示例
