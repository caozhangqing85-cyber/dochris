# 5 分钟快速上手

> 从零开始，5 分钟内拥有一个可查询的 AI 知识库。

## 前置要求

| 项目 | 要求 |
|------|------|
| Python | 3.11 或更高版本 |
| 内存 | 4GB+（推荐 8GB） |
| API Key | 一个 LLM API Key（推荐智谱 GLM，也支持 OpenRouter 免费模型） |

## 第一步：安装（1 分钟）

### 使用 pip 安装

```bash
# 克隆项目
git clone https://github.com/caozhangqing85-cyber/dochris.git
cd dochris

# 创建虚拟环境
python3.11 -m venv venv
source venv/bin/activate    # Windows: venv\Scripts\activate

# 安装核心依赖
pip install -e .

# 安装全部可选依赖（Web UI、API、PDF、音频、OCR）
pip install -e ".[all]"
```

预期输出：

```
Successfully installed dochris-1.4.0
✅ 安装完成
```

### 使用 PyPI 安装

```bash
pip install dochris
```

> 💡 **提示**：`pip install -e ".[all]"` 会安装所有可选功能（Gradio Web UI、FastAPI、PDF 解析、音频转录等），推荐首次使用时安装。

## 第二步：配置（1 分钟）

### 方式 A：交互式初始化（推荐）

```bash
kb init
```

向导会引导你完成所有配置，包括 API Key 输入和目录创建。

预期输出：

```
============================================================
📚 Dochris 知识库初始化向导
============================================================

✅ Python 版本: 3.11.9

📁 创建工作区目录结构...
✅ 已创建 18 个目录

🔑 配置 API Key...
请选择 LLM 提供商:
  1. 智谱 AI (推荐)
  2. OpenAI
  3. OpenRouter (免费模型)
  4. 其他 OpenAI 兼容 API
请输入选项 [1]: 1
请输入 API Key: sk-xxxxxxxx

✅ 配置已保存到 ~/.knowledge-base/.env

🚀 初始化完成！接下来：
   1. 将文件放入 ~/.knowledge-base/raw/ 对应子目录
   2. 运行 kb ingest 扫描文件
   3. 运行 kb compile 编译知识库
   4. 运行 kb query "关键词" 查询
```

### 方式 B：环境变量

```bash
# 设置 API Key
export OPENAI_API_KEY="your_api_key_here"

# 智谱 AI
export OPENAI_API_BASE="https://open.bigmodel.cn/api/paas/v4"
export MODEL="glm-5.1"

# 或 OpenRouter（免费模型）
# export OPENAI_API_BASE="https://openrouter.ai/api/v1"
# export MODEL="qwen/qwen-2.5-72b-instruct:free"
```

### 方式 C：.env 文件

```bash
# 创建配置文件
cp .env.example ~/.knowledge-base/.env

# 编辑配置
nano ~/.knowledge-base/.env
```

填入以下必要配置：

```bash
# 必填：LLM API Key
OPENAI_API_KEY=your_api_key_here
OPENAI_API_BASE=https://open.bigmodel.cn/api/paas/v4
MODEL=glm-5.1

# 可选：工作区路径（默认 ~/.knowledge-base）
WORKSPACE=~/.knowledge-base
```

## 第三步：放入你的文件（30 秒）

### 支持的文件格式

| 类型 | 格式 | 存放目录 |
|------|------|---------|
| PDF 文档 | `.pdf` | `raw/pdfs/` |
| 文章/文本 | `.md`, `.txt`, `.html` | `raw/articles/` |
| 音频 | `.mp3`, `.wav`, `.m4a`, `.flac` | `raw/audio/` |
| 视频 | `.mp4`, `.mkv`, `.avi` | `raw/videos/` |
| 电子书 | `.epub`, `.mobi` | `raw/ebooks/` |
| 其他 | `.docx`, `.pptx`, `.csv` 等 | `raw/other/` |

### 放入文件

```bash
# 直接复制文件
cp ~/Downloads/论文合集/*.pdf ~/.knowledge-base/raw/pdfs/
cp ~/Music/播客/*.mp3 ~/.knowledge-base/raw/audio/

# 或创建符号链接（不占用额外空间）
ln -s ~/Documents/我的笔记.md ~/.knowledge-base/raw/articles/

# 或指定外部源目录
echo "SOURCE_PATH=~/Documents/我的资料" >> ~/.knowledge-base/.env
```

### 从 Obsidian 同步

如果你的笔记在 Obsidian vault 中：

```bash
# 配置 Obsidian vault 路径
echo "OBSIDIAN_VAULT=~/Documents/Obsidian-Sync" >> ~/.knowledge-base/.env

# 拉取 Obsidian 笔记到知识库
kb vault seed "所有主题"
```

预期输出：

```
📦 从 Obsidian 拉取笔记...
扫描 vault: ~/Documents/Obsidian-Sync
找到 42 个匹配笔记
已创建符号链接: 42 个文件
✅ 完成
```

## 第四步：编译知识库（2 分钟）

### 首次编译

```bash
# 查看系统状态
kb status
```

预期输出：

```
📚 Dochris 知识库状态
════════════════════════════════════════════
工作区:    ~/.knowledge-base
源文件:    25 个
已编译:    0 个
待编译:    25 个
质量达标:  0 个
════════════════════════════════════════════
```

```bash
# 摄入文件（扫描并创建 manifest）
kb ingest
```

预期输出：

```
📥 Phase 1: 摄入文件
扫描 raw/ 目录...
发现 25 个文件
创建 manifest: SRC-0001 ~ SRC-0025
去重: 0 个重复文件
✅ 摄入完成: 25 个文件
```

