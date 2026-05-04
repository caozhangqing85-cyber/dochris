# 使用示例

> 5 个真实场景，展示 Dochris 如何将不同类型的资料转化为可查询的知识库。

---

## 场景 1：学术论文管理

> **需求**：我下载了 20 篇 AI 相关的 PDF 论文，想快速找到「注意力机制在不同模型中的变体」。

### 步骤

```bash
# 1. 将论文放入 raw/pdfs/
cp ~/Downloads/papers/*.pdf ~/.knowledge-base/raw/pdfs/

# 2. 摄入文件
kb ingest

# 3. 编译所有论文
kb compile
```

预期输出：

```
📥 Phase 1: 摄入文件
发现 20 个文件
创建 manifest: SRC-0001 ~ SRC-0020

⚙️ Phase 2: 编译文档
编译 SRC-0001 attention-is-all-you-need.pdf ... ✓ (质量: 94)
编译 SRC-0002 bert-pretraining.pdf ................. ✓ (质量: 91)
编译 SRC-0003 gpt-3-language-models.pdf ........... ✓ (质量: 89)
...
✅ 编译完成: 20/20 成功, 0 失败
```

### 查询

```bash
kb query "注意力机制在不同模型中的变体"
```

预期输出：

```
🔍 找到 4 个相关结果:

1. [质量: 94] SRC-0001 - attention-is-all-you-need.pdf
   📝 原始 Transformer 使用缩放点积注意力(Scaled Dot-Product Attention)，
   通过多头机制(Multi-Head Attention)让模型关注不同位置的信息...

2. [质量: 91] SRC-0002 - bert-pretraining.pdf
   📝 BERT 采用双向自注意力，通过 [MASK] 机制实现双向上下文理解，
   相比单向注意力能捕获更完整的上下文信息...

3. [质量: 89] SRC-0003 - gpt-3-language-models.pdf
   📝 GPT-3 使用因果注意力(Causal/Masked Attention)，通过下三角
   矩阵掩码确保每个位置只能关注之前的信息...

4. [质量: 87] SRC-0015 - efficient-attention.pdf
   📝 Linformer 提出低秩近似注意力，将注意力复杂度从 O(n²) 降到
   O(n)，通过投影矩阵压缩 Key 和 Value 的序列长度...
```

### 查看结构化摘要

```bash
cat ~/.knowledge-base/outputs/summaries/SRC-0001.md
```

```markdown
# Attention Is All You Need

## 摘要
本文提出了 Transformer 架构，完全基于注意力机制，摒弃了
传统的循环和卷积结构...

## 关键点
1. 多头注意力机制允许模型同时关注不同位置的不同表示子空间
2. 位置编码使用正弦/余弦函数，避免引入顺序参数
3. 缩放因子 1/√d_k 防止点积在维度较大时梯度过小
4. 编码器-解码器架构实现了灵活的序列到序列转换
5. 学习率预热(Warmup)策略对训练稳定性至关重要

## 概念
- **Self-Attention**: 查询、键、值均来自同一输入序列
- **Multi-Head Attention**: 将注意力空间分成多个头并行计算
- **Positional Encoding**: 正弦余弦函数编码位置信息
```

---

## 场景 2：播客/课程笔记

> **需求**：我有 10 期 AI 播客的 MP3 文件，想提取关键观点并能在之后搜索。

### 步骤

```bash
# 1. 安装音频处理依赖（如果还没有）
pip install -e ".[audio]"

# 2. 放入音频文件
cp ~/Podcasts/AI-Trending/*.mp3 ~/.knowledge-base/raw/audio/

# 3. 摄入
kb ingest

# 4. 编译（会自动转录音频 → 生成摘要）
kb compile --concurrency 2
```

预期输出：

```
⚙️ Phase 2: 编译文档
转录 SRC-0001 ai-trends-2026-ep01.mp3 (45min) ... ✓
转录 SRC-0002 ai-trends-2026-ep02.mp3 (38min) ... ✓
编译 SRC-0001 ... ✓ (质量: 90)
编译 SRC-0002 ... ✓ (质量: 87)
...
✅ 编译完成: 10/10 成功
```

### 查询

