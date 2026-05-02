# ============================================================
# Knowledge Base - Multi-Stage Dockerfile
# ============================================================
# 支持 CPU 和 GPU（NVIDIA）运行环境
# 构建: docker build -t dochris:latest .
# API:  docker build --build-arg BUILD_TARGET=api -t dochris:api .
# Web:  docker build --build-arg BUILD_TARGET=web -t dochris:web .
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
ARG BUILD_TARGET=core

# 安装系统依赖（用于编译 Python 包）
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 创建虚拟环境
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# 升级 pip 和安装构建工具
RUN pip install --no-cache-dir --upgrade pip setuptools wheel

# 先复制依赖文件以利用层缓存
COPY pyproject.toml README.md ./

# 根据 BUILD_TARGET 选择安装的 extras
RUN <<EOF
  case "$BUILD_TARGET" in
    core)  pip install --no-cache-dir -e . ;;
    pdf)   pip install --no-cache-dir -e ".[pdf]" ;;
    api)   pip install --no-cache-dir -e ".[api]" ;;
    web)   pip install --no-cache-dir -e ".[web]" ;;
    all)   pip install --no-cache-dir -e ".[all]" ;;
    *)     pip install --no-cache-dir -e . ;;
  esac
EOF

# ============================================================
# Stage 2: Runtime - 最终运行镜像
# ============================================================
FROM python:${PYTHON_VERSION}-slim AS runtime

ARG BUILD_TARGET=core

# 元数据
LABEL maintainer="caozhangqing85-cyber" \
      description="个人知识库编译系统 — 四阶段流水线" \
      version="1.2.0" \
      build_target="${BUILD_TARGET}"

# 设置环境变量
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    WORKSPACE=/app \
    PATH="/opt/venv/bin:$PATH" \
    PYTHONPATH="/app:$PYTHONPATH"

# 安装运行时依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    git \
    poppler-utils \
    tesseract-ocr \
    tesseract-ocr-chi-sim \
    tesseract-ocr-eng \
    libtesseract-dev \
    ffmpeg \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgl1-mesa-glx \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

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

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import sys; sys.exit(0)" || exit 1

# 暴露端口（API 服务 + Web UI）
EXPOSE 8000 7860

# 设置入口点
ENTRYPOINT ["/app/docker_entrypoint.sh"]

# 默认命令：显示帮助信息
CMD ["--help"]
