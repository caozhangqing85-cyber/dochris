#!/usr/bin/env python3
"""
Workers 模块导入测试
"""


# 确保 scripts 目录在 sys.path

print("✓ Testing workers imports...")

try:
    from workers import compiler_worker

    print("✓ workers.compiler_worker")
    print(f"  - CompilerWorker: {hasattr(compiler_worker.CompilerWorker, '__init__')}")
except ImportError as e:
    print(f"✗ workers.compiler_worker: {e}")
    import traceback

    traceback.print_exc()

try:
    from workers import monitor_worker

    print("✓ workers.monitor_worker")
    print(f"  - MonitorWorker: {hasattr(monitor_worker.MonitorWorker, '__init__')}")
except ImportError as e:
    print(f"✗ workers.monitor_worker: {e}")
    import traceback

    traceback.print_exc()

print("\n✓ Workers import test completed!")
