"""Provider-agnostic LLM client with structured output support.

Supports Anthropic (Claude) and OpenAI APIs through a common interface.
Uses the `instructor` library for structured responses via Pydantic models.
"""

from __future__ import annotations

import logging
from enum import Enum
from typing import TypeVar, Type

from pydantic import BaseModel

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


class LLMProvider(Enum):
    ANTHROPIC = "anthropic"
    OPENAI = "openai"


class LLMClient:
    """Unified LLM client supporting text and vision, with structured outputs."""

    def __init__(
        self,
        provider: LLMProvider = LLMProvider.ANTHROPIC,
        model: str | None = None,
        api_key: str | None = None,
    ) -> None:
        self.provider = provider
        self.api_key = api_key

        if provider == LLMProvider.ANTHROPIC:
            self.model = model or "claude-sonnet-4-20250514"
            self._init_anthropic()
        elif provider == LLMProvider.OPENAI:
            self.model = model or "gpt-4o"
            self._init_openai()

    def _init_anthropic(self) -> None:
        import anthropic
        import instructor

        base_client = anthropic.Anthropic(api_key=self.api_key)
        self._client = instructor.from_anthropic(base_client)
        self._raw_client = base_client

    def _init_openai(self) -> None:
        import openai
        import instructor

        base_client = openai.OpenAI(api_key=self.api_key)
        self._client = instructor.from_openai(base_client)
        self._raw_client = base_client

    def structured(
        self,
        prompt: str,
        response_model: Type[T],
        system: str | None = None,
        max_retries: int = 2,
    ) -> T:
        """Get a structured response matching a Pydantic model."""
        messages = []
        if system and self.provider == LLMProvider.OPENAI:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        kwargs: dict = {
            "model": self.model,
            "messages": messages,
            "response_model": response_model,
            "max_retries": max_retries,
        }

        if system and self.provider == LLMProvider.ANTHROPIC:
            kwargs["system"] = system

        return self._client.chat.completions.create(**kwargs)

    def vision_structured(
        self,
        prompt: str,
        image_b64: str,
        media_type: str,
        response_model: Type[T],
        max_retries: int = 2,
    ) -> T:
        """Get a structured response from an image + prompt."""
        if self.provider == LLMProvider.ANTHROPIC:
            content = [
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": media_type,
                        "data": image_b64,
                    },
                },
                {"type": "text", "text": prompt},
            ]
        else:
            content = [
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:{media_type};base64,{image_b64}"},
                },
                {"type": "text", "text": prompt},
            ]

        messages = [{"role": "user", "content": content}]

        return self._client.chat.completions.create(
            model=self.model,
            messages=messages,
            response_model=response_model,
            max_retries=max_retries,
        )

    def text(self, prompt: str, system: str | None = None) -> str:
        """Get a plain text response (no structured output)."""
        if self.provider == LLMProvider.ANTHROPIC:
            import anthropic
            response = self._raw_client.messages.create(
                model=self.model,
                max_tokens=4096,
                system=system or "",
                messages=[{"role": "user", "content": prompt}],
            )
            return response.content[0].text
        else:
            messages = []
            if system:
                messages.append({"role": "system", "content": system})
            messages.append({"role": "user", "content": prompt})
            response = self._raw_client.chat.completions.create(
                model=self.model,
                messages=messages,
            )
            return response.choices[0].message.content or ""
