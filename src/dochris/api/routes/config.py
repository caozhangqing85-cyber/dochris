"""配置路由 — GET/PUT /api/v1/config"""

from __future__ import annotations

import logging
import os
from pathlib import Path

from fastapi import APIRouter
from pydantic import BaseModel

from dochris.settings import get_settings

logger = logging.getLogger(__name__)
router = APIRouter(tags=["config"])


class ConfigResponse(BaseModel):
    api_base: str = ""
    api_key: str = ""
    model: str = ""
    query_model: str = ""
    llm_provider: str = "openai_compat"
    temperature: float = 0.1
    workspace: str = ""
    vector_store: str = "chromadb"


class ConfigUpdateRequest(BaseModel):
    api_base: str | None = None
    api_key: str | None = None
    model: str | None = None
    query_model: str | None = None
    llm_provider: str | None = None
    temperature: float | None = None
    workspace: str | None = None
    vector_store: str | None = None


def _mask_key(key: str) -> str:
    if len(key) >= 10:
        return f"{key[:6]}...{key[-4:]}"
    return "已配置" if key else ""


@router.get("/config", response_model=ConfigResponse)
async def get_config() -> ConfigResponse:
    """获取当前配置"""
    settings = get_settings()
    return ConfigResponse(
        api_base=settings.api_base,
        api_key=_mask_key(settings.api_key or ""),
        model=settings.model,
        query_model=settings.query_model,
        llm_provider=settings.llm_provider,
        temperature=settings.llm_temperature,
        workspace=str(settings.workspace),
        vector_store=settings.vector_store,
    )


@router.put("/config", response_model=ConfigResponse)
async def update_config(body: ConfigUpdateRequest) -> ConfigResponse:
    """更新配置到 .env 文件"""
    from dochris.settings.config import reset_settings

    settings = get_settings()
    updates: dict[str, str] = {}

    if body.api_base:
        updates["OPENAI_API_BASE"] = body.api_base
    if body.api_key and "..." not in body.api_key:
        updates["OPENAI_API_KEY"] = body.api_key
    if body.model:
        updates["MODEL"] = body.model
    if body.query_model:
        updates["QUERY_MODEL"] = body.query_model
    if body.llm_provider:
        updates["LLM_PROVIDER"] = body.llm_provider
    if body.vector_store:
        updates["VECTOR_STORE"] = body.vector_store
    if body.temperature is not None:
        updates["LLM_TEMPERATURE"] = str(body.temperature)
    if body.workspace:
        ws = str(Path(body.workspace).expanduser())
        updates["WORKSPACE"] = ws
        try:
            Path(ws).mkdir(parents=True, exist_ok=True)
        except OSError as e:
            logger.warning(f"无法创建工作区目录 {ws}: {e}")

    # 更新环境变量
    for key, value in updates.items():
        os.environ[key] = value

    # 写入 .env
    try:
        workspace = Path(body.workspace).expanduser() if body.workspace else settings.workspace
        env_path = workspace / ".env"
        env_path.parent.mkdir(parents=True, exist_ok=True)
        _write_env(env_path, updates)
    except OSError as e:
        logger.warning(f"无法写入 .env 文件: {e}")

    # 重置 Settings 单例
    reset_settings()

    # 清理 query_engine 缓存（LLM 客户端需要重新创建以使用新模型）
    from dochris.phases.query_engine import clear_caches

    clear_caches()
    try:
        new_settings = get_settings()
    except Exception as e:
        logger.warning(f"重置 Settings 失败，使用旧配置: {e}")
        new_settings = settings

    return ConfigResponse(
        api_base=new_settings.api_base,
        api_key=_mask_key(new_settings.api_key or ""),
        model=new_settings.model,
        query_model=new_settings.query_model,
        llm_provider=new_settings.llm_provider,
        temperature=new_settings.llm_temperature,
        workspace=str(new_settings.workspace),
        vector_store=new_settings.vector_store,
    )


def _write_env(env_path: Path, updates: dict[str, str]) -> None:
    """合并写入 .env 文件"""
    pending = dict(updates)
    lines: list[str] = []
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8", errors="ignore").splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                lines.append(line)
                continue
            if "=" in stripped:
                key = stripped.partition("=")[0].strip()
                if key in pending:
                    lines.append(f"{key}={pending.pop(key)}")
                else:
                    lines.append(line)
            else:
                lines.append(line)
    for key, value in pending.items():
        lines.append(f"{key}={value}")
    env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
