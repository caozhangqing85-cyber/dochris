# 查询知识库

编译完成后，可以通过自然语言查询知识库。

## 查询模式

### 综合查询（默认）

```bash
kb query "费曼学习法的核心原理"
```

搜索概念和摘要，返回最相关的知识片段。

### 概念模式

```bash
kb query "深度学习" --mode concept
```

仅在编译提取的概念中搜索，适合查找特定术语。

### 摘要模式

```bash
kb query "Python 装饰器" --mode summary
```

仅在文档摘要中搜索，适合查找主题概述。

## 查询选项

```bash
kb query "关键词" --limit 5     # 限制返回数量
kb query "关键词" --source pdf   # 限定来源类型
```

## LLM 增强

查询结果会经过 LLM 二次处理，生成更精准的回答。支持多种 LLM 后端：

- **智谱 GLM**（默认）
- **OpenAI 兼容 API**
- **Ollama**（本地模型）

配置 LLM：

```bash
kb config
# 或编辑 .env 文件
LLM_API_KEY=your_key
LLM_MODEL=glm-5.1
LLM_API_BASE=https://open.bigmodel.cn/api/paas/v4
```
