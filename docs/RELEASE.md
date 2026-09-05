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
