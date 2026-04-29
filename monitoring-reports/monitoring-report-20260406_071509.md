# PDF 编译质量监控报告

**时间**: 2026-04-06 07:15

## 1. 进程状态

- **运行进程数**: 2

- PID 1576563: CPU 0.0%, 内存 1588 KB (0.0)
- PID 1576564: CPU 13.8%, 内存 937792 KB (5.7)

## 2. 编译进度

- **已编译**: 4 个
- **成功**: 4 个
- **失败**: 0 个
- **跳过**: 0 个
- **成功率**: 100.0%

## 3. JSON 解析错误率

- **JSON 解析错误**: 1 次
- **错误率**: 25.0%

### 最近的 JSON 解析错误

- JSON parse failed with strict=False: Expecting property name enclosed in double quotes: line 2 column 76 (char 77)

## 4. 编译速度

### 最近 10 次编译

- 编译: AGENTS.md
- 编译: SKILL_1_2_3_4_5_6_7_8_9_10_11_12_13_14_15_16.md
- 编译: agent-reach-install.md
- 编译: grok.md
- 编译: 知乎减肥文章可信度分析报告.md

## 5. 摘要质量

- **短摘要（<600 字）**: 71 个
- **总摘要数**: 272 个
- **短摘要率**: 26.1%

## 6. 告警状态

- 🔴 **告警**: JSON 解析错误率过高 (25.0%)
- 🔴 **告警**: 多个进程同时运行 (2 个)
- 🟡 **警告**: 短摘要数量过多 (71 个)

## 7. 建议和下一步

1. **JSON 解析优化**
   - json-repair 库已安装，应该会自动修复部分错误
   - 考虑优化 Prompt，要求 LLM 严格输出合法 JSON

3. **质量提升**
   - 运行 `python3 scripts/phase2_compilation.py recompile-short` 重新编译短摘要
   - 增加 detailed_summary 的字数要求

---
报告生成时间: 2026-04-06 07:15:09.639372
日志文件: /home/admin/.openclaw/knowledge-base/logs/phase2_20260406_071003.log
