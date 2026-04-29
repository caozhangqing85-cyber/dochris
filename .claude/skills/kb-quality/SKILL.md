---
name: kb-quality
description: Check and report knowledge base quality scores. Use when user wants to review quality, find low-scoring items, or check for pollution.
argument-hint: "[--report] [--threshold N]"
allowed-tools: Bash(python3:*), Read, Glob, Grep
---

# Knowledge Base Quality Check

Analyze quality scores across compiled knowledge items.

## Steps

1. Run quality gate check:
   ```bash
   cd ~/.openclaw/knowledge-base
   ~/.openclaw/vector_env/bin/python scripts/quality_gate.py check --report
   ```

2. If quality_gate.py doesn't support --report, manually analyze:
   ```bash
   cd ~/.openclaw/knowledge-base
   find outputs/ -name "*.json" -exec grep -l "quality_score" {} \;
   ```

3. Report:
   - Total compiled items
   - Average quality score
   - Items below threshold (default: 85)
   - Pollution detection results
