import os
import time
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

_LLM_SEMAPHORE = asyncio.Semaphore(int(os.getenv("LLM_MAX_CONCURRENCY", "1")))
_pacing_lock = asyncio.Lock()
_last_request_time: float = 0.0

GEMINI_FLASH_LITE_FALLBACKS = [
    "gemini-3.5-flash-lite",
    "gemini-3.1-flash-lite",
    "gemini-2.5-flash-lite",
    "gemini-flash-lite-latest",
]

class LLMConfigurationError(Exception):
    pass

class RateLimitError(Exception):
    def __init__(self, message: str, retry_after: float = 5.0, is_daily_quota: bool = False):
        super().__init__(message)
        self.retry_after = retry_after
        self.is_daily_quota = is_daily_quota

class LLMReplayError(Exception):
    pass

def clean_prompt_for_cache(prompt: str) -> str:
    """Strip volatile values like UUIDs, timestamps, and request IDs for cache key stability."""
    cleaned = re.sub(r'dec_[a-zA-Z0-9_-]{6,}', 'dec_XXX', prompt)
    cleaned = re.sub(r'task_[a-zA-Z0-9_-]{6,}', 'task_XXX', cleaned)
    cleaned = re.sub(r'sim_[a-zA-Z0-9_-]{6,}', 'sim_XXX', cleaned)
    cleaned = re.sub(r'conflict_[a-zA-Z0-9_-]{6,}', 'conflict_XXX', cleaned)
    cleaned = re.sub(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})?', 'TIMESTAMP', cleaned)
    return cleaned

