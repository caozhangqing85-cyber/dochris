# LLM 高效处理长文本 PDF 文档的摘要/知识提取 — 深度调研报告

> 调研日期：2026-04-18  
> 目标场景：中文 PDF（知乎长文、电子书、课程材料）→ LLM 结构化摘要  
> LLM：智谱 glm-4-flash（128K 上下文，TPM 有限）  
> 文档规模：解析后 2-8 万汉字

---

## 目录

1. [主流方案对比](#1-主流方案对比)
2. [GitHub 项目调研](#2-github-项目调研)
3. [学术论文](#3-学术论文)
4. [推荐方案](#4-推荐方案)
5. [实施建议](#5-实施建议)

---

## 1. 主流方案对比

### 1.1 Map-Reduce（分段摘要再合并）

**原理**：将长文档切分为多个 chunk，每个 chunk 独立生成摘要（Map 阶段），然后将所有 chunk 摘要合并，再由 LLM 生成最终全局摘要（Reduce 阶段）。

**流程**：
```
原文 → [chunk1, chunk2, ..., chunkN]
     → Map: 每个chunk独立摘要 → [summary1, summary2, ..., summaryN]
     → Reduce: 合并所有summary → 最终摘要
```

**优点**：
- ✅ 并行处理，速度快（Map 阶段可并发）
- ✅ 实现简单，LangChain 内置支持
- ✅ 对 TPM 友好（每次请求 token 量可控）
- ✅ 容错性好（单个 chunk 失败不影响整体）

**缺点**：
- ❌ 丢失跨 chunk 的上下文关联（如"如前所述"这类引用）
- ❌ 信息可能遗漏（某 chunk 的关键信息在摘要中被压缩掉）
- ❌ Reduce 阶段的输入质量依赖 Map 质量
- ❌ 对结构化文档（如教材）不够友好

**适用场景**：文档各部分相对独立、对速度要求高的场景。

---

### 1.2 Map-Chain / Stuff-Chain（逐段链式摘要）

**原理**：按顺序处理每个 chunk，将前一个 chunk 的摘要作为下一个 chunk 的上下文，逐步积累信息。

**流程**：
```
chunk1 + system_prompt → summary1
chunk2 + summary1 + system_prompt → summary2
chunk3 + summary2 + system_prompt → summary3
...
summaryN → 最终摘要
```

**优点**：
- ✅ 保留了文档的顺序信息流
- ✅ 比 Map-Reduce 更好地处理跨段引用
- ✅ 适合叙事性文档（小说、散文）

**缺点**：
- ❌ 无法并行，串行处理速度慢
- ❌ 信息累积可能丢失早期信息（"漏斗效应"）
- ❌ 后面 chunk 的处理质量受前面 chunk 摘要质量的影响
- ❌ 越往后，context 越长，token 消耗增大
- ❌ 错误会级联放大

**适用场景**：叙事性文档、前后逻辑强关联的文档。

---

### 1.3 Sliding Window（滑动窗口）

**原理**：用一个固定大小的窗口在文档上滑动，相邻窗口之间保留重叠区域（overlap），确保边界信息不丢失。

**流程**：
```
[chunk1: 0-3000] [chunk2: 2500-5500] [chunk3: 5000-8000] ...
     ↑ 500字重叠    ↑ 500字重叠
```

**优点**：
- ✅ 边界处信息不会丢失
- ✅ 可以并行处理（如果不需要全局合并）
- ✅ 实现简单

**缺点**：
- ❌ 重叠区域浪费 token（增加成本）
- ❌ overlap 太小 → 仍然丢失边界信息；太大 → 冗余太多
- ❌ 没有全局视角，缺乏整体理解
- ❌ 重叠区域可能产生重复摘要

**适用场景**：作为其他方案的补充手段（分段策略），而非独立的摘要方案。

---

### 1.4 Hierarchical Summarization（分层摘要）

**原理**：模拟人类阅读文档的方式，自底向上分层摘要。先对段落生成摘要，再将段落摘要按章节分组，对章节摘要再生成全局摘要。

**流程**：
```
段落层：[p1, p2, ..., pn] → [s1, s2, ..., sn]（段落摘要）
章节层：[s1..s5, s6..s10, ...] → [cs1, cs2, ...]（章节摘要）
文档层：[cs1, cs2, ...] → 最终摘要
```

**优点**：
- ✅ 保留文档层次结构
- ✅ 信息保真度高（每层只做轻度压缩）
- ✅ 可以在任何层级停止（灵活控制粒度）
- ✅ 特别适合结构化文档（教材、论文）

**缺点**：
- ❌ LLM 调用次数多（N段 → N次 + M章 → M次 + 1次）
- ❌ 每一层都可能引入信息损失
- ❌ 需要预先知道文档结构（或先做结构检测）
- ❌ 实现复杂度较高

**适用场景**：结构化文档（教材、论文、技术文档），需要保留层次关系的场景。

---

### 1.5 Refine（迭代精炼）

**原理**：LangChain 提出的方案。维护一个"运行摘要"，逐段将新内容融入已有摘要。每处理一段，都将已有摘要与新段落一起送入 LLM，让 LLM 更新摘要。

**流程**：
```
initial_prompt + chunk1 → running_summary_v1
running_summary_v1 + chunk2 → running_summary_v2
running_summary_v2 + chunk3 → running_summary_v3
...
running_summary_vN → final_summary
```

**与 Map-Chain 的区别**：Refine 每次都将**完整已有摘要**传递给 LLM，让 LLM 融合新信息，而不是基于上一段摘要生成新摘要。

**优点**：
- ✅ 信息保真度最高（已有摘要始终完整保留）
- ✅ 新旧信息自然融合
- ✅ 适合提取知识点（可以持续累积概念列表）

**缺点**：
- ❌ 串行处理，速度最慢
- ❌ 每次请求都包含完整已有摘要，token 消耗随文档增长
- ❌ 后期 context 可能很长（running_summary + new_chunk）
- ❌ 仍可能丢失早期细节（摘要压缩导致）

**适用场景**：质量优先、文档不太长（<5万字）、需要高保真的场景。

---

### 1.6 Map-Rerank（分段排序）

**原理**：将文档分段后，先用一个轻量级模型对每个 chunk 打分（relevance score），只选择最相关的 top-K 个 chunk 进行处理。

**流程**：
```
原文 → [chunk1, chunk2, ..., chunkN]
     → Rerank: 每个 chunk 评分 → [chunk3(0.95), chunk7(0.88), chunk1(0.82)]
     → 只处理 top-K → [summary3, summary7, summary1]
     → 合并
```

**优点**：
- ✅ 大幅减少需要处理的 token 量
- ✅ 聚焦最相关内容

**缺点**：
- ❌ 需要额外的 rerank 模型（或用 LLM 自己打分）
- ❌ 可能遗漏重要但不"相关"的内容
- ❌ 不适合全文摘要场景（更适合问答/RAG）
- ❌ 打分本身也需要 token 消耗

**适用场景**：针对特定问题的信息提取（而非全文摘要），RAG 场景。

---

### 1.7 LLMLingua / LongLLMLingua（Prompt 压缩）

**原理**：微软研究院提出的方法，通过训练一个小模型来识别和删除 prompt 中的"不重要" token，从而压缩输入长度。

- **LLMLingua**（arxiv: 2310.05736）：基于困惑度（perplexity）的 token 级压缩，可以压缩到原始长度的 20%。
- **LongLLMLingua**（arxiv: 2310.06839）：针对长上下文场景优化，加入 question-aware 压缩策略。
- **LLMLingua-2**（arxiv: 2403.12968）：数据蒸馏方法，不需要 GPT-4 训练，更轻量。

**优点**：
- ✅ 可以将 prompt 压缩 4-5 倍
- ✅ 压缩后仍保持较好的下游任务性能
- ✅ 开源可用（pip install llmlingua）

**缺点**：
- ❌ 主要针对英文优化，中文效果可能下降
- ❌ 压缩是非语义的（基于 perplexity），可能误删关键内容
- ❌ 对于需要完整理解全文的摘要任务，压缩可能丢失关键信息
- ❌ 需要额外运行压缩模型（虽然小模型很快）
- ❌ 对于"提取所有知识点"这种需求，压缩可能删掉不常见但重要的概念

**适用场景**：RAG 问答、有明确查询目标的场景；不太适合需要完整知识提取的场景。

---

### 1.8 其他方案

#### 1.8.1 MemWalker（2023）
通过构建文档的"记忆树"（memory tree），先让 LLM 浏览树状索引，再深入读取相关段落。适合长文档问答，不太适合摘要。

#### 1.8.2 Recap（2024, arxiv: 2401.06168）
递归总结 + 分块检索，将文档总结为递归结构，查询时先匹配总结再深入。适合问答场景。

#### 1.8.3 Adaptive Chunking（2026, arxiv: 2603.25333）
动态选择最优分块方法，根据文档特征自动选择语义分块、固定长度分块等策略。

#### 1.8.4 Focus-dLLM（2026, arxiv: 2602.02159）
基于置信度引导的上下文聚焦，动态裁剪不重要的 token。仍在研究阶段。

#### 1.8.5 Context-Aware Hierarchical Merging（2025, arxiv: 2502.00977）
爱丁堡大学提出，在分层合并时考虑上下文感知，用于长文档摘要。与 Hierarchical Summarization 类似但加入了上下文融合。

#### 1.8.6 RST-LoRA（2024, arxiv: 2405.00657）
利用修辞结构理论（Rhetorical Structure Theory）的 LoRA 微调方法，提高长文档摘要质量。需要微调，不太适合直接使用。

---

### 1.9 方案对比总结表

| 方案 | 并行能力 | 信息保真度 | 实现复杂度 | Token效率 | 中文适用性 | 适合全文摘要 |
|------|---------|-----------|-----------|----------|-----------|------------|
| **Map-Reduce** | ⭐⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ |
| **Map-Chain** | ⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ |
| **Sliding Window** | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐ |
| **Hierarchical** | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ |
| **Refine** | ⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| **Map-Rerank** | ⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐ |
| **LLMLingua** | N/A | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐ |
| **Hierarchical+Refine** | ⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |

---

## 2. GitHub 项目调研

### 2.1 LangChain — Document Summarization Chains

- **GitHub**: https://github.com/langchain-ai/langchain
- **Stars**: ~100k+
- **核心模块**: `langchain.chains.summarize`
  - `load_summarize_chain` 支持 4 种模式：`stuff`, `map_reduce`, `refine`, `map_rerank`
  - `RecursiveCharacterTextSplitter` — 递归字符分割器
  - `TokenTextSplitter` — 按 token 数分割
  - `MarkdownHeaderTextSplitter` — 按 Markdown 标题分割
  - `SemanticChunker` — 语义分块（基于 embedding 相似度）

**核心思路**：
```python
from langchain.chains.summarize import load_summarize_chain
from langchain_community.document_loaders import PyPDFLoader

loader = PyPDFLoader("document.pdf")
docs = loader.load()
chain = load_summarize_chain(llm, chain_type="map_reduce")
result = chain.run(docs)
```

**优点**：
- ✅ 开箱即用，API 设计优秀
- ✅ 支持多种分割策略和摘要策略
- ✅ 社区活跃，文档完善
- ✅ 支持自定义 prompt 模板

**缺点**：
- ❌ 抽象层次过高，难以精细控制
- ❌ 对中文 PDF 的结构解析较弱（依赖 PDF loader）
- ❌ `stuff` 模式对长文档不适用
- ❌ 默认分块策略对中文不够友好（按字符分割不如按语义分割）

**中文适用性**：⭐⭐⭐（框架可用，但需要自定义分块策略）

---

### 2.2 LlamaIndex — Document Processing

- **GitHub**: https://github.com/run-llama/llama_index
- **Stars**: ~40k+
- **核心模块**:
  - `SentenceSplitter` — 句子级分割
  - `SemanticSplitter` — 语义分割
  - `DocumentSummaryIndex` — 文档摘要索引
  - `SummaryIndex` / `TreeIndex` / `ListIndex` — 多种索引结构
  - `RefinePrompt` — 迭代精炼 prompt

**核心思路**：
LlamaIndex 更侧重于构建可查询的文档索引。`DocumentSummaryIndex` 会在构建时为每个文档/节点生成摘要，查询时先匹配摘要再深入。

```python
from llama_index.core import DocumentSummaryIndex, SimpleDirectoryReader

docs = SimpleDirectoryReader("./data").load_data()
doc_summary_index = DocumentSummaryIndex.from_documents(docs)
```

**优点**：
- ✅ 多种索引结构，灵活选择
- ✅ `DocumentSummaryIndex` 天然支持分层摘要
- ✅ 与 RAG 流程无缝集成
- ✅ 对长文档处理有专门优化

**缺点**：
- ❌ 更侧重检索场景，纯摘要功能不如 LangChain 直接
- ❌ 需要理解 Index 概念，学习曲线稍高
- ❌ 中文文档处理同样需要自定义

**中文适用性**：⭐⭐⭐（框架可用，但需要自定义）

---

### 2.3 Unstructured

- **GitHub**: https://github.com/Unstructured-IO/unstructured
- **Stars**: ~12k+
- **核心功能**：
  - PDF / DOCX / PPTX / HTML 等多格式解析
  - 自动检测文档结构（标题、段落、表格、列表、图片）
  - 输出结构化元素（Title, NarrativeText, Table, ListItem 等）
  - 支持分块（chunking）并保留结构信息

**核心思路**：
```python
from unstructured.partition.auto import partition
from unstructured.chunking.title import chunk_by_title

elements = partition(filename="document.pdf")
chunks = chunk_by_title(elements)
```

**优点**：
- ✅ PDF 结构解析能力强（特别是表格、标题）
- ✅ 分块时保留文档结构信息（每个 chunk 知道来自哪个标题下）
- ✅ 支持多种分块策略：按标题、按页面、按固定大小
- ✅ 开源免费版功能足够

**缺点**：
- ❌ 安装较重（依赖很多系统库）
- ❌ 对中文 PDF 的 OCR 能力有限（需要配合 Tesseract）
- ❌ 分块功能是新增的，API 还在演进
- ❌ 处理速度较慢（特别是大文件）

**中文适用性**：⭐⭐⭐（结构解析可用，但中文 OCR 需额外配置）

---

### 2.4 LlamaParse

- **GitHub**: https://github.com/run-llama/llama_parse
- **Stars**: ~5k+
- **核心功能**：
  - 基于 LLM 的 PDF 解析器
  - 自动识别文档结构、表格、图片
  - 输出 Markdown 格式
  - 特别擅长复杂布局的 PDF

**核心思路**：
```python
from llama_parse import LlamaParse

parser = LlamaParse(result_type="markdown")
documents = parser.load_data("document.pdf")
```

**优点**：
- ✅ 解析质量高，特别是复杂布局
- ✅ 输出 Markdown，天然保留结构
- ✅ 与 LlamaIndex 无缝集成
- ✅ 支持中文

**缺点**：
- ❌ **免费额度有限**（每天 1000 页），大量处理需要付费
- ❌ 依赖云端 API（不是完全本地）
- ❌ 解析速度取决于 API 响应速度
- ❌ 成本可能较高

**中文适用性**：⭐⭐⭐⭐（支持中文，但付费限制）

---

### 2.5 PyMuPDF / pdfplumber（PDF 解析工具）

虽然不是专门的摘要工具，但作为 PDF 解析环节的重要选择：

**PyMuPDF (fitz)**
- GitHub: https://github.com/pymupdf/PyMuPDF (~13k stars)
- 速度快、功能全、支持文本+图片+表格提取
- 中文支持好
- 推荐作为 PDF 文本提取的首选工具

**pdfplumber**
- GitHub: https://github.com/jsvine/pdfplumber (~6k stars)
- 专注表格提取
- 速度比 PyMuPDF 慢，但表格处理更精确

---

### 2.6 专门的 PDF 摘要/知识提取项目

#### 2.6.1 docetl / etl-for-llms
- GitHub: https://github.com/ucbepic/docetl (~3k stars)
- 用声明式 YAML 定义文档处理管道
- 支持 Map-Reduce 模式处理大量文档
- 适合批量处理，但配置较复杂

#### 2.6.2 document-chat / chatpdf
- 多个类似项目（ChatPDF, PrivateGPT 等）
- 主要是问答场景，不是摘要场景
- 大多基于 LangChain/LlamaIndex 封装

#### 2.6.3 paper-qa
- GitHub: https://github.com/Future-House/paper-qa (~12k stars)
- 专注于学术论文的 QA 和摘要
- 内置引用追踪和摘要生成
- 英文学术论文效果好，中文一般

#### 2.6.4 marker
- GitHub: https://github.com/VikParuchuri/marker (~25k stars)
- PDF → Markdown 转换工具
- 使用深度学习模型（Nougat、LayoutLM 等）
- 支持数学公式、表格、多栏布局
- 中等中文支持（依赖 OCR 模型）

#### 2.6.5 MinerU (opendatalab)
- GitHub: https://github.com/opendatalab/MinerU (~35k stars)
- ⭐ **中文 PDF 解析首选**
- 专门针对中文 PDF 优化
- 支持公式、表格、多栏布局
- 输出 Markdown 格式
- 开源免费，可本地部署
- 有 GUI 和 API 两种模式

**中文适用性**：⭐⭐⭐⭐⭐（专为中文设计）

---

### 2.7 中文长文档处理项目

#### 2.7.1 MinerU (opendatalab)
- 如上所述，35k+ stars
- 目前最好的开源中文 PDF 解析工具
- 推荐作为中文 PDF 文本提取的首选

#### 2.7.2 magic-pdf (opendatalab)
- MinerU 的前身/组件
- 专注 PDF 转 Markdown

#### 2.7.3 Surya
- GitHub: https://github.com/VikParuchuri/surya (~15k stars)
- 多语言 OCR 工具
- 支持布局检测、文本识别、阅读顺序检测
- 中文支持中等

#### 2.7.4 PaddleOCR / PaddlePP-Structure
- 百度开源
- 中文 OCR 能力最强
- 支持文档结构分析（版面分析）
- 可以检测标题、段落、表格、图片等区域
- 推荐用于扫描版中文 PDF

#### 2.7.5 text2vec / bge-embedding
- 中文 embedding 模型（BAAI/bge 系列）
- 可用于语义分块（计算段落相似度来决定分割点）

---

### 2.8 GitHub 项目对比总结

| 项目 | Stars | 核心能力 | 中文适用 | 推荐度 |
|------|-------|---------|---------|-------|
| **MinerU** | 35k | PDF→Markdown解析 | ⭐⭐⭐⭐⭐ | 🥇 解析首选 |
| **LangChain** | 100k | 摘要链式处理 | ⭐⭐⭐ | 🥇 框架首选 |
| **LlamaIndex** | 40k | 文档索引+摘要 | ⭐⭐⭐ | 🥈 框架备选 |
| **marker** | 25k | PDF→Markdown | ⭐⭐⭐⭐ | 🥈 解析备选 |
| **PaddleOCR** | 45k | 中文OCR+版面 | ⭐⭐⭐⭐⭐ | 🥇 扫描件首选 |
| **PyMuPDF** | 13k | PDF文本提取 | ⭐⭐⭐⭐ | 文本PDF首选 |
| **Unstructured** | 12k | 结构化分块 | ⭐⭐⭐ | 分块参考 |
| **LlamaParse** | 5k | LLM PDF解析 | ⭐⭐⭐⭐ | 付费方案 |

---

## 3. 学术论文

### 3.1 Prompt 压缩方向

#### LLMLingua (2023, arxiv: 2310.05736)
- **作者**: Huiqiang Jiang 等（微软研究院）
- **核心思想**: 基于困惑度（perplexity）的 token 级 prompt 压缩
- **压缩率**: 可达 20x（压缩到原始 5%）
- **关键发现**: 压缩后的 prompt 在多项下游任务中保持了 90%+ 的性能
- **局限**: 主要针对英文

#### LongLLMLingua (2023, arxiv: 2310.06839)
- **作者**: 同上
- **核心思想**: 针对长上下文场景优化，加入 question-aware 压缩
- **关键发现**: 在长上下文 QA 任务中，压缩后反而提升了性能（因为减少了噪声干扰）
- **局限**: 需要有明确的 question/目标

#### LLMLingua-2 (2024, arxiv: 2403.12968)
- **核心思想**: 数据蒸馏方法训练压缩模型，不需要 GPT-4
- **改进**: 更轻量、更快、更容易部署
- **适用**: 作为通用 prompt 压缩工具

#### PCToolkit (2024, arxiv: 2403.17411)
- 统一的 prompt 压缩工具包，集成了多种压缩方法
- 可直接比较不同方法的性能

#### Characterizing Prompt Compression (2024, arxiv: 2407.08892)
- 系统性评测了多种 prompt 压缩方法
- 发现：压缩方法在摘要任务上效果不如 QA 任务
- **关键结论**: 对于需要完整信息保留的摘要任务，压缩方法可能导致显著的信息损失

---

### 3.2 长文档摘要方向

#### Context-Aware Hierarchical Merging (2025, arxiv: 2502.00977)
- **作者**: Litu Ou, Mirella Lapata（爱丁堡大学）
- **核心思想**: 在分层合并摘要时加入上下文感知机制
- **方法**: 相邻的摘要合并时，保留合并前的上下文信息
- **结果**: 在多个长文档摘要 benchmark 上取得 SOTA
- **启示**: 分层合并 + 上下文保留 是处理长文档的有效策略

#### RST-LoRA (2024, arxiv: 2405.00657)
- **核心思想**: 利用修辞结构理论（RST）来指导摘要
- **方法**: 用 LoRA 微调 LLM，让模型理解文档的修辞结构
- **结果**: 在长文档摘要上优于纯 LLM 方法
- **启示**: 文档的修辞/篇章结构对摘要质量很重要

#### Toward Unifying Text Segmentation and Long Document Summarization (2022, arxiv: 2210.16422)
- **核心思想**: 将文本分段和长文档摘要统一为一个任务
- **方法**: 联合学习分段和摘要
- **启示**: 好的分段是好的摘要的前提

#### Efficient Attentions for Long Document Summarization (2021, arxiv: 2104.02112)
- 比较了多种长注意力机制在长文档摘要中的效果
- 发现简单的注意力机制在长文档中表现不佳

---

### 3.3 分块策略方向

#### Adaptive Chunking (2026, arxiv: 2603.25333)
- **核心思想**: 动态选择最优分块方法
- **方法**: 根据文档特征（类型、长度、结构）自动选择分块策略
- **结果**: 自适应分块优于固定策略
- **启示**: 不同文档可能需要不同的分块策略

---

### 3.4 中文文档处理特殊挑战

#### Benchmarking Chinese Text Recognition (2021, arxiv: 2112.15093)
- 中文 OCR 的系统性 benchmark
- 发现：中文文本识别在复杂布局下仍有较大提升空间

#### 中文文档处理的特殊挑战：

1. **分词问题**: 中文没有天然的词边界，按"词"分割比英文困难
2. **Token 效率**: 中文在大多数 LLM 的 tokenizer 中，每个汉字占 1-3 个 token（智谱的 tokenizer 每个汉字约 1-2 token），比英文的 1 token/词更贵
3. **文档结构多样性**: 中文 PDF 格式不规范的情况比英文更多（扫描件、图片 PDF 更多）
4. **排版差异**: 中文竖排、古文、混合中英文等特殊情况
5. **缺乏中文 Benchmark**: 大多数长文档摘要 benchmark 以英文为主（BookSum, GovReport, PubMed, arXiv）

---

## 4. 推荐方案

### 4.1 场景分析

| 维度 | 我们的场景 |
|------|----------|
| 文档类型 | 中文 PDF（知乎长文、电子书、课程材料） |
| 文档长度 | 解析后 2-8 万汉字 |
| 输出需求 | 结构化 JSON（一句话摘要、要点、详细摘要、概念列表） |
| LLM | 智谱 glm-4-flash（128K 上下文，TPM 有限） |
| 核心约束 | TPM 限流（需要减少每次请求的 token 量） |
| 质量要求 | 知识点提取要完整，不能遗漏重要概念 |

### 4.2 推荐方案：分层摘要 + 语义分块 + 结构感知

**核心思路**：将 Hierarchical Summarization 与 Refine 的思想结合，形成"结构感知的分层精炼"方案。

#### 架构图

```
                    ┌──────────────┐
                    │  PDF 原文件   │
                    └──────┬───────┘
                           │
                    ┌──────▼───────┐
                    │ 文本提取     │  PyMuPDF / MinerU
                    │ + 结构检测   │  (标题/段落/列表)
                    └──────┬───────┘
                           │
              ┌────────────▼────────────┐
              │  结构感知分块            │
              │  (按标题/章节分割)      │
              │  每块 3000-5000 字      │
              └────────────┬────────────┘
                           │
              ┌────────────▼────────────┐
              │  第一层：段落摘要        │
              │  每块独立生成：         │
              │  - 本段要点             │
              │  - 提取的概念/知识点    │
              │  - 一句话概括           │
              │  [可并行]              │
              └────────────┬────────────┘
                           │
              ┌────────────▼────────────┐
              │  第二层：章节摘要        │
              │  合并同一章节下的段落摘要│
              │  Refine 模式：          │
              │  基于已有摘要精炼        │
              └────────────┬────────────┘
                           │
              ┌────────────▼────────────┐
              │  第三层：全局摘要        │
              │  合并所有章节摘要       │
              │  生成最终结构化 JSON    │
              └─────────────────────────┘
```

#### 为什么选这个方案

1. **解决 TPM 限流**：每层每次请求的 token 量可控（3000-8000 字 ≈ 4000-12000 tokens），不会触发限流
2. **保留文档结构**：按章节/标题分割，结构信息自然保留
3. **知识点不遗漏**：第一层就提取概念/知识点，即使后面合并时有损失，原始概念列表已保留
4. **可并行**：第一层段落摘要可并行处理，大幅提速
5. **质量高**：分层处理确保信息逐层浓缩而非一步到位
6. **中文友好**：不依赖 token 级压缩（LLMLingua 在中文上效果不确定）

---

### 4.3 与其他方案的对比

| 方案 | TPM友好 | 信息保真 | 速度 | 实现复杂度 | 综合评分 |
|------|---------|---------|------|-----------|---------|
| **推荐方案(分层+精炼)** | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | **最佳** |
| 纯 Map-Reduce | ⭐⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | 质量不足 |
| 纯 Refine | ⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐ | ⭐⭐⭐⭐ | TPM不友好 |
| LLMLingua 压缩后摘要 | ⭐⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | 中文效果不确定 |

---

## 5. 实施建议

### 5.1 分段策略

#### 5.1.1 优先按文档结构分段

```python
def structure_aware_split(text: str) -> list[dict]:
    """
    按文档结构分段，优先识别标题/章节
    
    返回: [{"title": "章节标题", "content": "正文", "level": 标题层级}]
    """
    # 1. 如果是 Markdown（MinerU 输出），按 # 标题分割
    # 2. 如果是纯文本，用正则识别可能的标题（全行大写、数字编号等）
    # 3. 如果检测不到结构，回退到语义分块
```

#### 5.1.2 语义分块（回退方案）

当文档没有明显结构时，使用语义分块：

```python
def semantic_chunk(text: str, chunk_size: int = 4000, 
                   overlap: int = 200) -> list[str]:
    """
    语义分块：在 chunk_size 附近找自然的断句点（段落、句号）
    
    - chunk_size: 目标字数（汉字数）
    - overlap: 重叠字数（只保留上一段的最后 200 字作为上下文）
    """
    # 1. 先按段落分割
    # 2. 合并段落直到接近 chunk_size
    # 3. 在最近的段落/句子边界处断开
    # 4. 重叠部分只作为"前文摘要"传入，不重复处理
```

#### 5.1.3 推荐的分段大小

| 参数 | 推荐值 | 说明 |
|------|-------|------|
| **段落层 chunk_size** | 3000-5000 汉字 | 约 4000-7000 tokens，确保单次请求不超限 |
| **overlap** | 200-500 汉字 | 提供上下文，避免边界信息丢失 |
| **章节层 chunk_size** | 合并 3-5 个段落摘要 | 约 5000-10000 字 |
| **全局层** | 所有章节摘要 | 通常 < 10000 字 |

**为什么是 3000-5000 字？**
- glm-4-flash 128K 上下文，每次请求建议不超过 20K tokens（含输入输出）
- 5000 汉字 ≈ 7000-10000 tokens（智谱 tokenizer）
- 留 5000-10000 tokens 给 prompt 模板和输出
- 总计 < 20K tokens，安全余量充足

---

### 5.2 Prompt 设计

#### 5.2.1 第一层 Prompt（段落摘要 + 知识点提取）

```python
PARAGRAPH_PROMPT = """你是一个知识提取专家。请从以下文档片段中提取信息。

## 文档上下文
{document_title}
{section_title}
{previous_summary}  <!-- 前一段摘要，提供上下文 -->

## 当前文档片段
{chunk_content}

请以 JSON 格式输出：
{{
  "one_line_summary": "一句话概括本段核心内容",
  "key_points": ["要点1", "要点2", "要点3"],
  "concepts": [
    {{"name": "概念名称", "definition": "概念定义", "importance": "high/medium/low"}}
  ],
  "detailed_summary": "本段的详细摘要（200-300字）"
}}

注意：
- concepts 中只提取明确出现的专业概念/术语/知识点
- importance 基于本段中该概念被强调的程度
- 如果本段没有专业概念，concepts 可以为空数组"""
```

#### 5.2.2 第二层 Prompt（章节摘要合并）

```python
SECTION_MERGE_PROMPT = """你是一个文档摘要专家。请将以下段落摘要合并为章节摘要。

## 文档信息
{document_title}
## 本章标题
{section_title}

## 段落摘要列表
{paragraph_summaries}

请以 JSON 格式输出：
{{
  "one_line_summary": "本章一句话概括",
  "key_points": ["本章核心要点"],
  "concepts": [
    {{"name": "概念名称", "definition": "定义", "importance": "high/medium/low"}}
  ],
  "detailed_summary": "本章详细摘要（300-500字）"
}}

注意：
- 合并段落摘要时，保留所有重要概念
- 去除重复内容
- concepts 列表应包含所有段落中提取的概念"""
```

#### 5.2.3 第三层 Prompt（全局摘要）

```python
GLOBAL_SUMMARY_PROMPT = """你是一个文档摘要专家。请根据以下章节摘要生成全文摘要。

## 文档信息
标题：{document_title}

## 章节摘要列表
{section_summaries}

请以 JSON 格式输出：
{{
  "one_line_summary": "全文一句话概括",
  "key_points": ["全文核心要点（5-10条）"],
  "concepts": [
    {{"name": "概念名称", "definition": "定义", "importance": "high/medium/low"}}
  ],
  "detailed_summary": "全文详细摘要（500-1000字）",
  "structure": {{
    "main_topics": ["主要主题1", "主要主题2"],
    "logic_flow": "文档的逻辑脉络简述"
  }}
}}

注意：
- concepts 应包含所有高重要性的概念
- key_points 应覆盖各章节的核心内容
- detailed_summary 应连贯叙述，而非简单拼接"""
```

---

### 5.3 代码架构

```
knowledge_base/
├── pdf_processor/
│   ├── __init__.py
│   ├── extractor.py          # PDF 文本提取（PyMuPDF/MinerU）
│   ├── splitter.py           # 结构感知分块
│   ├── summarizer.py         # 分层摘要核心逻辑
│   ├── prompts.py            # Prompt 模板
│   └── models.py             # 数据模型（Pydantic）
├── config.py                 # 配置（chunk_size, overlap, 并发数等）
└── main.py                   # 入口
```

#### 5.3.1 核心代码框架

```python
import asyncio
from dataclasses import dataclass
from typing import Optional

@dataclass
class ChunkResult:
    """第一层段落摘要结果"""
    one_line_summary: str
    key_points: list[str]
    concepts: list[dict]
    detailed_summary: str
    chunk_index: int

@dataclass
class SectionResult:
    """第二层章节摘要结果"""
    one_line_summary: str
    key_points: list[str]
    concepts: list[dict]
    detailed_summary: str
    section_title: str

@dataclass
class DocumentResult:
    """第三层全局摘要结果"""
    one_line_summary: str
    key_points: list[str]
    concepts: list[dict]
    detailed_summary: str
    structure: dict


class HierarchicalSummarizer:
    def __init__(self, llm_client, config):
        self.llm = llm_client
        self.config = config  # chunk_size=4000, overlap=300, max_concurrent=3
    
    async def process(self, text: str, title: str = "") -> DocumentResult:
        """处理完整文档"""
        
        # Step 1: 结构感知分块
        chunks = self.split_document(text)
        
        # Step 2: 第一层 - 并行段落摘要
        chunk_results = await self.summarize_chunks(chunks, title)
        
        # Step 3: 按章节分组
        sections = self.group_by_section(chunk_results)
        
        # Step 4: 第二层 - 章节摘要（可并行）
        section_results = await self.merge_sections(sections, title)
        
        # Step 5: 第三层 - 全局摘要
        final_result = await self.global_summary(section_results, title)
        
        return final_result
    
    async def summarize_chunks(self, chunks, title):
        """第一层：并行处理每个 chunk"""
        semaphore = asyncio.Semaphore(self.config.max_concurrent)
        
        async def process_one(chunk):
            async with semaphore:
                return await self.llm.generate(PARAGRAPH_PROMPT.format(...))
        
        tasks = [process_one(c) for c in chunks]
        return await asyncio.gather(*tasks)
    
    def split_document(self, text: str) -> list[dict]:
        """结构感知分块"""
        # 1. 尝试检测 Markdown 标题结构
        # 2. 回退到段落分割
        # 3. 最后回退到固定长度分割
        ...
    
    def group_by_section(self, chunk_results):
        """按章节分组段落结果"""
        ...
```

---

### 5.4 并发与限流策略

```python
class RateLimitedLLM:
    """带限流的 LLM 客户端"""
    
    def __init__(self, api_key, tpm_limit=50000):
        self.tpm_limit = tpm_limit
        self.token_budget = tpm_limit  # 每分钟 token 预算
        self.lock = asyncio.Lock()
    
    async def generate(self, prompt: str) -> str:
        estimated_tokens = len(prompt) * 1.5  # 粗估
        
        async with self.lock:
            while self.token_budget < estimated_tokens:
                await asyncio.sleep(1)  # 等待预算恢复
            self.token_budget -= estimated_tokens
        
        # 启动后台定时器恢复预算
        # ...
        
        return await self._call_api(prompt)
```

**推荐配置**：
- 最大并发数：3-5（取决于 TPM 限制）
- 每个请求控制在 8000-15000 tokens（输入+输出）
- 第一层并行，第二层并行，第三层串行
- 加入指数退避重试（应对偶发 429）

---

### 5.5 降级策略

```
文档长度     策略
──────────────────────────────────────
< 1万字     直接全文摘要（单次请求）
1-3万字     Map-Reduce（一层）
3-8万字     分层摘要（推荐方案）
> 8万字     分层摘要 + 增加中间层
```

---

### 5.6 质量保障

1. **概念去重**：每层合并时，对 concepts 做去重（基于名称相似度）
2. **完整性检查**：最终检查 concepts 列表是否包含所有 high importance 概念
3. **JSON Schema 校验**：每层输出都做 JSON schema 校验，失败则重试
4. **保留原始段落摘要**：即使最终摘要丢失了某些细节，第一层的段落摘要仍保留了完整信息
5. **增量更新**：如果只需要更新某个章节，可以只重新处理该章节的段落

---

### 5.7 成本估算

以一个 5 万汉字的文档为例：

| 阶段 | 请求数 | 每次输入 tokens | 每次输出 tokens | 总输入 tokens |
|------|-------|----------------|----------------|-------------|
| 分块 | - | - | - | - |
| 第一层 (12 chunks) | 12 | ~6,000 | ~1,000 | 72,000 |
| 第二层 (3 sections) | 3 | ~4,000 | ~800 | 12,000 |
| 第三层 (全局) | 1 | ~3,000 | ~1,500 | 3,000 |
| **总计** | **16** | - | - | **~87,000** |

对比直接全文处理：
- 一次请求：50,000 汉字 ≈ 75,000-100,000 tokens 输入 + ~3,000 tokens 输出
- **总输入 tokens 相当**，但：
  - 每次请求 token 量小，不会触发 TPM 限流
  - 第一层可并行，总耗时 ≈ 12次 / 并发数 + 3次 + 1次
  - 信息保真度更高

---

## 附录：技术选型建议

| 环节 | 推荐工具 | 备选 |
|------|---------|------|
| PDF文本提取 | **PyMuPDF** (文本PDF) / **MinerU** (复杂PDF) | pdfplumber |
| 扫描件OCR | **PaddleOCR** | Surya |
| 分块 | **自研结构感知分块** | LangChain RecursiveCharacterTextSplitter |
| 摘要 | **自研分层摘要** (本文推荐方案) | LangChain load_summarize_chain |
| LLM调用 | **直接调智谱 API** + 异步并发 | LangChain LLM wrapper |
| JSON校验 | **Pydantic** | jsonschema |
| 并发控制 | **asyncio.Semaphore** + 限流器 | Celery (过重) |

---

## 参考资源

### 论文
1. LLMLingua: https://arxiv.org/abs/2310.05736
2. LongLLMLingua: https://arxiv.org/abs/2310.06839
3. LLMLingua-2: https://arxiv.org/abs/2403.12968
4. Context-Aware Hierarchical Merging: https://arxiv.org/abs/2502.00977
5. RST-LoRA: https://arxiv.org/abs/2405.00657
6. PCToolkit: https://arxiv.org/abs/2403.17411
7. Adaptive Chunking: https://arxiv.org/abs/2603.25333
8. Characterizing Prompt Compression: https://arxiv.org/abs/2407.08892

### 开源项目
1. LangChain: https://github.com/langchain-ai/langchain
2. LlamaIndex: https://github.com/run-llama/llama_index
3. MinerU: https://github.com/opendatalab/MinerU
4. PyMuPDF: https://github.com/pymupdf/PyMuPDF
5. marker: https://github.com/VikParuchuri/marker
6. PaddleOCR: https://github.com/PaddlePaddle/PaddleOCR
7. LLMLingua: https://github.com/microsoft/LLMLingua
8. Unstructured: https://github.com/Unstructured-IO/unstructured

---

> **结论**：对于我们的场景（中文 PDF、知识点提取、TPM 有限），推荐采用**结构感知的分层精炼方案**，结合 PyMuPDF/MinerU 做文本提取，自研分块和摘要逻辑。该方案在信息保真度、TPM 友好性和实现复杂度之间取得了最佳平衡。
