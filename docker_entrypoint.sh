#!/bin/bash
# ============================================================
# Dochris Docker 入口脚本
# ============================================================
# 默认行为：显示帮助信息
# 可通过 CMD 或 docker-compose command 覆盖

set -e

# ============================================================
# 1. 确保 workspace 目录结构存在
# ============================================================
WORKSPACE="${WORKSPACE:-/app}"

for dir in data raw outputs wiki curated logs manifests cache; do
    mkdir -p "${WORKSPACE}/${dir}"
done

# 确保 manifests/sources 子目录存在
mkdir -p "${WORKSPACE}/manifests/sources"

# ============================================================
# 2. 首次运行检测：如果没有 manifest 索引则初始化
# ============================================================
if [ ! -f "${WORKSPACE}/manifests/source_index.csv" ]; then
    echo "[entrypoint] 首次运行检测 — 初始化 workspace..."
    # 不执行 kb init 以避免依赖交互式输入
    # 只确保目录结构存在即可
fi

# ============================================================
# 3. 如果没有传入参数，显示帮助
# ============================================================
if [ $# -eq 0 ]; then
    exec kb --help
else
    # 执行传入的命令
    exec "$@"
fi
