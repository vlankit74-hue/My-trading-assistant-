"""
Provider-agnostic LLM interface. The rest of the app calls `LLMClient`
methods only — switching providers is a one-line config change
(`llm_provider=claude` vs `llm_provider=openai`), never a code change in
the decision logic.
"""
from abc import ABC, abstractmethod


class LLMClient(ABC):
    """Contract: send a system+user prompt pair, get raw text back.
    JSON parsing/validation happens one layer up (decision_engine.py) so it's
    identical regardless of which provider answered."""

    @abstractmethod
    async def complete(self, system_prompt: str, user_prompt: str, max_tokens: int = 1500) -> str:
        raise NotImplementedError
