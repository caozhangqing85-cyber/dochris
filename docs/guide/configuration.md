# 配置详解

dochris 的配置按以下优先级加载：

**`.env` 文件 > 环境变量 > 默认值**

## 查看配置

```bash
kb config
```

## 核心配置项

### LLM 配置

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `OPENAI_API_KEY` | 必填 | LLM API 密钥 |
| `OPENAI_API_BASE` | `https://open.bigmodel.cn/api/coding/paas/v4` | API 地址 |
| `MODEL` | `glm-5.1` | 编译使用的模型 |

### 工作区配置

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `WORKSPACE` | `~/.knowledge-base` | 工作区路径 |
| `SOURCE_PATH` | `~/materials` | 源文件目录 |

### 编译配置

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `MIN_QUALITY_SCORE` | `85` | 质量晋升门槛 |
| `MAX_CONTENT_CHARS` | `20000` | 单文件最大字符数 |
| `MAX_CONCURRENCY` | `1` | 并发编译数 |

### 向量存储配置

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `VECTOR_STORE` | `chromadb` | 向量存储后端（`chromadb` / `faiss`） |
| `EMBEDDING_MODEL` | `BAAI/bge-small-zh-v1.5` | 嵌入模型 |

### 日志配置

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `LOG_FORMAT` | `text` | 日志格式（`text` / `json`） |
| `LOG_LEVEL` | `INFO` | 日志级别 |

## .env 文件示例

```env
# LLM 配置
OPENAI_API_KEY=your_api_key_here
OPENAI_API_BASE=https://open.bigmodel.cn/api/coding/paas/v4
MODEL=glm-5.1

# 工作区
WORKSPACE=~/.knowledge-base
SOURCE_PATH=~/materials

# 编译
MIN_QUALITY_SCORE=85
MAX_CONTENT_CHARS=20000
MAX_CONCURRENCY=3

# 向量存储
VECTOR_STORE=chromadb
EMBEDDING_MODEL=BAAI/bge-small-zh-v1.5

# 日志
LOG_FORMAT=text
LOG_LEVEL=INFO
```

## 配置文件位置

dochris 按以下顺序查找配置：

1. 当前目录 `.env`
2. 工作区目录 `.env`
3. 环境变量
4. 内置默认值

## 使用 OpenClaw 配置

如果 `OPENAI_API_KEY` 未设置，dochris 会尝试从 OpenClaw 配置文件获取：

```
~/.openclaw/openclaw.json
```

运行 `kb doctor` 检查配置状态。
