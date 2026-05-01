# 快速上手

5 分钟体验 dochris 的完整工作流。

## 1. 初始化工作区

```bash
kb init
```

交互式创建目录结构和 `.env` 配置文件。

## 2. 准备学习资料

将 PDF、Markdown、音频等文件放入源目录（默认 `~/materials/`）。

## 3. 摄入文件

```bash
kb ingest
```

扫描源目录，创建 manifest，将文件链接到 `raw/`。

## 4. AI 编译

```bash
kb compile
```

- 自动提取关键概念
- 生成结构化摘要
- 建立知识关联
- 质量评分（阈值 85）

## 5. 查询知识库

```bash
kb query "费曼学习法"
kb query "深度学习" --mode concept
kb query "Python 装饰器" --mode summary
```

## 6. 晋升到 Wiki

```bash
kb promote SRC-0001 --to wiki
```

将高质量编译结果推送到 Obsidian Vault。