```bash
# 编译（LLM 提取结构化内容）
kb compile 10          # 先编译前 10 个试试
```

预期输出：

```
⚙️ Phase 2: 编译文档
────────────────────────────────────────
编译 SRC-0001 论文-注意力机制.pdf ... ✓ (质量: 92)
编译 SRC-0002 播客-AI趋势.mp3 ............. ✓ (质量: 88)
编译 SRC-0003 读书笔记-原则.md ............. ✓ (质量: 95)
...
────────────────────────────────────────
✅ 编译完成: 10/10 成功, 0 失败
```

### 提高编译速度

```bash
# 使用更多并发
kb compile --concurrency 6

# 后台运行大量文件
nohup kb compile > compile.log 2>&1 &
```

### 查看进度

```bash
# 查看当前状态
kb status

# 质量报告
kb quality --report
```

## 第五步：开始查询（30 秒）

### CLI 查询

```bash
# 语义搜索
kb query "注意力机制在 Transformer 中的作用"

# 查看详细输出
kb query "费曼学习法" --verbose

# 限制返回数量
kb query "机器学习优化方法" --top-k 5
```

预期输出：

```
🔍 查询: 注意力机制在 Transformer 中的作用

找到 3 个相关结果:

1. [质量: 95] SRC-0001 - 论文-注意力机制.pdf
   📝 注意力机制是 Transformer 的核心组件，通过计算查询(Query)、
   键(Key)、值(Value) 三个向量的点积注意力来实现...

2. [质量: 88] SRC-0015 - Transformer详解.md
   📝 Transformer 架构完全基于注意力机制，摒弃了传统的循环和卷积...

3. [质量: 82] SRC-0008 - 深度学习综述.pdf
   📝 自注意力机制允许模型在处理序列时直接关注任意位置的信息...
```

### Web UI 查询

```bash
# 启动 Web UI（需要安装 .[all]）
kb serve --web
```

预期输出：

```
🌐 启动 Gradio Web UI...
Running on local URL:  http://127.0.0.1:7860
```

打开浏览器访问 `http://127.0.0.1:7860`，你可以：
- 📝 **查询**：语义搜索知识库
- ⚙️ **编译**：可视化管理编译任务
- 📊 **质量**：查看质量仪表盘
- 🕸️ **图谱**：浏览知识图谱

### API 服务

```bash
# 启动 API 服务
kb serve

# 或指定端口
kb serve --port 9000
```

预期输出：

```
🚀 API 服务已启动
地址: http://127.0.0.1:8000
文档: http://127.0.0.1:8000/docs
```

API 调用示例：

```bash
curl -X POST http://127.0.0.1:8000/api/query \
  -H "Content-Type: application/json" \
  -d '{"query": "注意力机制", "top_k": 5}'
```

## 进阶使用

### 质量检查与晋升

```bash
# 查看质量报告
kb quality --report

# 晋升高质量内容到 wiki 层（质量分 ≥ 85）
kb promote SRC-0001 --to wiki

# 批量晋升
kb promote --batch --min-score 85 --to wiki

# 推送到 Obsidian
kb promote SRC-0001 --to obsidian
```

### 知识图谱

```bash
# 查看图谱统计
kb graph stats

# 搜索图谱节点
kb graph search "注意力机制"

# 导出图谱
kb graph export -o graph.json
```

### Obsidian 双向同步

```bash
# 从 Obsidian 拉取笔记
kb vault seed "AI 相关"

# 推送高质量内容到 Obsidian
kb vault push

# 查看同步状态
kb vault status
```

### Docker 部署

```bash
# 构建镜像
docker build -t dochris --build-arg BUILD_TARGET=all .

# 运行容器
docker run -d \
  -p 8000:8000 \
  -p 7860:7860 \
  -v ~/my-knowledge:/workspace \
  -e OPENAI_API_KEY=your_key \
  --name dochris \
  dochris
```

## 常见问题

### API Key 相关

**Q: 如何获取智谱 API Key？**

访问 [https://open.bigmodel.cn/](https://open.bigmodel.cn/) 注册账号，在控制台创建 API Key。新用户有免费额度。

**Q: 有免费方案吗？**

有的！使用 OpenRouter 的免费模型：

```bash
export OPENAI_API_BASE="https://openrouter.ai/api/v1"
export MODEL="qwen/qwen-2.5-72b-instruct:free"
export OPENAI_API_KEY="your_openrouter_key"
```

### 编译失败处理

**Q: 编译时报错 `400 error 1301`**

这是 API 内容审核拦截。系统会自动清洗敏感词。如仍遇到，尝试：
1. 检查文件内容是否包含敏感信息
2. 使用其他 API 提供商

**Q: 质量评分总是很低**

重试编译通常能获得更高分数：

```bash
# 重新编译指定文件
kb compile --src-id SRC-0001 --force

# 批量重新编译低分文件
kb quality --report    # 查看低分文件
kb compile --min-score 60 --force
```

### 内存不足

**Q: 编译时内存不够怎么办？**

1. 降低并发数：
   ```bash
   export MAX_CONCURRENCY=1
   kb compile
   ```
2. 使用轻量级查询模型：
   ```bash
   export QUERY_MODEL=glm-4-flash
   ```
3. 使用 FAISS 代替 ChromaDB（更省内存）：
   ```bash
   export VECTOR_STORE=faiss
   ```

### 其他问题

**Q: 如何检查环境是否正常？**

```bash
kb doctor
```

**Q: 如何查看完整配置？**

```bash
kb config
```

**Q: 如何查看版本信息？**

```bash
kb version
```
