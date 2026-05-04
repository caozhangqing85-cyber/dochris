# API 参考

dochris 的 Python API 参考文档，从源码 docstring 自动生成。

## 模块概览

| 模块 | 说明 |
|------|------|
| `dochris.core` | 核心模块：LLM 客户端、质量评分、文本分块 |
| `dochris.phases` | 流水线阶段：摄入、编译、查询 |
| `dochris.parsers` | 文件解析器：PDF、Word、代码 |
| `dochris.llm` | LLM 提供商抽象层 |
| `dochris.vector` | 向量存储后端 |
| `dochris.plugin` | 插件系统 |
| `dochris.quality` | 质量评估 |
| `dochris.settings` | 配置管理 |
| `dochris.api` | HTTP API (FastAPI) |
| `dochris.graph` | 知识图谱 |

## 导入方式

```python
# 核心模块
from dochris.core.llm_client import LLMClient
from dochris.core.quality_scorer import QualityScorer
from dochris.core.text_chunker import TextChunker

# 配置
from dochris.settings import get_settings

# 异常
from dochris.exceptions import DochrisError, CompilationError
```

## 快速开始

```python
from dochris.settings import get_settings
from dochris.core.llm_client import LLMClient

# 获取配置
settings = get_settings()

# 使用 LLM 客户端
client = LLMClient(settings)
response = client.compile("你的文本内容")
```

左侧导航中列出了各模块的详细 API 参考。
