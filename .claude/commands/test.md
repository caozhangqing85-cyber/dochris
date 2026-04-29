---
description: Run tests and fix failures
argument-hint: "[test-file-pattern]"
---

Run the test suite and fix any failures:

1. Run: `~/.openclaw/vector_env/bin/python -m pytest tests/ -v --tb=short`
2. If tests fail, analyze the error and fix the test or source code
3. Re-run until all tests pass
4. Report the final results
