# 晋升到 Wiki

将高质量编译结果推送到 Obsidian Vault 或知识库 Wiki。

## 晋升条件

文档必须满足：

- ✅ 编译成功
- ✅ 质量评分 ≥ 阈值（默认 85）
- ✅ 摘要内容完整

## 单个晋升

```bash
# 晋升到 Wiki
kb promote SRC-0001 --to wiki

# 晋升到 Obsidian Vault
kb promote SRC-0001 --to obsidian
```

## 批量晋升

```bash
# 晋升所有高质量文档
kb promote --all --quality 90
```

## 晋升内容

晋升时生成：

- **主文档**：结构化的知识卡片
- **元数据**：来源、质量分、编译时间
- **双向链接**：自动生成 `[[概念名]]` 格式的 Obsidian 链接

## Manifest 更新

晋升后 manifest 状态更新：

```
compiled → promoted_to_wiki
compiled → promoted
```
