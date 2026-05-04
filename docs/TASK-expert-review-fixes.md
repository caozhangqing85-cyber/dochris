# Claude Code 优化任务 — 基于专家论坛评审

> 评审日期：2026-05-04 | 6位专家评审 | 综合评分 C
> 执行规则：按 Step 顺序执行，每个 Step 完成后运行验证。所有修改必须通过 ruff check。

---

## Step 1: 安全修复 — API Key 常数时间比较

**文件**: `src/dochris/api/auth.py`

**当前问题**: `client_key != api_key` 使用 Python `!=` 比较，存在时序侧信道攻击风险。攻击者可逐字符爆破 API Key。

**修复要求**:
- 使用 `hmac.compare_digest()` 进行常数时间比较
- 保持向后兼容：DOCHRIS_API_KEY 为空时跳过认证（开发模式）
- 添加前缀检查优化：如果长度不同直接返回 False（不需要常数时间）
- 保持现有函数签名和返回类型不变

**验证**: `python -c "from dochris.api.auth import verify_api_key; print('OK')"`

---

## Step 2: 安全修复 — CORS 收紧

**文件**: `src/dochris/api/app.py`

**当前问题**: `allow_methods=["*"]` 和 `allow_headers=["*"]` 过于宽松。

**修复要求**:
- `allow_methods` 改为 `["GET", "POST", "PUT", "DELETE", "OPTIONS"]`
- `allow_headers` 改为 `["Authorization", "Content-Type", "X-API-Key"]`
- 保持现有的 `allow_origins` 从环境变量读取的逻辑不变
- `allow_credentials=True` 保持不变（API Key 认证需要）

**验证**: `python -c "from dochris.api.app import create_app; print('OK')"`

---

## Step 3: 性能修复 — httpx 连接池扩大

**文件**: `src/dochris/llm/openai_compat.py` 第62行

**当前问题**: `httpx.Limits(max_connections=1)` 导致所有 LLM 请求串行执行，`max_concurrency=3` 配置形同虚设。全量编译时间 ~7.4 小时。

**修复要求**:
- `max_connections` 从 1 改为 20
- 添加 `max_keepalive_connections=10`
- 在修改行上方添加注释说明原因（引用性能评审）

**验证**: `python -c "from dochris.llm.openai_compat import OpenAICompatProvider; print('OK')"`

---

## Step 4: 代码质量 — 消除 P0 DRY 违规（sanitize 函数统一）

**涉及文件**:
- `src/dochris/compensate/compensate_failures.py`
- `src/dochris/compensate/compensate_extractors.py`
- `src/dochris/admin/recompile_missing_concepts.py`
- `src/dochris/admin/sanitize_sensitive_words.py`

**当前问题**: `sanitize_filename`, `should_skip_file`, `sanitize_prompt`, `sanitize_pdf_content` 等函数在 4 个文件中有重复实现。

**修复要求**:
1. 检查 `src/dochris/core/utils.py` 中是否已有 `sanitize_filename()` 函数
2. 如果有，确认其实现是否完善（处理路径遍历、特殊字符等）
3. 在 `core/utils.py` 中添加缺失的 sanitize 函数（如果需要）
4. 将 4 个文件中的重复 sanitize 函数替换为从 `core/utils.py` 的 import
5. 确保所有原有调用点行为不变

**验证**: 
- `ruff check src/dochris/core/utils.py src/dochris/compensate/ src/dochris/admin/`
- `python -c "from dochris.core.utils import sanitize_filename; print('OK')"`

---

## Step 5: 代码质量 — 消除 extract_text_from_file 重复

**涉及文件**:
- `src/dochris/compensate/compensate_extractors.py`
- `src/dochris/compensate/compensate_failures.py`

**当前问题**: `extract_text_from_file()` 函数在两个文件中几乎逐行相同（约80行）。

**修复要求**:
1. 对比两个文件中的 `extract_text_from_file()` 实现，确认差异
2. 如果功能完全相同，删除 `compensate_failures.py` 中的副本，改为 `from dochris.compensate.compensate_extractors import extract_text_from_file`
3. 如果有细微差异，合并为一个函数（放在 `compensate_extractors.py` 中），通过参数区分行为
4. 更新所有调用点

**验证**: `python -c "from dochris.compensate.compensate_extractors import extract_text_from_file; print('OK')"`

---

## Step 6: 代码质量 — batch_promote.py 三段重复逻辑统一

**文件**: `src/dochris/admin/batch_promote.py`

**当前问题**: 文件中有三段几乎相同的过滤→排序→遍历→统计逻辑（约57-101行, 131-175行, 213-267行）。

**修复要求**:
1. 提取一个通用函数 `_batch_promote(target_layer, manifests, ...)` 
2. 三段重复逻辑改为调用这个通用函数
3. 保持所有原有功能和行为不变
4. 函数签名设计要合理，通过参数区分不同的目标层

**验证**: `python -c "from dochris.admin.batch_promote import main; print('OK')"`

---

## Step 7: 代码质量 — 收紧异常捕获

**涉及文件**: 全项目范围（53处 `except Exception`）

**修复要求**:
1. 首先读取 `src/dochris/exceptions.py`，了解已定义的自定义异常类
2. 重点修复以下文件中的宽泛异常捕获：
   - `src/dochris/compensate/compensate_failures.py` (5处)
   - `src/dochris/compensate/compensate_extractors.py` (3处)
   - `src/dochris/web/app.py` (12处)
   - `src/dochris/core/llm_client.py` (1处静默吞掉异常)
3. 将 `except Exception as e` 替换为更具体的异常类型（如 `OSError`, `json.JSONDecodeError`, `TextExtractionError` 等）
4. 对于确实需要捕获所有异常的守卫位置（如顶层事件处理器），保持 `except Exception` 但添加注释说明原因
5. **不要修改 `except Exception` 如果没有合适的更具体类型**，宁可不改也不要改错

**验证**: `ruff check src/dochris/`

---

## Step 8: 代码质量 — 修复 httpx 延迟导入

**文件**: `src/dochris/core/llm_client.py`

**当前问题**: `import httpx` 在方法内部（约第151行和第186行），但该模块顶层已导入 httpx，属于无意义的延迟导入。

**修复要求**:
1. 检查文件顶部的 import 列表
2. 如果 httpx 已在顶部导入，删除方法内部的重复导入
3. 如果顶部未导入，将 import 移到顶部

**验证**: `ruff check src/dochris/core/llm_client.py`

---

## Step 9: 运行完整验证

完成所有修改后，运行以下验证：

```bash
# 1. ruff lint 检查
python -m ruff check src/dochris/

# 2. 运行相关测试
python -m pytest tests/test_api/ tests/test_quality_scorer.py tests/test_coverage_boost_v4.py -v --tb=short

# 3. 导入检查
python -c "from dochris.api.app import create_app; from dochris.llm.openai_compat import OpenAICompatProvider; from dochris.core.utils import sanitize_filename; from dochris.compensate.compensate_extractors import extract_text_from_file; print('ALL OK')"
```

如果任何测试失败，修复后重新运行。**不要跳过失败的测试**。

---

## 重要约束

1. **不要修改任何函数的公开签名和返回类型**（除非 Step 1 中明确要求）
2. **不要修改 pyproject.toml 或依赖版本**（setuptools 升级等由 Nomi 单独处理）
3. **所有修改必须通过 ruff check**
4. **每个 Step 独立可验证**，不要留半成品
5. **中文注释**，代码风格与项目现有风格保持一致
