# 安装

## 系统要求

- Python 3.11+
- pip

## 基础安装

```bash
pip install dochris
```

## 可选依赖

### 音频转录（需要 GPU）

```bash
pip install dochris[audio]
```

安装 faster-whisper 用于本地音频转录。

### 开发工具

```bash
pip install dochris[dev]
```

包含 pytest、ruff、mypy、pre-commit、pytest-benchmark。

### 全部功能

```bash
pip install dochris[all]
```

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
pip install -e ".[dev]"
```
