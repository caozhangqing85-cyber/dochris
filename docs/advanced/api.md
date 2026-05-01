# HTTP API

dochris 提供 REST API 接口，支持程序化访问。

## 安装

```bash
pip install dochris[api]
```

## 启动服务器

```bash
kb serve                  # 默认 localhost:8000
kb serve --port 9000      # 自定义端口
kb serve --host 0.0.0.0   # 允许外部访问
kb serve --reload         # 开发模式（热重载）
```

## API 端点

### 查询知识库

```
GET /api/v1/query?q=关键词&mode=concept&limit=5
```

### 编译文档

```
POST /api/v1/compile
{
  "limit": 10,
  "concurrency": 4,
  "quality_threshold": 85
}
```

### 系统状态

```
GET /api/v1/status
```

### 晋升操作

```
POST /api/v1/promote/{source_id}
{
  "target": "wiki"
}
```

## 响应格式

所有响应使用 JSON：

```json
{
  "success": true,
  "data": { ... },
  "meta": {
    "total": 10,
    "limit": 5
  }
}
```

## OpenAPI 文档

启动服务器后访问：

- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`
```
