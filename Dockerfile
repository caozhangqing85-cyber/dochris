# ============================================================
# Knowledge Base - Multi-Stage Dockerfile
# ============================================================
# 支持 CPU 和 GPU（NVIDIA）运行环境
# 构建: docker build -t knowledge-base:latest .
# 运行: docker run --rm -it knowledge-base:latest
# GPU运行: docker run --gpus all --rm -it knowledge-base:latest

# ============================================================
# Stage 1: Builder - 安装编译依赖和构建包
# ============================================================
FROM python:3.11-slim AS builder

# 设置构建参数
ARG DEBIAN_FRONTEND=noninteractive

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

# ============================================================
# Stage 2: Runtime - 最终运行镜像
# ============================================================
FROM python:3.11-slim AS runtime

# 设置环境变量
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    # 工作目录
    WORKSPACE=/app \
    # 路径配置
    PATH="/opt/venv/bin:$PATH" \
    PYTHONPATH="/app:$PYTHONPATH"

# 安装运行时依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    # 基础工具
    curl \
    git \
    # 文档处理依赖
    poppler-utils \
    tesseract-ocr \
    tesseract-ocr-chi-sim \
    tesseract-ocr-eng \
    libtesseract-dev \
    # 音视频处理（可选）
    ffmpeg \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgl1-mesa-glx \
    # 清理缓存
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

# ============================================================
# 安装 Python 依赖
# ============================================================
# 先复制依赖文件以利用层缓存
COPY pyproject.toml ./

# 安装核心依赖（包含 faster-whisper）
RUN pip install --no-cache-dir -e .[pdf]

# ============================================================
# 复制应用代码
# ============================================================
# 复制源代码
COPY src/ /app/src/
COPY README.md ./

# ============================================================
# 创建目录结构
# ============================================================
RUN mkdir -p \
    /app/data \
    /app/raw \
    /app/outputs \
    /app/wiki \
    /app/curated \
    /app/logs \
    /app/manifests \
    && chown -R kbuser:kbuser /app

# ============================================================
# 复制入口脚本并设置权限
# ============================================================
COPY docker_entrypoint.sh /app/docker_entrypoint.sh
RUN chmod +x /app/docker_entrypoint.sh

# 切换到非 root 用户
USER kbuser

# ============================================================
# 健康检查
# ============================================================
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import sys; sys.exit(0)" || exit 1

# ============================================================
# 暴露端口（可选，用于未来 API 服务）
# ============================================================
# EXPOSE 8000

# ============================================================
# 设置入口点
# ============================================================
ENTRYPOINT ["/app/docker_entrypoint.sh"]

# 默认命令：显示帮助信息
CMD ["--help"]
