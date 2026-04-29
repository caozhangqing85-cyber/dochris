---
name: kb-query
description: Search the knowledge base using semantic search. Use when user wants to find information, concepts, or documents.
argument-hint: "<query> [--limit N] [--layer L0|L1|L2]"
allowed-tools: Bash(python3:*), Read, Glob, Grep
---

# Knowledge Base Query

Search compiled knowledge using semantic vector search.

## Steps

1. Run query:
   ```bash
   cd ~/.openclaw/knowledge-base
   ~/.openclaw/vector_env/bin/python scripts/phase3_query.py "$QUERY" --limit $LIMIT
   ```

2. If vector DB not available, fallback to grep:
   ```bash
   cd ~/.openclaw/knowledge-base
   grep -rl "$QUERY" outputs/ wiki/ curated/ 2>/dev/null | head -10
   ```

3. Present results with:
   - Source file name
   - Relevance score (if available)
   - Key matching excerpts
