# CLI 命令参考

## 全局选项

```bash
kb --verbose          # 详细输出
kb --quiet            # 静默模式
kb --log-format json  # JSON 日志格式
kb --completion bash  # Shell 补全
kb version            # 显示版本
```

## 核心命令

### `kb init`

初始化工作区，创建目录结构和配置文件。

```bash
kb init
```

### `kb ingest`

Phase 1：摄入文件，创建 manifest。

```bash
kb ingest                      # 使用默认源目录
kb ingest /path/to/materials   # 指定源目录
kb ingest --dry-run            # 模拟运行
```

### `kb compile`

Phase 2：AI 编译文档。

```bash
kb compile                     # 编译所有待编译文档
kb compile 10                  # 编译前 10 个
kb compile --concurrency 4     # 4 个并发
kb compile --quality 90        # 质量门槛 90
```

### `kb query`

Phase 3：查询知识库。

```bash
kb query "费曼技巧"                # 综合查询
kb query "深度学习" --mode concept  # 仅搜索概念
kb query "Python" --mode summary   # 仅搜索摘要
kb query "AI" --limit 5            # 限制结果数
```

### `kb promote`

晋升操作。

```bash
kb promote SRC-0001 --to wiki     # 晋升到 Wiki
kb promote SRC-0001 --to obsidian # 晋升到 Obsidian
kb promote --all --quality 90     # 批量晋升
```

### `kb quality`

质量管理。

```bash
kb quality              # 检查待编译文档
kb quality --report     # 生成质量报告
```

### `kb vault`

Obsidian Vault 联动。

```bash
kb vault seed "财富自由"    # 拉取相关笔记
kb vault status            # 查看 Vault 状态
```

### `kb config`

显示当前配置。

```bash
kb config
```

### `kb doctor`

环境诊断。

```bash
kb doctor        # 全部检查
kb doctor --fix  # 自动修复
```

### `kb plugin`

插件管理。

```bash
kb plugin list              # 列出插件
kb plugin info my-plugin    # 插件详情
kb plugin enable my-plugin  # 启用插件
kb plugin disable my-plugin # 禁用插件
kb plugin load /path/to/plugin.py  # 加载插件
```

### `kb status`

系统状态概览。

```bash
kb status
```

### `kb serve`

启动 HTTP API 服务器。

```bash
kb serve                 # 默认 localhost:8000
kb serve --port 9000     # 自定义端口
kb serve --reload        # 开发模式（热重载）
```

## 退出码

| 码 | 含义 |
|----|------|
| 0 | 成功 |
| 1 | 通用错误 |
| 2 | 参数错误 |
| 3 | 配置错误 |
| 4 | 网络错误 |
| 5 | 权限错误 |