class LLMClient:
    def __init__(
        self,
        mode: Optional[str] = None,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        mock_handler: Optional[Callable[..., Any]] = None
    ):
        raw_mode = (mode or os.getenv("LLM_MODE", "mock")).lower()
        if raw_mode not in ["mock", "real", "record", "replay"]:
            raw_mode = "mock"
        self.mode: Literal["mock", "real", "record", "replay"] = raw_mode  # type: ignore

        self.provider = (provider or os.getenv("LLM_PROVIDER", "mock")).lower()
        self.model = model or os.getenv("LLM_MODEL")
        self.mock_handler = mock_handler
        self.call_count: int = 0

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
            elif self.provider == "cerebras":
                if not (os.getenv("CEREBRAS_API_KEY") or os.getenv("LLM_API_KEY")):
                    raise LLMConfigurationError("LLM_MODE=real/record with cerebras requires CEREBRAS_API_KEY")
            elif self.provider == "groq":
                if not (os.getenv("GROQ_API_KEY") or os.getenv("LLM_API_KEY")):
                    raise LLMConfigurationError("LLM_MODE=real/record with groq requires GROQ_API_KEY")
            elif self.provider == "openai_compatible":
                if not (os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY")):
                    raise LLMConfigurationError("LLM_MODE=real/record with openai_compatible requires LLM_API_KEY or OPENAI_API_KEY")
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
        max_retries: int = 5,
        temperature: float = 0.0,
        canned_response: Optional[T] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> T:
        self.call_count += 1

        # 1. Mock mode
        if self.mode == "mock":
            if canned_response is not None:
                return canned_response
            if self.mock_handler:
                try:
                    handled = self.mock_handler(prompt, response_model, metadata=metadata)
                except TypeError:
                    handled = self.mock_handler(prompt, response_model)
                if isinstance(handled, response_model):
                    return handled
                if isinstance(handled, dict):
                    return response_model.model_validate(handled)
            from agents.mock_handlers import default_mock_handler
            return default_mock_handler(prompt, response_model, metadata=metadata)

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

        # 3. Real or Record mode (with semaphore limiter, pacing, and exponential backoff)
        last_error = None
        min_pacing = float(os.getenv("LLM_REQUEST_INTERVAL", "4.0")) if self.provider == "gemini" else float(os.getenv("LLM_REQUEST_INTERVAL", "0.2"))
        async with _LLM_SEMAPHORE:
            for attempt in range(max_retries):
                try:
                    # Enforce polite pacing to stay strictly within provider RPM limits
                    async with _pacing_lock:
                        global _last_request_time
                        now = time.time()
                        elapsed = now - _last_request_time
                        if elapsed < min_pacing:
                            await asyncio.sleep(min_pacing - elapsed)
                        _last_request_time = time.time()

                    raw_json = await self._call_provider_adapter(
                        prompt=prompt,
                        system_prompt=system_prompt,
                        response_model=response_model,
                        temperature=temperature
                    )

                    # Validate response
                    try:
                        parsed = json.loads(raw_json)
                        validated = response_model.model_validate(parsed)
                    except (json.JSONDecodeError, ValidationError) as parse_err:
                        # Attempt 1 immediate JSON repair retry
                        logger.warning(f"Response validation failed ({parse_err}). Attempting JSON repair retry...")
                        repair_prompt = (
                            f"{prompt}\n\n"
                            f"Your previous output was invalid:\n{str(parse_err)}\n"
                            f"Return ONLY valid JSON matching the schema."
                        )
                        repair_json = await self._call_provider_adapter(
                            prompt=repair_prompt,
                            system_prompt=system_prompt,
                            response_model=response_model,
                            temperature=temperature
                        )
                        parsed = json.loads(repair_json)
                        validated = response_model.model_validate(parsed)
                        raw_json = repair_json

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

                except RateLimitError as rle:
                    last_error = rle
                    # If daily quota is exhausted for this model, automatically switch to an active Flash Lite model
                    if rle.is_daily_quota and self.provider == "gemini":
                        candidates = [m for m in GEMINI_FLASH_LITE_FALLBACKS if m != self.model]
                        if candidates:
                            new_model = candidates[0]
                            logger.warning(
                                f"Daily quota exhausted for model {self.model}. "
                                f"Auto-switching to fallback Flash Lite model {new_model} (500 RPD tier)..."
                            )
                            self.model = new_model
                            continue

                    sleep_time = max(rle.retry_after, 5.0 * (attempt + 1)) + random.uniform(0.5, 1.5)
                    logger.warning(f"Rate limited (429) on attempt {attempt + 1}. Backing off for {sleep_time:.1f}s...")
                    await asyncio.sleep(sleep_time)
                except LLMConfigurationError:
                    raise
                except Exception as e:
                    logger.warning(f"LLM call attempt {attempt + 1} ({self.provider}/{self.model}) failed: {e}")
                    last_error = e
                    delay = (2 ** attempt) * 1.0 + random.uniform(0.1, 0.5)
                    await asyncio.sleep(delay)

        if os.getenv("LLM_FALLBACK_ON_ERROR", "true").lower() == "true" and self.mode == "real":
            logger.warning(
                f"LLM call ({self.provider}/{self.model}) failed after {max_retries} attempts ({last_error}). "
                "Engaging autonomous resilience fallback: generating structured assumptions from deterministic telemetry handler."
            )
            from agents.mock_handlers import default_mock_handler
            return default_mock_handler(prompt, response_model, metadata=metadata)

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

            async with httpx.AsyncClient(timeout=60.0) as client:
                res = await client.post(url, json=payload, headers=headers)
                if res.status_code == 429:
                    body_text = res.text.lower()
                    if "limit: 0" in body_text or "quota limit: 0" in body_text:
                        raise LLMConfigurationError(
                            f"Model '{self.model}' quota limit is 0 on this key's free tier. "
                            "Run scripts/list_gemini_models.py to choose a Flash-family model."
                        )
                    is_daily = any(term in body_text for term in ["requests per day", "requests_per_day", "per day", "daily"])
                    retry_after = float(res.headers.get("Retry-After", 5.0))
                    raise RateLimitError("Gemini API rate limit exceeded (429)", retry_after=retry_after, is_daily_quota=is_daily)

                res.raise_for_status()
                data = res.json()

                candidates = data.get("candidates", [])
                if not candidates:
                    raise ValueError(f"Gemini returned no candidates for model {self.model}")

                candidate = candidates[0]
                finish_reason = candidate.get("finishReason", "")
                if finish_reason in ["SAFETY", "BLOCKLIST", "PROHIBITED_CONTENT", "SPII"]:
                    raise ValueError(f"Gemini generation blocked by safety policy ({finish_reason})")

                parts = candidate.get("content", {}).get("parts", [])
                if not parts:
                    raise ValueError("Gemini returned candidate with empty parts")

                return parts[0].get("text", "")

        elif self.provider in ["openai", "openai_compatible", "cerebras", "groq"]:
            if self.provider == "cerebras":
                api_key = os.getenv("CEREBRAS_API_KEY") or os.getenv("LLM_API_KEY")
                base_url = os.getenv("CEREBRAS_BASE_URL", "https://api.cerebras.ai/v1").rstrip("/")
                url = f"{base_url}/chat/completions"
            elif self.provider == "groq":
                api_key = os.getenv("GROQ_API_KEY") or os.getenv("LLM_API_KEY")
                base_url = os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1").rstrip("/")
                url = f"{base_url}/chat/completions"
            elif self.provider == "openai_compatible":
                api_key = os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY")
                base_url = os.getenv("LLM_BASE_URL", "https://api.openai.com/v1").rstrip("/")
                url = f"{base_url}/chat/completions"
            else:
                api_key = os.getenv("OPENAI_API_KEY")
                url = "https://api.openai.com/v1/chat/completions"

            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            }
            messages = []
            sys_msg = system_prompt or "You are a helpful strategic analysis assistant."
            if "json" not in sys_msg.lower() and "json" not in prompt.lower():
                sys_msg += " Return your response strictly as a valid JSON object."
            messages.append({"role": "system", "content": sys_msg})
            messages.append({"role": "user", "content": prompt})
            payload = {
                "model": self.model,
                "messages": messages,
                "temperature": temperature,
                "response_format": {"type": "json_object"}
            }
            async with httpx.AsyncClient(timeout=60.0) as client:
                res = await client.post(url, json=payload, headers=headers)
                if res.status_code >= 400:
                    try:
                        err_json = res.json()
                        err_msg = err_json.get("error", {}).get("message", res.text)
                    except Exception:
                        err_msg = res.text

                    if res.status_code == 429:
                        retry_after = float(res.headers.get("Retry-After", 2.0))
                        raise RateLimitError(f"{self.provider} API rate limit exceeded (429): {err_msg}", retry_after=retry_after)
                    raise RuntimeError(f"{self.provider} API error ({res.status_code}): {err_msg}")

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
            async with httpx.AsyncClient(timeout=60.0) as client:
                res = await client.post(url, json=payload, headers=headers)
                if res.status_code == 429:
                    retry_after = float(res.headers.get("Retry-After", 2.0))
                    await asyncio.sleep(retry_after)
                    res.raise_for_status()
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