```bash
kb query "2026年 AI 发展趋势"
```

预期输出：

```
🔍 找到 3 个相关结果:

1. [质量: 90] SRC-0001 - ai-trends-2026-ep01.mp3
   📝 2026年AI领域三大趋势：1) 多模态大模型成为标配，GPT-5和
   Gemini Ultra 引领视觉-语言融合；2) AI Agent 从概念走向
   实际应用，自动化工作流显著提升生产力...

2. [质量: 87] SRC-0002 - ai-trends-2026-ep02.mp3
   📝 播客讨论了开源模型的快速发展，Llama 4 和 Qwen 3 在
   多项基准测试中接近闭源模型水平...
```

### 提示

- 音频转录需要 `faster-whisper` 依赖，首次编译会自动下载模型
- 编译时间与音频长度成正比，建议使用 `--concurrency 2` 控制内存
- 转录后的文本保存在 `transcripts/` 目录

---

## 场景 3：Obsidian 笔记增强

> **需求**：我在 Obsidian 中积累了 200+ 篇学习笔记，想让 AI 帮我整理、搜索、并推送高质量内容。

### 步骤

```bash
# 1. 配置 Obsidian vault 路径
echo "OBSIDIAN_VAULT=~/Documents/Obsidian-Sync" >> ~/.knowledge-base/.env

# 2. 从 Obsidian 拉取笔记
kb vault seed "所有主题"
```

预期输出：

```
📦 从 Obsidian 拉取笔记
扫描 vault: ~/Documents/Obsidian-Sync
发现 200+ 个 Markdown 文件
匹配: 200 个
创建符号链接: 200 个文件
✅ 拉取完成
```

```bash
# 3. 摄入并编译
kb ingest
kb compile --concurrency 4
```

```bash
# 4. 质量检查
kb quality --report
```

预期输出：

```
📊 质量报告
════════════════════════════════════════════════
总文件:   200
已编译:   200
质量分布:
  90-100: 45 个 (22.5%)  ⭐⭐⭐
  85-89:  78 个 (39.0%)  ⭐⭐
  70-84:  52 个 (26.0%)  ⭐
  <70:    25 个 (12.5%)  ❌
════════════════════════════════════════════════
```

```bash
# 5. 晋升高质量内容
kb promote --batch --min-score 85 --to wiki

# 6. 推送精选内容回 Obsidian
kb vault push
```

### 查询

```bash
kb query "费曼学习法的核心步骤"
```

```
🔍 找到 2 个相关结果:

1. [质量: 95] SRC-0042 - 费曼学习法笔记.md
   📝 费曼学习法四步：1) 选择一个概念 2) 用简单语言解释给
   外行听 3) 发现解释不清的地方，回到原始材料学习 4) 简化
   直到连小学生都能理解...

2. [质量: 88] SRC-0115 - 学习方法总结.md
   📝 费曼技巧的关键在于"教是最好的学"，通过主动回忆和
   简化表达来发现知识盲点...
```

### 双向同步

```bash
# 查看同步状态
kb vault status

# 拉取新笔记
kb vault seed "AI 学习"

# 推送知识库内容到 Obsidian
kb vault push --min-score 90
```

---

## 场景 4：电子书知识提取

> **需求**：我有一批 EPUB/MOBI 格式的电子书，想提取核心概念和知识要点。

### 步骤

```bash
# 1. 安装电子书解析插件
# 将 epub_parser.py 放入插件目录
mkdir -p ~/.knowledge-base/plugins/
cp examples/plugins/epub_parser.py ~/.knowledge-base/plugins/

# 2. 启用插件
kb plugin enable epub_parser

# 3. 放入电子书
cp ~/ebooks/*.epub ~/.knowledge-base/raw/ebooks/

# 4. 摄入并编译
kb ingest
kb compile
```

预期输出：

```
📥 Phase 1: 摄入文件
发现 8 个电子书文件
使用 epub_parser 解析 EPUB 文件...

⚙️ Phase 2: 编译文档
编译 SRC-0001 thinking-fast-slow.epub ... ✓ (质量: 93)
编译 SRC-0002 atomic-habits.epub .......... ✓ (质量: 91)
编译 SRC-0003 principles.epub ............. ✓ (质量: 96)
...
✅ 编译完成: 8/8 成功
```

