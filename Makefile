.PHONY: help install install-dev install-all install-audio test test-cov test-fast lint format format-check typecheck check clean build docker-build docker-up docker-down docs

# 默认目标
help: ## 显示帮助信息
	@echo "dochris - 个人知识库编译系统"
	@echo ""
	@echo "可用命令:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'

# 安装相关
install: ## 安装项目（基础依赖）
	pip install -e .

install-dev: ## 安装开发依赖
	pip install -e ".[dev]"

install-all: ## 安装所有依赖（包括音频、PDF、OCR）
	pip install -e ".[all]"

install-audio: ## 安装音频处理依赖
	pip install -e ".[audio]"

# 测试相关
test: ## 运行测试
	pytest tests/ --tb=short -q

test-cov: ## 运行测试并生成覆盖率报告
	pytest tests/ --cov=dochris --cov-report=term --cov-report=html --tb=short -q

test-fast: ## 运行快速测试（跳过慢速测试）
	pytest tests/ --tb=short -q -m "not slow"

# 代码质量
lint: ## 运行 linter 检查
	ruff check src/ tests/

format: ## 格式化代码
	ruff format src/ tests/

format-check: ## 检查代码格式
	ruff format --check src/ tests/

typecheck: ## 运行类型检查（可选）
	mypy src/

check: lint format-check test ## 完整检查（lint + format + test）

# 清理
clean: ## 清理临时文件和构建产物
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
	rm -rf htmlcov/ .coverage dist/ build/ *.egg-info

# 构建
build: ## 构建发布包
	python -m build

# Docker 相关（预留）
docker-build: ## 构建 Docker 镜像
	docker build -t dochris:latest .

docker-up: ## 启动 Docker 容器
	docker compose up -d

docker-down: ## 停止 Docker 容器
	docker compose down

# 文档
docs: ## 生成 API 文档
	pdoc dochris -o docs/html
