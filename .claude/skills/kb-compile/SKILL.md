---
name: kb-compile
description: Compile knowledge base files with LLM. Use when user wants to compile, process, or batch-convert source files.
argument-hint: "[--limit N] [--resume] [--model MODEL]"
allowed-tools: Bash(python3:*), Bash(pytest:*), Read, Write, Edit, Glob, Grep
---

# Knowledge Base Compilation

Run the Phase 2 compilation pipeline to convert source files into structured knowledge.

## Steps

1. Check current workspace and configuration:
   ```bash
   cd ~/.openclaw/knowledge-base
   ~/.openclaw/vector_env/bin/python scripts/config.py show
   ```

2. Run compilation (use --resume for incremental, --limit N for batch):
   ```bash
   cd ~/.openclaw/knowledge-base
   ~/.openclaw/vector_env/bin/python scripts/phase2_compilation.py --resume --limit $LIMIT
   ```

3. Check results:
   - Count compiled vs failed manifests
   - Report average quality score
   - List any errors

## Arguments
- `--limit N`: Process only N files (default: all)
- `--resume`: Continue from last checkpoint
- `--model MODEL`: Override compilation model
