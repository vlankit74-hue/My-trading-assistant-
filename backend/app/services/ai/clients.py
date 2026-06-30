"""
Concrete LLM clients. Both implement the same `complete()` contract so the
decision engine code never branches on provider.
"""
from anthropic import AsyncAnthropic
from openai import AsyncOpenAI

from app.core.config import Settings
from app.services.ai.base import LLMClient


class ClaudeClient(LLMClient):
    def __init__(self, settings: Settings):
        self._client = AsyncAnthropic(api_key=settings.anthropic_api_key.get_secret_value())
        self._model = settings.anthropic_model

    async def complete(self, system_prompt: str, user_prompt: str, max_tokens: int = 1500) -> str:
        response = await self._client.messages.create(
            model=self._model,
            max_tokens=max_tokens,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )
        return "".join(block.text for block in response.content if block.type == "text")


class OpenAIClient(LLMClient):
    def __init__(self, settings: Settings):
        self._client = AsyncOpenAI(api_key=settings.openai_api_key.get_secret_value())
        self._model = settings.openai_model

    async def complete(self, system_prompt: str, user_prompt: str, max_tokens: int = 1500) -> str:
        response = await self._client.chat.completions.create(
            model=self._model,
            max_tokens=max_tokens,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        return response.choices[0].message.content or ""


def get_llm_client(settings: Settings) -> LLMClient:
    """Factory — this is the ONE place that knows which provider is active."""
    if settings.llm_provider == "claude":
        return ClaudeClient(settings)
    if settings.llm_provider == "openai":
        return OpenAIClient(settings)
    raise ValueError(f"Unknown llm_provider: {settings.llm_provider}")
