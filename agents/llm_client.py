import os
import json
import re
import random
import hashlib
import asyncio
import logging
from pathlib import Path
from typing import Type, TypeVar, Optional, Any, Callable, Dict, Literal
from pydantic import BaseModel, ValidationError

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)

CASSETTES_DIR = Path(__file__).resolve().parent.parent / "tests" / "cassettes"

class LLMConfigurationError(Exception):
    pass

class LLMReplayError(Exception):
    pass

def clean_prompt_for_cache(prompt: str) -> str:
    """Strip volatile values like UUIDs, timestamps, and request IDs for cache key stability."""
    cleaned = re.sub(r'dec_[a-f0-9]{8,}', 'dec_XXX', prompt)
    cleaned = re.sub(r'task_[a-zA-Z0-9_]+_[a-f0-9]{6,}', 'task_XXX', cleaned)
    cleaned = re.sub(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})?', 'TIMESTAMP', cleaned)
    return cleaned

class LLMClient:
    def __init__(
        self,
        mode: Optional[str] = None,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        mock_handler: Optional[Callable[[str, Type[T]], Any]] = None
    ):
        raw_mode = (mode or os.getenv("LLM_MODE", "mock")).lower()
        if raw_mode not in ["mock", "real", "record", "replay"]:
            raw_mode = "mock"
        self.mode: Literal["mock", "real", "record", "replay"] = raw_mode  # type: ignore

        self.provider = (provider or os.getenv("LLM_PROVIDER", "mock")).lower()
        self.model = model or os.getenv("LLM_MODEL")
        self.mock_handler = mock_handler

        # Validation for real and record modes
        if self.mode in ["real", "record"]:
            if not self.model:
                raise LLMConfigurationError(
                    f"LLM_MODE={self.mode} requires an explicit LLM_MODEL (no default model ID baked in)."
                )
            if self.provider == "gemini":
                if not os.getenv("GEMINI_API_KEY"):
                    raise LLMConfigurationError("LLM_MODE=real/record with gemini requires GEMINI_API_KEY")
            elif self.provider == "openai":
                if not os.getenv("OPENAI_API_KEY"):
                    raise LLMConfigurationError("LLM_MODE=real/record with openai requires OPENAI_API_KEY")
            elif self.provider == "anthropic":
                if not os.getenv("ANTHROPIC_API_KEY"):
                    raise LLMConfigurationError("LLM_MODE=real/record with anthropic requires ANTHROPIC_API_KEY")
            else:
                raise LLMConfigurationError(f"Unsupported provider for {self.mode} mode: {self.provider}")

    def _get_cassette_path(self, prompt: str, model_cls_name: str) -> Path:
        cleaned = clean_prompt_for_cache(prompt)
        key_str = f"{cleaned}||{model_cls_name}||{self.provider}||{self.model}"
        hash_val = hashlib.sha256(key_str.encode("utf-8")).hexdigest()
        return CASSETTES_DIR / f"{hash_val}.json"

    async def call(
        self,
        prompt: str,
        response_model: Type[T],
        system_prompt: Optional[str] = None,
        max_retries: int = 3,
        temperature: float = 0.0,
        canned_response: Optional[T] = None
    ) -> T:
        # 1. Mock mode
        if self.mode == "mock":
            if canned_response is not None:
                return canned_response
            if self.mock_handler:
                handled = self.mock_handler(prompt, response_model)
                if isinstance(handled, response_model):
                    return handled
                if isinstance(handled, dict):
                    return response_model.model_validate(handled)
            from agents.mock_handlers import default_mock_handler
            return default_mock_handler(prompt, response_model)

        # 2. Replay mode
        if self.mode == "replay":
            cassette_path = self._get_cassette_path(prompt, response_model.__name__)
            if not cassette_path.exists():
                raise LLMReplayError(
                    f"Cassette not found for prompt in replay mode: {cassette_path}. "
                    "Run scripts/run_real_demo.py with LLM_MODE=record first."
                )
            with open(cassette_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return response_model.model_validate_json(data["response"])

        # 3. Real or Record mode (with exponential backoff and jitter)
        last_error = None
        for attempt in range(max_retries):
            try:
                raw_json = await self._call_provider_adapter(
                    prompt=prompt,
                    system_prompt=system_prompt,
                    response_model=response_model,
                    temperature=temperature
                )
                parsed = json.loads(raw_json)
                validated = response_model.model_validate(parsed)

                if self.mode == "record":
                    cassette_path = self._get_cassette_path(prompt, response_model.__name__)
                    cassette_path.parent.mkdir(parents=True, exist_ok=True)
                    with open(cassette_path, "w", encoding="utf-8") as f:
                        json.dump({
                            "prompt": prompt,
                            "cleaned_prompt": clean_prompt_for_cache(prompt),
                            "model_name": response_model.__name__,
                            "provider": self.provider,
                            "model": self.model,
                            "response": raw_json
                        }, f, indent=2)

                return validated

            except Exception as e:
                logger.warning(f"LLM call attempt {attempt + 1} failed: {e}")
                last_error = e
                # Check for rate limit or retry header
                delay = (2 ** attempt) * 0.5 + random.uniform(0.05, 0.2)
                await asyncio.sleep(delay)

        raise RuntimeError(f"LLM call failed after {max_retries} retries: {last_error}")

    async def _call_provider_adapter(
        self,
        prompt: str,
        system_prompt: Optional[str],
        response_model: Type[T],
        temperature: float
    ) -> str:
        import httpx

        if self.provider == "gemini":
            api_key = os.getenv("GEMINI_API_KEY")
            # Header key, NEVER in URL
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent"
            headers = {
                "x-goog-api-key": api_key,
                "Content-Type": "application/json"
            }
            payload = {
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {
                    "temperature": temperature,
                    "responseMimeType": "application/json"
                }
            }
            if system_prompt:
                payload["systemInstruction"] = {"parts": [{"text": system_prompt}]}

            async with httpx.AsyncClient(timeout=30.0) as client:
                res = await client.post(url, json=payload, headers=headers)
                if res.status_code == 429:
                    retry_after = float(res.headers.get("Retry-After", 2.0))
                    await asyncio.sleep(retry_after)
                    res.raise_for_status()
                res.raise_for_status()
                data = res.json()
                return data["candidates"][0]["content"]["parts"][0]["text"]

        elif self.provider == "openai":
            api_key = os.getenv("OPENAI_API_KEY")
            url = "https://api.openai.com/v1/chat/completions"
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            }
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})
            payload = {
                "model": self.model,
                "messages": messages,
                "temperature": temperature,
                "response_format": {"type": "json_object"}
            }
            async with httpx.AsyncClient(timeout=30.0) as client:
                res = await client.post(url, json=payload, headers=headers)
                if res.status_code == 429:
                    retry_after = float(res.headers.get("Retry-After", 2.0))
                    await asyncio.sleep(retry_after)
                    res.raise_for_status()
                res.raise_for_status()
                data = res.json()
                return data["choices"][0]["message"]["content"]

        elif self.provider == "anthropic":
            api_key = os.getenv("ANTHROPIC_API_KEY")
            url = "https://api.anthropic.com/v1/messages"
            headers = {
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "Content-Type": "application/json"
            }
            payload = {
                "model": self.model,
                "max_tokens": 2048,
                "temperature": temperature,
                "messages": [{"role": "user", "content": prompt}]
            }
            if system_prompt:
                payload["system"] = system_prompt
            async with httpx.AsyncClient(timeout=30.0) as client:
                res = await client.post(url, json=payload, headers=headers)
                res.raise_for_status()
                data = res.json()
                return data["content"][0]["text"]

        else:
            raise ValueError(f"Unsupported provider: {self.provider}")

default_llm_client = LLMClient()

async def llm_call(
    prompt: str,
    response_model: Type[T],
    system_prompt: Optional[str] = None,
    client: Optional[LLMClient] = None,
    **kwargs
) -> T:
    c = client or default_llm_client
    return await c.call(prompt, response_model, system_prompt=system_prompt, **kwargs)
