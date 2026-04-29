---
description: Run code review on the knowledge-base project
argument-hint: "[file-or-directory]"
---

Perform a thorough code review on the specified file or directory (default: entire project).

Focus on:
1. Code quality (type annotations, docstrings, bare except)
2. Security (no hardcoded secrets, path traversal)
3. Configuration consistency (imports from config.py)
4. Test coverage (check if tests exist for modified code)

Output a structured report with severity levels (🔴/🟡/🟢) and specific fix suggestions.
