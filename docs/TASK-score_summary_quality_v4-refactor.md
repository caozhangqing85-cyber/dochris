# 🔧 任务：`score_summary_quality_v4` 全面重构

> 来源：Nomi 专家圆桌审查（架构师 + 测试工程师 + 安全专家）
> 日期：2026-05-04
> 优先级：P0（项目最高复杂度函数，复杂度 52/F 级）

---

## 背景

`src/dochris/core/quality_scorer.py` 中的 `score_summary_quality_v4` 函数是整个项目的质量评分核心，当前存在以下问题：

1. **圈复杂度 52（F 级）**：170 行平铺在一个函数中
2. **评分体系设计缺陷**：理论最高分 140 > 声明的 100
3. **关键词重叠**：INFO_KEYWORDS 15 个全部包含在 LEARNING_KEYWORDS 中（100% 重叠）
4. **测试精度不足**：one_line 测试为空壳，多个维度无精确测试
5. **阈值源不一致**：`get_quality_threshold()` 硬编码 85，未使用 settings

---

## 执行步骤（按顺序）

### Step 1：安全修复（不改结构，先修评分逻辑）

#### 1.1 修复 `get_quality_threshold()`
```python
# 当前（硬编码）：
def get_quality_threshold() -> int:
    return 85

# 修改为：
def get_quality_threshold() -> int:
    return get_settings().min_quality_score
```

#### 1.2 修复 LEARNING_KEYWORDS 重复
- 检查 `constants.py` 中 `LEARNING_KEYWORDS` 列表，去除重复的 `"运用"`（出现两次）

#### 1.3 修复 INFO_KEYWORDS 与 LEARNING_KEYWORDS 重叠
- 当前 INFO_KEYWORDS 的 15 个词全部包含在 LEARNING_KEYWORDS 中
- **替换 INFO_KEYWORDS** 为独立的、不与 LEARNING_KEYWORDS 重叠的技术/工具类词汇，例如：
  ```python
  INFO_KEYWORDS = [
      "工具", "框架", "API", "SDK", "算法", "架构", "协议",
      "数据库", "缓存", "容器", "微服务", "中间件", "配置",
      "部署", "监控"
  ]
  ```
- 注意：替换后要确保测试仍然通过，如果测试依赖了具体关键词需要同步更新

#### 1.4 修复 key_points / concepts 空串评分
- 在 `_score_key_points` 和 `_score_concepts` 中（或当前函数对应位置），过滤空字符串后再计数：
  ```python
  valid_kps = [kp for kp in key_points if isinstance(kp, str) and kp.strip()]
  # 用 len(valid_kps) 而不是 len(key_points) 计分
  ```

#### 1.5 添加超长文本惩罚
- `detailed_summary` 超过 3000 字时扣分：
  ```python
  if len(detailed_summary) > 3000:
      points -= min(10, (len(detailed_summary) - 3000) // 500)  # 每 500 字扣 1 分，最多扣 10
  ```

#### 1.6 重新分配评分权重使理论最大值 = 100
当前：35+40+25+10+10+20 = 140
建议调整为：
```
detailed_summary 长度:  25  (原 35)
key_points 完整性:       30  (原 40)
学习价值:               15  (原 25)
信息密度:                5  (原 10)
one_line 质量:           5  (原 10)
concepts 完整性:        10  (原 20)
                      ----
合计:                   90  + 模板扣分空间 10
```

> ⚠️ **重要**：修改权重后必须运行全量测试，对比修改前后的分数变化，确保不会导致大量已编译文档突然不达标。如果影响面太大，可以先只调整关键词重叠问题，权重调整放到后续版本。

---

### Step 2：结构重构（拆分函数）

#### 2.1 提取工具函数
```python
def _safe_str(value: Any) -> str:
    """防御性字符串提取"""
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    return str(value) if value else ""

def _safe_list(value: Any) -> list:
    """防御性列表提取"""
    if value is None:
        return []
    if isinstance(value, list):
        return value
    logger.warning(f"Expected list, got {type(value).__name__}, converting")
    return []

def _tiered_score(value: int, tiers: list[tuple[int, int]], default: int = 0) -> int:
    """通用阶梯式分段评分。tiers 从高到低排列 [(阈值, 分数), ...]"""
    for threshold, points in tiers:
        if value >= threshold:
            return points
    return default
```

#### 2.2 新增数据结构
```python
from dataclasses import dataclass

@dataclass(frozen=True)
class DimensionScore:
    """单个维度的评分结果"""
    name: str
    points: int
    max_points: int
    detail: str

@dataclass
class QualityReport:
    """质量评分完整报告"""
    total: int
    dimensions: list[DimensionScore]
    template_detected: bool
```

