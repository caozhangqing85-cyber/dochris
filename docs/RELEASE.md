# 发布就绪（Release Readiness）

本页是唯一的发布就绪参考（DOC-03）。发布相关的一切问题以本页为准。

## 支持矩阵（Support Matrix）

| 维度 | 支持范围 |
|---|---|
| Python | 3.11、3.12（CI 双版本矩阵；3.13 可运行但 FAISS/SWIG 有弃用警告） |
| 操作系统 | Linux x86_64（CI/镜像）、macOS arm64（CI 安装 smoke） |
| Docker | 任意支持 Compose v2 的运行时；镜像基于 python:3.11-slim 与 node:22 |
| 浏览器 | 现代常青浏览器（React 18 + Vite 构建） |
| 发布渠道 | PyPI（Trusted Publishing）、GitHub Release（wheel/sdist/checksums/SBOM） |

## 发布门禁（必须全部通过）

任何 tag 发布之前，以下门禁必须全部绿色：

1. `make check`（ruff lint + format + fast tests）
2. `make typecheck`（mypy）
3. Integration suite：write-path e2e、storage migration、API 契约、真实传输层
4. 前端：`npm test`、`npm run lint`、`npm run build`、e2e smoke
5. Docker：API 镜像 build + `/health` smoke、Web 镜像 build、Compose 栈启动健康检查
6. `make docs`（`mkdocs build --strict`）

