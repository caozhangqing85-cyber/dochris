PYTHON ?= $(if $(wildcard .venv/bin/python),.venv/bin/python,python3)
PYTEST ?= $(PYTHON) -m pytest
RUFF ?= $(PYTHON) -m ruff
MYPY ?= $(PYTHON) -m mypy

.PHONY: help install install-standard install-dev install-all install-audio install-docs test test-cov test-fast test-full test-full-no-cov lint format format-check typecheck check clean build docker-build docker-up docker-down docker-all docker-api docker-bench bench bench-report bench-save bench-check docs docs-serve changelog release web web-api graph-stats graph-export

# 默认目标
help: ## 显示帮助信息
	@echo "dochris - 个人知识库编译系统"
	@echo ""
	@echo "可用命令:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'

# 安装相关
install: ## 安装项目（基础依赖）
	$(PYTHON) -m pip install -e .

install-standard: ## 安装推荐运行能力（API、PDF、Chroma/语义检索）
	$(PYTHON) -m pip install -e ".[standard]"

install-dev: ## 安装推荐运行能力和开发依赖
	$(PYTHON) -m pip install -e ".[dev,standard]"

install-all: ## 安装所有运行时依赖（开发工具请使用 install-dev）
	$(PYTHON) -m pip install -e ".[all]"

install-audio: ## 安装音频处理依赖
	$(PYTHON) -m pip install -e ".[audio]"

# 测试相关
test: ## 运行完整测试（使用 pyproject 覆盖率门禁）
	$(PYTEST) tests/ --tb=short -q

test-cov: ## 运行测试并生成覆盖率报告
	$(PYTEST) tests/ --cov=dochris --cov-report=term --cov-report=html --tb=short -q

test-fast: ## Gate 1A 快速测试（仅 unit/API contract，不跑覆盖率门禁）
	$(PYTEST) tests/ --tb=short -q -m "fast" --no-cov

test-full: test ## 运行完整测试别名（保留覆盖率门禁）

test-full-no-cov: ## 运行完整测试但关闭覆盖率门禁（push/nightly 诊断用）
	$(PYTEST) tests/ --tb=short -q --no-cov

# 代码质量
lint: ## 运行 linter 检查
	$(RUFF) check src/ tests/

format: ## 格式化代码
	$(RUFF) format src/ tests/

format-check: ## 检查代码格式
	$(RUFF) format --check src/ tests/

typecheck: ## 运行类型检查（可选依赖例外见 pyproject.toml）
	$(MYPY) src/dochris/

check: lint format-check test-fast ## 快速 PR 检查（lint + format + Gate 1A）

# 清理
clean: ## 清理临时文件和构建产物
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
	rm -rf htmlcov/ .coverage dist/ build/ *.egg-info

# 构建
build: ## 构建发布包
	$(PYTHON) -m build

# Docker 相关
docker-build: ## 构建 Docker 镜像（默认 core）
	docker build -t dochris:latest .

docker-all: ## 构建并启动所有服务（app + chromadb）
	docker compose --profile api up -d --build

docker-api: ## 启动 API 服务（app + api + chromadb）
	docker compose --profile api up -d --build

docker-bench: ## 在 Docker 中运行基准测试
	docker build --build-arg BUILD_TARGET=all -t dochris:bench .
	docker run --rm dochris:bench pytest benchmark/ --benchmark-only -v

docker-up: ## 启动 Docker 容器
	docker compose up -d

docker-down: ## 停止 Docker 容器
	docker compose --profile api down

# 基准测试
bench: ## 运行所有基准测试
	$(PYTEST) benchmark/ --benchmark-only -v

bench-report: ## 运行基准测试并保存报告
	@mkdir -p reports
	$(PYTEST) benchmark/ --benchmark-only \
		--benchmark-json=reports/benchmark-$$(date +%Y%m%d-%H%M%S).json \
		-v

# DEBT-06：p50/p95 回归对比（先 bench-save 存基线，再 bench-check 守门）
bench-save: ## 保存基准基线（reports/benchmark-baseline.json）
	@mkdir -p reports
	$(PYTEST) benchmark/ --benchmark-only -q \
		--benchmark-json=reports/benchmark-baseline.json

bench-check: ## 与基线对比，均值劣化超过 25% 视为回归（CI 可用）
	@[ -f reports/benchmark-baseline.json ] || { echo "缺少基线文件，请先 make bench-save"; exit 1; }
	$(PYTEST) benchmark/ --benchmark-only -q \
		--benchmark-json=reports/benchmark-current.json \
		--benchmark-compare=reports/benchmark-baseline.json \
		--benchmark-compare-fail=mean:25%

# 文档
docs: ## 构建 MkDocs 文档（strict 模式，与 CI docs.yml 一致）
	$(PYTHON) -m mkdocs build --strict

docs-serve: ## 本地预览文档
	$(PYTHON) -m mkdocs serve

# 发布相关
changelog: ## 生成 CHANGELOG
	git-cliff -o CHANGELOG.md

release: ## 版本自检与发布提示（正式发布流程见 docs/RELEASE.md）
	@$(PYTHON) -c 'import dochris; print("当前版本:", dochris.__version__)'
	@echo "发布步骤（docs/RELEASE.md）："
	@echo "  1. 更新 pyproject.toml / src/dochris/__init__.py 的版本号与 CHANGELOG.md"
	@echo "  2. git commit && git tag vX.Y.Z && git push origin vX.Y.Z"
	@echo "  3. release.yml 自动执行完整门禁 → 构建 → smoke → PyPI（Trusted Publishing）"


# Web UI
web: ## 启动 React Web UI（需要另行运行 make web-api）
	cd frontend && npm run dev

web-api: ## 在 127.0.0.1:8000 启动 React 开发环境所需的 FastAPI API
	PYTHONPATH=src $(PYTHON) -m dochris.cli.main serve --host 127.0.0.1 --port 8000

# 知识图谱
graph-stats: ## 显示知识图谱统计
	PYTHONPATH=src $(PYTHON) -m dochris.cli.main graph stats

graph-export: ## 导出知识图谱为 JSON
	PYTHONPATH=src $(PYTHON) -m dochris.cli.main graph export --output graph.json
