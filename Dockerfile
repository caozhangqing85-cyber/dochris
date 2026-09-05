# ============================================================
# Knowledge Base - Multi-Stage Dockerfile
# ============================================================
# 支持 CPU 和 GPU（NVIDIA）运行环境
# 构建: docker build -t dochris:latest .
# API:  docker build --build-arg BUILD_TARGET=api -t dochris:api .
# 全部: docker build --build-arg BUILD_TARGET=all -t dochris:full .
# 运行: docker run --rm -it dochris:latest
# GPU:  docker run --gpus all --rm -it dochris:latest

# ============================================================
# 构建参数
# ============================================================
ARG PYTHON_VERSION=3.11
ARG BUILD_TARGET=core

# ============================================================
# Stage 1: Builder - 安装编译依赖和构建包
# ============================================================
FROM python:${PYTHON_VERSION}-slim AS builder

ARG DEBIAN_FRONTEND=noninteractive

# 安装系统依赖（用于编译 Python 包）
RUN apt-get -o Acquire::Retries=3 update \
    && apt-get -o Acquire::Retries=3 install -y --no-install-recommends \
    build-essential \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 创建虚拟环境
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
ARG PIP_NETWORK_OPTIONS="--retries 10 --timeout 60"
ARG PIP_LARGE_DOWNLOAD_OPTIONS="--retries 10 --resume-retries 10 --timeout 60"

# builder 复用下载缓存，并为大体积 CPU/向量依赖提供断点续传与重试。
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install $PIP_NETWORK_OPTIONS --upgrade pip setuptools wheel

# 只有需要向量/语义能力的镜像才安装 Torch；core/pdf 保持轻量。
ARG BUILD_TARGET=core
ARG TORCH_VERSION=2.13.0
RUN --mount=type=cache,target=/root/.cache/pip \
    case "$BUILD_TARGET" in \
      api|all) pip install $PIP_LARGE_DOWNLOAD_OPTIONS "torch==${TORCH_VERSION}+cpu" \
        --index-url https://download.pytorch.org/whl/cpu ;; \
      *) echo "Skipping Torch for BUILD_TARGET=$BUILD_TARGET" ;; \
    esac

# 复制构建元数据与源码；setuptools 构建包时必须能看到 src/
COPY pyproject.toml README.md ./
COPY src/ ./src/

# 根据 BUILD_TARGET 选择安装的 extras
RUN --mount=type=cache,target=/root/.cache/pip <<EOF
  case "$BUILD_TARGET" in
    core)  pip install $PIP_LARGE_DOWNLOAD_OPTIONS . ;;
    pdf)   pip install $PIP_LARGE_DOWNLOAD_OPTIONS ".[pdf]" ;;
    api)   pip install $PIP_LARGE_DOWNLOAD_OPTIONS ".[standard]" ;;
    all)   pip install $PIP_LARGE_DOWNLOAD_OPTIONS ".[all]" ;;
    *)     pip install $PIP_LARGE_DOWNLOAD_OPTIONS . ;;
  esac
EOF

# ============================================================
# Stage 2: Runtime - 最终运行镜像
# ============================================================
FROM python:${PYTHON_VERSION}-slim AS runtime

# 设置环境变量
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    WORKSPACE=/app \
    PATH="/opt/venv/bin:$PATH" \
    PYTHONPATH="/app/src"

ARG BUILD_TARGET=core

# 只有 all 镜像包含 OCR/音视频系统工具；core/pdf/api 保持最小运行时。
RUN set -eu; \
    runtime_packages=""; \
    case "$BUILD_TARGET" in \
      all) runtime_packages="poppler-utils tesseract-ocr tesseract-ocr-chi-sim tesseract-ocr-eng ffmpeg" ;; \
    esac; \
    if [ -n "$runtime_packages" ]; then \
      apt-get -o Acquire::Retries=3 update; \
      apt-get -o Acquire::Retries=3 install -y --no-install-recommends $runtime_packages; \
      apt-get clean; \
      rm -rf /var/lib/apt/lists/*; \
    fi

# 元数据
LABEL maintainer="caozhangqing85-cyber" \
      description="个人知识库编译系统 — 四阶段流水线" \
      version="1.4.0" \
      build_target="${BUILD_TARGET}"

# 从 builder 复制虚拟环境
COPY --from=builder /opt/venv /opt/venv

# 创建非 root 用户
RUN groupadd -r kbuser && useradd -r -g kbuser -u 1000 kbuser \
    && mkdir -p /app \
    && chown -R kbuser:kbuser /app

# 设置工作目录
WORKDIR /app

# 先复制版本信息（层缓存优化）
COPY pyproject.toml README.md ./
COPY src/dochris/__init__.py ./src/dochris/__init__.py

# 复制源代码
COPY src/ /app/src/

# 创建目录结构
RUN mkdir -p \
    /app/data \
    /app/raw \
    /app/outputs \
    /app/wiki \
    /app/curated \
    /app/logs \
    /app/manifests \
    /app/cache \
    && chown -R kbuser:kbuser /app

# 复制入口脚本并设置权限
COPY docker_entrypoint.sh /app/docker_entrypoint.sh
RUN chmod +x /app/docker_entrypoint.sh

# 切换到非 root 用户
USER kbuser

# 暴露端口（API 服务）
EXPOSE 8000

# 设置入口点
ENTRYPOINT ["/app/docker_entrypoint.sh"]

# 默认命令：显示帮助信息；具体服务在 Compose 中提供专用命令与探针
CMD ["kb", "--help"]
