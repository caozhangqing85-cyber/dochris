"""CLI 命令：配置、版本"""

import argparse
from pathlib import Path

from dochris.cli.cli_utils import bold, dim, error, info, success
from dochris.settings import get_settings


def _find_env_file() -> Path | None:
    """查找 .env 文件路径"""
    env_paths = [
        Path.cwd() / ".env",
        Path.home() / ".knowledge-base" / ".env",
        Path.home() / ".openclaw" / "knowledge-base" / ".env",
    ]
    # 也检查 WORKSPACE 环境变量
    import os

    workspace = os.environ.get("WORKSPACE")
    if workspace:
        env_paths.insert(0, Path(workspace).expanduser() / ".env")

    for p in env_paths:
        if p.exists():
            return p
    return None


def _read_env_file(env_path: Path) -> dict[str, str]:
    """读取 .env 文件，返回 key-value 字典"""
    env_vars: dict[str, str] = {}
    if not env_path.exists():
        return env_vars
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            key, _, value = line.partition("=")
            env_vars[key.strip()] = value.strip()
    return env_vars


def _write_env_file(env_path: Path, env_vars: dict[str, str]) -> None:
    """写入 .env 文件"""
    env_path.parent.mkdir(parents=True, exist_ok=True)
    lines = []
    # 保留注释和空行
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                lines.append(line)
            elif "=" in stripped:
                key = stripped.split("=", 1)[0].strip()
                if key in env_vars:
                    lines.append(f"{key}={env_vars[key]}")
                    del env_vars[key]
                else:
                    lines.append(line)
            else:
                lines.append(line)
    # 添加新 key
    for key, value in env_vars.items():
        lines.append(f"{key}={value}")
    env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def cmd_config(args: argparse.Namespace) -> int:
    """配置管理（支持子命令 set/get/默认显示）"""
    config_command = getattr(args, "config_command", None)

    if config_command == "set":
        return _cmd_config_set(args)
    elif config_command == "get":
        return _cmd_config_get(args)
    else:
        return _cmd_config_show(args)


def _cmd_config_show(args: argparse.Namespace) -> int:
    """显示当前配置"""
    print(f"\n{info('知识库配置')}")
    print(f"{'=' * 40}")

    _s = get_settings()
    print(f"\n{bold('路径配置:')}")
    print(f"  工作区: {_s.workspace}")
    print(f"  日志目录: {_s.logs_dir}")
    print(f"  Wiki 目录: {_s.wiki_dir}")
    print(f"  输出目录: {_s.outputs_dir}")

    print(f"\n{bold('源配置:')}")
    print(f"  主源目录: {_s.source_path or dim('未配置')}")
    print(f"  Obsidian Vaults: {len(_s.obsidian_vaults) if _s.obsidian_vaults else 0} 个")
    if _s.obsidian_vaults:
        print(f"    主 Vault: {_s.obsidian_vaults[0]}")

    print(f"\n{bold('API 配置:')}")
    if _s.api_key:
        masked = f"...{_s.api_key[-6:]}" if len(_s.api_key) > 6 else "***"
        print(f"  API Key: {success('已配置')} ({masked})")
    else:
        print(f"  API Key: {error('未配置')}")
    print(f"  Base URL: {_s.api_base}")
    print(f"  模型: {_s.model}")

    print(f"\n{bold('编译配置:')}")
    print(f"  并发数: {_s.max_concurrency}")
    print(f"  质量门槛: {_s.min_quality_score}")
    print(f"  最大内容: {_s.max_content_chars} 字符")

    print()
    return 0


def _cmd_config_set(args: argparse.Namespace) -> int:
    """设置配置项"""

    # 获取剩余参数（set KEY VALUE）
    # argparse subparser 不会自动处理位置参数，需要从 sys.argv 中提取
    key = getattr(args, "key", None)
    value = getattr(args, "value", None)

    if not key or not value:
        print(f"\n{error('✗ 用法: kb config set <KEY> <VALUE>')}")
        return 1

    env_path = _find_env_file()
    if env_path is None:
        # 创建默认位置
        import os

        workspace = os.environ.get("WORKSPACE", str(Path.cwd()))
        env_path = Path(workspace).expanduser() / ".env"

    env_vars = _read_env_file(env_path)
    env_vars[key] = value
    _write_env_file(env_path, env_vars)

    print(f"{success(f'✓ 已设置 {key}={value}')}")
    print(f"  配置文件: {env_path}")
    print(f"{dim('💡 重新运行命令后生效')}")
    return 0


def _cmd_config_get(args: argparse.Namespace) -> int:
    """查看单个配置项"""

    key = getattr(args, "key", None)
    if not key:
        print(f"\n{error('✗ 用法: kb config get <KEY>')}")
        return 1

    _s = get_settings()
    # 尝试从 settings 对象获取属性
    value = getattr(_s, key, None)
    if value is None:
        # 尝试小写
        value = getattr(_s, key.lower(), None)

    if value is not None:
        print(f"{key} = {value}")
    else:
        # 尝试从环境变量获取
        import os

        env_val = os.environ.get(key)
        if env_val:
            print(f"{key} = {env_val}")
        else:
            print(f"{error(f'✗ 未找到配置项: {key}')}")
            print(f"{dim('💡 运行 kb config 查看所有可用配置')}")
            return 1
    return 0


def cmd_version(args: argparse.Namespace) -> int:
    """显示版本"""
    from dochris import __version__

    print(f"\n知识库编译系统 v{__version__}")
    print("统一 CLI 入口")
    print()
    return 0