以上全部已固化在 [release workflow](https://github.com/caozhangqing85-cyber/dochris/blob/main/.github/workflows/release.yml)
的 `release-gate` / `build` / `install-smoke` / `github-release` / `publish` 链条中：
**tag 推送无法绕过门禁直接发布**，且 PyPI 只发布通过门禁的同一份 artifact。

## 发布流程（Release Checklist）

1. 确认 `main` 分支全部 CI 门禁绿色（含 nightly full coverage）。
2. 确认 `pyproject.toml` 的 `version` 与 `src/dochris/__init__.py` 的 `__version__` 一致（release workflow 会校验 tag 匹配）。
3. 更新 `CHANGELOG.md`（基于 Keep a Changelog）。
4. 提交版本号变更，创建 annotated tag 并推送：
   ```bash
   git tag -a vX.Y.Z -m "Release vX.Y.Z"
   git push origin vX.Y.Z
   ```
5. release workflow 自动执行：gate → build → install smoke → GitHub Release（附 checksums/SBOM）→ PyPI 发布。
6. 发布完成后：
   - 验证 `pip install dochris==X.Y.Z` 干净环境安装 + `kb --help` smoke；
   - 验证 Docker 镜像 `docker pull ghcr.io/caozhangqing85-cyber/dochris:X.Y.Z`（如适用）；
   - 在 GitHub Release 页确认 checksums.sha256 与 sbom.json 已附上。

### PyPI Trusted Publishing 前置配置（一次性）

PyPI 项目设置中配置 Trusted Publisher：

- owner：`caozhangqing85-cyber`（以实际仓库为准）
- repository：`dochris`
- workflow：`release.yml`
- environment：`pypi`

配置完成后无需任何长期 API Token（REL-07）。

## 升级（Upgrade）

本地单机安装：

```bash
pip install --upgrade "dochris[standard]"
kb doctor   # 环境体检
```

Docker/Compose 部署：

```bash
git pull
docker compose --profile api up -d --build   # 命名卷数据保留
```

注意事项：

- 升级前建议备份工作区（`manifests/`、`outputs/`、`wiki/`、`curated/`、`data/`）。
- 存储格式变更由 `kb storage` 迁移子命令处理：先 `--dry-run` 审计，确认备份后 `--apply`。
- 编译任务历史（`data/compile-jobs.json`）向后兼容；服务重启时进行中的任务会被标记为 `interrupted`（可重试）。

## 回滚（Rollback）

```bash
pip install "dochris==X.Y.(Z-1)"      # PyPI 安装回滚
docker compose --profile api down      # 或回退到上一个镜像 tag
docker compose --profile api up -d --build
```

- 命名卷中的数据不会被 `docker compose down` 删除；仅在确认无用后使用 `down --volumes`（执行前必须备份）。
- 存储迁移提供了 backup + rollback 能力；迁移真实数据前必须在隔离副本上完整验证 dry-run → apply → rollback 循环。

## 发布红线

在以下门禁未固化前，不应执行正式 tag、PyPI 发布或真实数据迁移：

- 全量测试与 fresh coverage 绿色；
- 干净 clone / 干净 venv 从最终 wheel 安装并完成查询 smoke；
- Compose API/Web 可启动、访问、停止、恢复；
- Tag 无法绕过测试直接发布（当前 release workflow 已满足）。

此外：以当前认证模型（单机 `DOCHRIS_ALLOW_UNAUTHENTICATED=true`）**不应开放公网多用户访问**。

## 失败恢复、重试与回滚契约（SEC-06）

| 失败场景 | 系统行为 | 恢复手段 |
|---|---|---|
| 后台编译中进程崩溃 | 任务在重启后按 lease 状态标记为 `interrupted`（SQLite 仓库要求 lease 过期；他人有效 lease 不抢占），错误摘要脱敏入库 | `POST /compile/jobs/{id}/retry` 以原参数重试；`GET /compile/jobs/{id}/failures` 下载失败明细 |
| 单文档编译失败 | 其余文档继续；任务终态 `completed_with_errors`，`failed_files`/`failure_details` 可查 | 修复诱因后 retry（只重编 `status=ingested` 的文档）；单文档可用 recompile |
| 编译超时 | 任务级预算（`DOCHRIS_COMPILE_TIMEOUT_SECONDS`）到期标记 `failed`，错误注明预算值 | 调大预算后 retry |
| 客户端重复提交编译 | `Idempotency-Key` 命中已有任务时直接返回原任务，不重复执行 | — |
| 向量检索不可用 | `mode=vector` 返回类型化错误；`combined` 降级为关键词检索并发 warning | 修复向量库后自动恢复；期间查询不中断 |
| 存储迁移出错 | 迁移前强制备份；支持 rollback 恢复 | `kb storage` 的 dry-run → apply → rollback 流程 |
| 晋升/重置误操作 | 两者均提供 preview（`/promote/{id}/preview`、`reset-failed?preview=true`）先行确认 | 晋升产物可用文件备份恢复；建议操作前备份工作区 |

约定：

1. 一切"不可直接撤销"的写操作必须先提供 preview/diff（SEC-05）。
2. 任务历史（`data/compile-jobs.db`）跨重启保留，终态任务受 `max_history` 约束滚动清理，活动任务永不清除。
3. 错误对外的文本一律经过脱敏（无 API key / Bearer / 本机路径），见 `core/error_sanitizer.py`。

## RAG 质量门槛（RAG-12）

在默认开启 Reranker 或语义分块等"质量增强"能力之前，必须用真实语料基线证明收益。
评测链路：`eval/`（`RAGEvaluator` + `eval/rag_golden.jsonl` golden set），每次报告自带
模型/语料/commit 元数据，可直接对比。

| 指标 | 建议门槛（相对基线） | 说明 |
|---|---|---|
| recall@5 | ≥ 基线 且 绝对值 ≥ 0.7 | 期望来源命中率；低于 0.7 优先修检索而非加增强 |
| ndcg@5 | ≥ 基线 + 0.02 | 排序质量必须为正收益 |
| faithfulness | ≥ 0.8 | 回答句子的证据支持率（启发式指标） |
| citation_correctness | ≥ 0.9 | [Sn] 引用可映射到证据的比例 |
| retrieval P95 延迟 | ≤ 1.5 s | 本地文件 + 向量检索阶段 |
| 首 token 延迟 | ≤ 3 s（Provider 视情况） | 由 `QueryResponse.timings` / SSE `done.timings` 观测 |
| 成本 | 记录但不设硬门槛 | 通过 observability cost 指标跟踪 |

对比协议（RAG-07/10/11）：同一 golden set + 同一语料版本 + 同一模型，
对比 无 reranker / cross-encoder / BGE reranker，以及 structure / recursive /
semantic 分块；每轮保存 JSON 报告（含 commit SHA）后再决定是否切换默认配置。

