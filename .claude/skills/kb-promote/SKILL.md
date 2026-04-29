---
name: kb-promote
description: Promote knowledge items between trust layers. Use when user wants to promote items from outputs to wiki, or wiki to curated.
argument-hint: "<source-id> --to <target-layer>"
allowed-tools: Bash(python3:*), Read, Write, Glob, Grep
---

# Knowledge Base Promote

Move knowledge items through trust layers (L0→L1→L2→L3).

## Steps

1. Check item status:
   ```bash
   cd ~/.openclaw/knowledge-base
   ~/.openclaw/vector_env/bin/python scripts/promote_artifact.py info $SOURCE_ID
   ```

2. Verify quality score meets threshold (≥85 for wiki, ≥90 for curated)

3. Promote:
   ```bash
   cd ~/.openclaw/knowledge-base
   ~/.openclaw/vector_env/bin/python scripts/promote_artifact.py promote $SOURCE_ID --to $TARGET
   ```

4. For batch promote:
   ```bash
   cd ~/.openclaw/knowledge-base
   ~/.openclaw/vector_env/bin/python scripts/batch_promote.py --from outputs --to wiki --min-score 85
   ```

## Trust Layers
- L0 (outputs/): LLM generated, untrusted
- L1 (wiki/): Quality-gated (≥85), semi-trusted
- L2 (curated/): Human curated, trusted
- L3 (locked/): Immutable
