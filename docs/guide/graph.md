# 知识图谱

dochris 内置知识图谱功能，自动构建概念之间的关联关系。

## 概述

知识图谱从编译结果中提取概念和关系，构建可视化的知识网络。

## 命令

### 查看图谱统计

```bash
kb graph stats
```

显示节点数量、边数量、连通分量等统计信息。

### 导出图谱

```bash
kb graph export                # 导出到 stdout
kb graph export -o graph.json  # 导出到文件
```

以 JSON 格式导出完整的知识图谱数据。

### 搜索图谱

```bash
kb graph search "深度学习"
```

在图谱节点中搜索相关概念，返回匹配节点及其关联。

## 图谱结构

```
节点（Concept）
├── name: 概念名称
├── type: 概念类型
├── sources: 来源文档列表
└── properties: 扩展属性

边（Relation）
├── source: 源概念
├── target: 目标概念
├── type: 关系类型
└── weight: 关系权重
```

## 工作流程

1. **编译时**：Phase 2 编译过程中自动提取概念
2. **构建时**：将概念和关系写入图谱数据库
3. **查询时**：支持通过关键词搜索和遍历图谱

## 与 Obsidian 集成

图谱概念可自动同步到 Obsidian，生成 `[[概念名]]` 格式的双向链接。
