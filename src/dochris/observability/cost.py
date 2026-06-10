"""LLM 调用成本估算

根据 provider/model 和 token 用量估算 USD 成本。
定价数据内置（常见模型），支持通过配置文件扩展。

设计原则：
- 内置定价覆盖常用模型
- 未知模型返回 None（不估算）
- 定价数据来源于各厂商公开价格（2026 年数据）
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

# 定价表：{(provider, model_prefix): (prompt_per_1k, completion_per_1k)}
# 单位：USD / 1K tokens
_PRICING_TABLE: dict[tuple[str, str], tuple[float, float]] = {
    # 智谱 / BigModel
    ("openai_compat", "glm-5"): (0.005, 0.005),
    ("openai_compat", "glm-4"): (0.01, 0.01),
    ("openai_compat", "glm-4-flash"): (0.0001, 0.0001),
    ("openai_compat", "glm-4-plus"): (0.05, 0.05),
    # OpenAI
    ("openai_compat", "gpt-4o"): (0.0025, 0.01),
    ("openai_compat", "gpt-4o-mini"): (0.00015, 0.0006),
    ("openai_compat", "gpt-4"): (0.03, 0.06),
    ("openai_compat", "gpt-3.5"): (0.0005, 0.0015),
    # DeepSeek
    ("openai_compat", "deepseek-chat"): (0.00014, 0.00028),
    ("openai_compat", "deepseek-reasoner"): (0.00055, 0.00219),
    # Ollama（本地免费）
    ("ollama", "qwen"): (0.0, 0.0),
    ("ollama", "llama"): (0.0, 0.0),
}


class CostEstimator:
    """LLM 调用成本估算器。

    根据 provider/model 查找定价，计算 USD 成本。
    """

    def estimate(
        self,
        provider: str,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
    ) -> float | None:
        """估算单次 LLM 调用的 USD 成本。

        Args:
            provider: LLM 提供商
            model: 模型名称
            prompt_tokens: 输入 token 数
            completion_tokens: 输出 token 数

        Returns:
            估算成本（USD），未知模型返回 None
        """
        pricing = self._find_pricing(provider, model)
        if pricing is None:
            return None

        prompt_price, completion_price = pricing
        cost = (prompt_tokens / 1000.0) * prompt_price + (completion_tokens / 1000.0) * completion_price
        return round(cost, 6)

    def _find_pricing(self, provider: str, model: str) -> tuple[float, float] | None:
        """查找匹配的定价条目。

        策略：先精确匹配，再前缀匹配（如 "glm-5.1" 匹配 "glm-5"）。
        """
        provider = provider.lower()
        model_lower = model.lower()

        # 精确匹配
        for (p, m), pricing in _PRICING_TABLE.items():
            if p == provider and m == model_lower:
                return pricing

        # 前缀匹配
        for (p, m), pricing in _PRICING_TABLE.items():
            if p == provider and model_lower.startswith(m):
                return pricing

        return None
