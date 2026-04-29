---
description: Code standards for the knowledge-base project
globs: scripts/**/*.py
---

When editing Python files in this project, follow these standards:

1. **Type annotations**: All public functions must have parameter and return type hints
2. **Docstrings**: All public functions and modules must have docstrings
3. **Exceptions**: Use specific types from `scripts/exceptions.py`, never bare `except:` or `except Exception: pass`
4. **Configuration**: Import from `scripts.config`, never hardcode paths or values
5. **Logging**: Use `logging.getLogger(__name__)`, never `print()`
6. **Paths**: Always use `pathlib.Path`, never string concatenation
7. **Encoding**: Always specify `encoding='utf-8'` for file operations