#### 2.3 拆分为 7 个维度子函数（全部 private）
每个子函数返回 `DimensionScore`，复杂度 ≤ 3：

| 子函数 | 职责 | 最大分值 |
|--------|------|---------|
| `_score_detail_length(ds: str)` | 文本长度评分 | 25 |
| `_score_key_points(kp: list)` | 关键点数量评分 | 30 |
| `_score_learning_value(text: str)` | 学习价值关键词 | 15 |
| `_score_info_density(text: str)` | 信息密度关键词 | 5 |
| `_score_one_line(text: str)` | 单行摘要质量 | 5 |
| `_score_concepts(concepts: list)` | 概念完整性 | 10 |
| `_detect_template(text: str)` | 模板检测 | -10 |

#### 2.4 重写主函数为 facade
```python
def score_summary_quality_v4(summary: dict[str, Any] | None) -> int:
    """签名完全不变，调用者零改动"""
    if not isinstance(summary, dict):
        return 0
    
    ds = _safe_str(summary.get("detailed_summary"))
    ds_lower = ds.lower()
    
    dimensions = [
        _score_detail_length(ds),
        _score_key_points(_safe_list(summary.get("key_points"))),
        _score_learning_value(ds_lower),
        _score_info_density(ds_lower),
        _score_one_line(_safe_str(summary.get("one_line"))),
        _score_concepts(_safe_list(summary.get("concepts"))),
        _detect_template(ds_lower),
    ]
    
    total = max(0, min(sum(d.points for d in dimensions), 100))
    _log_quality_result(summary, total, dimensions)
    return total
```

#### 2.5 新增带报告的版本
```python
def score_summary_quality_v4_report(
    summary: dict[str, Any] | None,
) -> QualityReport:
    """返回评分明细，供 API/Web UI 使用"""
    # 实现同上，但返回 QualityReport 对象
```

---

### Step 3：测试重写

#### 3.1 修复空壳测试
- `test_one_line_quality_scoring` 函数体为空，必须补充实际断言

#### 3.2 重写为精确断言
- 将所有 `assert result >= base_score + expected - 5` 改为精确断言 `assert result == expected`
- 使用 `@pytest.mark.parametrize` 覆盖每个阈值档位

#### 3.3 为每个子函数新增精确测试
```
tests/test_quality_scorer/
├── test_score_detail_length.py      # ~10 用例，参数化
├── test_score_key_points.py         # ~8 用例
├── test_score_learning_value.py     # ~10 用例（6 个阈值 + 边界）
├── test_score_info_density.py       # ~6 用例
├── test_score_one_line.py           # ~8 用例（修复空壳 + 补充）
├── test_score_concepts.py           # ~8 用例
├── test_template_detection.py       # ~8 用例
├── test_score_combination.py        # 集成测试，保留原有
└── test_quality_threshold.py        # 阈值测试
```

#### 3.4 保留不动的测试
- `test_phase2.py` — 集成测试
- `test_integration_v2.py` — 集成测试
- 这些只通过公共 API 调用，不受重构影响

---

### Step 4：验证

```bash
# 1. 运行全量测试
~/.openclaw/vector_env/bin/python -m pytest tests/ -v --tb=short

# 2. 检查覆盖率
~/.openclaw/vector_env/bin/python -m pytest tests/ --cov=dochris --cov-report=term-missing

# 3. 确认复杂度降低
~/.openclaw/vector_env/bin/python -m radon cc src/dochris/core/quality_scorer.py -s

# 4. Ruff 检查
~/.openclaw/vector_env/bin/python -m ruff check src/dochris/core/quality_scorer.py
```

---

## 约束条件

1. **`score_summary_quality_v4` 签名和返回值类型（int）不能变** — 3 个调用者依赖它
2. **`get_quality_threshold()` 仍然返回 int** — quality_gate.py 依赖它
3. **所有修改必须通过 ruff 检查** — 项目零 lint 容忍
4. **测试不能降低覆盖率** — 当前 78.94%
5. **先跑 baseline 测试记录分数，修改后对比** — 确保不会导致大量文档降级

## 调用者列表（不可破坏）

| 调用者 | 导入方式 |
|--------|---------|
| `workers/compiler_worker.py:220` | `from dochris.core.quality_scorer import score_summary_quality_v4` |
| `admin/recompile_missing_concepts.py:322` | 同上 |
| `compensate/compensate_failures.py:71` | `from dochris.core.quality_scorer import score_summary_quality_v4 as score_summary_quality` |
| `core/__init__.py` | 导出 `score_summary_quality_v4` |
