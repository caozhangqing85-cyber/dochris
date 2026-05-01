# 多 LLM 支持

dochris 支持多种 LLM 后端，适配不同使用场景。

## 支持的提供商

### 智谱 GLM（默认）

```bash
LLM_API_KEY=your_key
LLM_MODEL=glm-5.1
LLM_API_BASE=https://open.bigmodel.cn/api/paas/v4
```

### OpenAI 兼容 API

```bash
LLM_API_KEY=sk-xxx
LLM_MODEL=gpt-4o
LLM_API_BASE=https://api.openai.com/v1
```

支持所有 OpenAI 兼容接口：DeepSeek、Moonshot、通义千问等。

### Ollama（本地模型）

```bash
LLM_MODEL=llama3
LLM_API_BASE=http://localhost:11434
# Ollama 不需要 API Key
```

## 配置方式

### 交互式

```bash
kb init  # 初始化时配置
kb config  # 查看当前配置
```

### 环境变量

编辑 `.env` 文件：

```env
LLM_API_KEY=your_api_key
LLM_MODEL=glm-5.1
LLM_API_BASE=https://open.bigmodel.cn/api/paas/v4
```

## LLM 抽象层

所有 LLM 调用通过统一抽象层：

```
LLMProvider (Protocol)
├── OpenAICompatProvider  ← OpenAI 兼容 API
└── OllamaProvider        ← Ollama 本地模型
```

新增提供商只需实现 `LLMProvider` 协议。
