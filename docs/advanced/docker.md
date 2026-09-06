# Docker 部署

仓库的 `api` profile 会构建并启动 core、FastAPI 和 React/Nginx 生产前端（ChromaDB 以嵌入式模式运行在 API 进程内，数据持久化于 `kb-data` 卷，无需独立服务容器）。前端镜像使用 Node 22 执行锁文件安装与 Vite production build，再由 Nginx 提供静态资源、SPA fallback 和同源 `/api` 反向代理。

本地开发仍使用 `make web-api` + `make web`，不需要为日常热更新构建容器。

## 启动完整产品

`.env` 是可选文件；没有它时本机 Compose 也能启动和使用只读界面，但涉及 LLM 的编译与回答需要有效的提供商配置。

```bash
# 可选：先创建并编辑配置
cp .env.example .env

# 构建并启动 React、API 与 core 容器
docker compose --profile api up -d --build

# 查看服务
docker compose --profile api ps
docker compose logs -f web api
```

默认地址：

- Web UI：`http://127.0.0.1:3000`（可用 `WEB_PORT` 修改）
- API：`http://127.0.0.1:8000`
- OpenAPI：`http://127.0.0.1:8000/docs`
- liveness：`http://127.0.0.1:8000/health`
- readiness：`http://127.0.0.1:8000/ready`

默认端口只绑定到 `127.0.0.1`。本机 Compose 显式设置 `DOCHRIS_ALLOW_UNAUTHENTICATED=true`，让 Web 反向代理在未配置网关密钥时可用；这项默认值只适合单机开发。

## 健康检查

```bash
curl --fail http://127.0.0.1:8000/health
curl --fail http://127.0.0.1:8000/ready
curl --fail http://127.0.0.1:3000/healthz
```

`/health` 只证明 API 进程能响应；`/ready` 还会检查工作区和运行所需目录是否存在且可写。`/healthz` 证明 Nginx Web 容器可响应。Compose 会先等待 API ready，再启动 Web。

CI 会解析 Compose 配置并实际构建 Web 镜像。若本机 `docker build` 报无法连接 socket，需先启动 Docker daemon；配置可解析不等于镜像已经在该机器上构建运行。

## 环境变量

在仓库根目录的 `.env` 中配置：

```env
OPENAI_API_KEY=your_api_key
MODEL=glm-5.1
OPENAI_API_BASE=https://open.bigmodel.cn/api/paas/v4
WORKSPACE=/app

# 对外部署时设置 API 认证与明确的浏览器来源
DOCHRIS_API_KEY=replace-with-a-strong-secret
DOCHRIS_ALLOW_UNAUTHENTICATED=false
DOCHRIS_CORS_ORIGINS=https://your-ui.example.com
```

启用 `DOCHRIS_API_KEY` 后，在 Web 的“设置 → Dochris 服务访问”中输入同一密钥。这个密钥只保存在当前浏览器的 `localStorage`，与 LLM 提供商 API Key 相互独立。若要对外发布，还需要显式修改 Compose 端口绑定或由受控反向代理暴露 Web，并保持 `DOCHRIS_ALLOW_UNAUTHENTICATED=false`。

## 数据持久化

Compose 使用命名卷保存以下目录：

| 容器路径 | 说明 |
|----------|------|
| `/app/raw` | 原始资料 |
| `/app/manifests` | Manifest 索引 |
| `/app/outputs` | 编译产物 |
| `/app/wiki` | 审核后知识层 |
| `/app/curated` | 人工精选层 |
| `/app/data` | 向量与运行数据 |
| `/app/uploads` | 上传暂存（inbox）与 raw 实体 |
| `/app/cache` | 缓存 |
| `/app/logs` | 日志 |

## 停止

```bash
docker compose --profile api down
```

命名卷不会被上述命令删除。需要删除数据时必须显式使用 `down --volumes`，执行前先备份。