### 查询

```bash
kb query "系统1和系统2的区别"
```

```
🔍 找到 1 个相关结果:

1. [质量: 93] SRC-0001 - thinking-fast-slow.epub
   📝 卡尼曼将人类思维分为两个系统：系统1（快思考）是自动化的、
   直觉的、毫不费力的，负责日常快速决策；系统2（慢思考）是
   刻意的、分析的、需要消耗精力的，用于复杂问题求解...

## 概念
- **系统1 (System 1)**: 快速、自动、无意识的思维方式
- **系统2 (System 2)**: 缓慢、刻意、需要努力的思维方式
- **锚定效应**: 先入为主的信息对后续判断的影响
- **可得性启发**: 根据信息容易想起来的程度来判断概率
```

---

## 场景 5：团队知识共享

> **需求**：团队需要一个共享的知识库 API 服务，供多个应用查询。

### 步骤

```bash
# 1. 编译知识库（同上）
kb ingest
kb compile

# 2. 配置 API 认证（可选）
echo "DOCHRIS_API_KEY=your_secret_key" >> ~/.knowledge-base/.env
echo "DOCHRIS_CORS_ORIGINS=https://your-app.example.com" >> ~/.knowledge-base/.env

# 3. 启动 API 服务
kb serve --port 8000
```

预期输出：

```
🚀 API 服务已启动
地址: http://0.0.0.0:8000
文档: http://0.0.0.0:8000/docs
认证: 已启用 (DOCHRIS_API_KEY)
```

### API 调用

```bash
# 查询知识库
curl -X POST http://localhost:8000/api/query \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your_secret_key" \
  -d '{
    "query": "微服务架构最佳实践",
    "top_k": 5
  }'
```

预期返回：

```json
{
  "query": "微服务架构最佳实践",
  "results": [
    {
      "src_id": "SRC-0012",
      "title": "微服务设计模式.pdf",
      "score": 0.92,
      "summary": "微服务架构的核心原则包括单一职责、自治性、去中心化治理...",
      "key_points": [
        "每个微服务应拥有独立的数据存储",
        "API 网关作为统一入口处理路由和认证",
        "使用服务发现替代硬编码服务地址"
      ]
    }
  ],
  "total": 3
}
```

### 启动 Web UI（可选）

```bash
# 同时启动 API 和 Web UI
kb serve --web --port 8000
```

团队成员可以：
- 🌐 通过 Web UI 浏览和查询知识库
- 🔗 通过 API 集成到自己的应用
- 📊 查看质量仪表盘了解知识库健康度
- 🕸️ 浏览知识图谱发现概念关联

### Docker 部署（生产环境）

```bash
# 构建镜像
docker build -t dochris --build-arg BUILD_TARGET=all .

# 运行
docker run -d \
  --name dochris \
  -p 8000:8000 \
  -p 7860:7860 \
  -v ~/shared-knowledge:/workspace \
  -e OPENAI_API_KEY=sk-xxx \
  -e DOCHRIS_API_KEY=team-secret-key \
  -e DOCHRIS_CORS_ORIGINS=https://app.example.com \
  dochris
```

---

## 更多命令速查

| 命令 | 用途 |
|------|------|
| `kb status` | 查看系统状态 |
| `kb doctor` | 环境诊断 |
| `kb ingest` | 摄入文件 |
| `kb compile 10` | 编译前 10 个 |
| `kb compile --force` | 强制重新编译 |
| `kb query "关键词"` | 语义查询 |
| `kb query "关键词" --top-k 3` | 限制返回数量 |
| `kb quality --report` | 质量报告 |
| `kb promote SRC-0001 --to wiki` | 晋升到 wiki 层 |
| `kb promote --batch --min-score 90 --to obsidian` | 批量推送 |
| `kb vault seed "主题"` | 从 Obsidian 拉取 |
| `kb vault push` | 推送到 Obsidian |
| `kb graph stats` | 知识图谱统计 |
| `kb serve --web` | 启动 Web UI |
| `kb config` | 查看配置 |
| `kb plugin list` | 列出插件 |
