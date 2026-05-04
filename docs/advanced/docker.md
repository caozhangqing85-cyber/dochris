# Docker 部署

使用 Docker 快速部署 dochris 服务。

## Dockerfile

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# 安装依赖
COPY pyproject.toml .
RUN pip install --no-cache-dir ".[api]"

# 复制源码
COPY src/ src/

# 暴露端口
EXPOSE 8000

# 启动 API 服务
CMD ["kb", "serve", "--host", "0.0.0.0", "--port", "8000"]
```

## Docker Compose

```yaml
version: "3.8"

services:
  dochris-api:
    build: .
    ports:
      - "8000:8000"
    volumes:
      - ./workspace:/root/.knowledge-base
      - ./materials:/root/materials:ro
    environment:
      - OPENAI_API_KEY=${OPENAI_API_KEY}
      - MODEL=glm-5.1
      - OPENAI_API_BASE=https://open.bigmodel.cn/api/coding/paas/v4
    restart: unless-stopped

  dochris-web:
    build: .
    command: kb serve --web --host 0.0.0.0 --web-port 7860
    ports:
      - "7860:7860"
    volumes:
      - ./workspace:/root/.knowledge-base
    environment:
      - OPENAI_API_KEY=${OPENAI_API_KEY}
    restart: unless-stopped
```

## 使用方法

```bash
# 构建镜像
docker compose build

# 启动服务
docker compose up -d

# 查看日志
docker compose logs -f dochris-api

# 停止服务
docker compose down
```

## 环境变量

在 `.env` 文件或 `environment` 中配置：

```env
OPENAI_API_KEY=your_api_key
MODEL=glm-5.1
OPENAI_API_BASE=https://open.bigmodel.cn/api/coding/paas/v4
WORKSPACE=/root/.knowledge-base
SOURCE_PATH=/root/materials
```

## 数据持久化

关键目录需要挂载为 volume：

| 容器路径 | 说明 |
|----------|------|
| `/root/.knowledge-base` | 工作区（manifests、outputs、wiki） |
| `/root/materials` | 源文件（只读） |

## 健康检查

```bash
curl http://localhost:8000/api/v1/status
```
