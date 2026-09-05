# 安装

## 系统要求

- Python 3.11+
- pip
- Node.js 22.13+（仅从源码运行 React Web UI；不支持 Node 23）

## 基础安装

```bash
pip install dochris
```

基础安装提供 CLI、纯文本解析和关键词检索，不会拉取 Torch、ONNXRuntime、ChromaDB 或 Kubernetes 等重依赖。

## 推荐安装

```bash
pip install "dochris[standard]"
```

推荐安装包含 HTTP API、Office/PDF 文档解析以及 ChromaDB/语义检索，适合大多数完整使用场景。

## 按能力安装

| Extra | 能力 |
|---|---|
| `documents` | Word、PowerPoint、Excel 等 Office 文档解析 |
| `vector` | ChromaDB 与 sentence-transformers 向量/语义检索 |
| `api` | FastAPI、SSE、指标与上传接口 |
| `pdf` | PyMuPDF、pdfplumber 与 PDF 解析 |
| `audio` | faster-whisper 音频转录 |
| `ocr` | Tesseract/Pillow OCR |
| `ollama` | Ollama 本地模型客户端 |
| `leann` | LEANN 向量后端 |

例如：

```bash
pip install "dochris[documents,ollama]"
```

### 音频转录（需要 GPU）

```bash
pip install dochris[audio]
```

安装 faster-whisper 用于本地音频转录。

### 开发工具

```bash
pip install "dochris[dev,standard]"
```

包含推荐运行能力以及 pytest、ruff、mypy、pre-commit、pytest-benchmark。

### 全部功能

```bash
pip install dochris[all]
```

安装全部运行时能力，不包含开发工具。

### HTTP API

```bash
pip install dochris[api]
```

包含 FastAPI + uvicorn，提供 REST API 接口。

## 验证安装

```bash
kb --help
kb version
```

## 从源码安装

```bash
git clone https://github.com/caozhangqing85-cyber/dochris.git
cd dochris
pip install -e ".[dev,standard]"
```
