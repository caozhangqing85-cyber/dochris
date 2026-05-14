"""Root conftest.py - ensures 'dochris' is importable even if editable install .pth is broken."""
import os
import sys
from pathlib import Path

# Add src/ to sys.path so `import dochris` works without a proper editable install
_src = str(Path(__file__).parent / "src")
if _src not in sys.path:
    sys.path.insert(0, _src)

# 允许测试环境中的交互式提示（覆盖 sys.stdin.isatty() 检查）
os.environ.setdefault("DOCHRIS_ALLOW_PROMPT", "1")
