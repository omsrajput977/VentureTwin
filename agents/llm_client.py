import os
import json
import logging
from typing import Type, TypeVar, Optional, Any, Callable
from pydantic import BaseModel, ValidationError

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)

class LLMConfigurationError(Exception):
    pass

class LLMClient:
    def __init__(
        self,
        mode: Optional[str] = None,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        mock_handler: Optional[Callable[[str, Type[T]], Any]] = None
    ):
        self.mode = (mode or os.getenv("LLM_MODE", "mock")).lower()
        self.provider = (provider or os.getenv("LLM_PROVIDER", "mock")).lower()
        self.model = model or os.getenv("LLM_MODEL", "mock-agent-v1")
        self.mock_handler = mock_handler
        
        if self.mode == "real":
            if self.provider == "gemini" and not os.getenv("GEMINI_API_KEY"):
                raise LLMConfigurationError("LLM_MODE=real with gemini requires GEMINI_API_KEY")
            elif self.provider == "openai" and not os.getenv("OPENAI_API_KEY"):
                raise LLMConfigurationError("LLM_MODE=real with openai requires OPENAI_API_KEY")

    async def call(
        self,
        prompt: str,
        response_model: Type[T],
        system_prompt: Optional[str] = None,
        max_retries: int = 3,
        temperature: float = 0.0,
        canned_response: Optional[T] = None
    ) -> T:
        """
        Provider-agnostic LLM call that returns a validated Pydantic model.
        In mock mode, returns a canned response or constructs one based on the model.
        """
        if self.mode == "mock":
            if canned_response is not None:
                return canned_response
            if self.mock_handler:
                handled = self.mock_handler(prompt, response_model)
                if isinstance(handled, response_model):
                    return handled
                if isinstance(handled, dict):
                    return response_model.model_validate(handled)
            # Default fallback mock generation: try instantiating or return mock default
            return self._generate_mock_instance(response_model)

        # Real mode (bounded retries)
        last_error = None
        for attempt in range(max_retries):
            try:
                raw_json = await self._call_real_provider(
                    prompt=prompt,
                    system_prompt=system_prompt,
                    response_model=response_model,
                    temperature=temperature
                )
                parsed = json.loads(raw_json)
                return response_model.model_validate(parsed)
            except (ValidationError, json.JSONDecodeError, Exception) as e:
                logger.warning(f"LLM call attempt {attempt + 1} failed: {e}")
                last_error = e

        raise RuntimeError(f"LLM call failed after {max_retries} retries: {last_error}")

    def _generate_mock_instance(self, model_cls: Type[T]) -> T:
        """Generate a basic valid mock instance using model field defaults or schema types."""
        sample_dict = {}
        for name, field in model_cls.model_fields.items():
            if field.default is not None and field.default is not ...:
                sample_dict[name] = field.default
            elif field.default_factory is not None:
                sample_dict[name] = field.default_factory()
            else:
                # Basic mock defaults for common types
                annotation = field.annotation
                if annotation == str or str in getattr(annotation, "__args__", ()):
                    sample_dict[name] = f"mock_{name}"
                elif annotation == float or float in getattr(annotation, "__args__", ()):
                    sample_dict[name] = 1.0
                elif annotation == int or int in getattr(annotation, "__args__", ()):
                    sample_dict[name] = 1
                elif annotation == bool:
                    sample_dict[name] = True
                elif getattr(annotation, "__origin__", None) == list:
                    sample_dict[name] = []
                else:
                    sample_dict[name] = None
        return model_cls.model_validate(sample_dict)

    async def _call_real_provider(
        self,
        prompt: str,
        system_prompt: Optional[str],
        response_model: Type[T],
        temperature: float
    ) -> str:
        # Provider specific call (placeholder for real integration via httpx)
        if self.provider == "gemini":
            import httpx
            api_key = os.getenv("GEMINI_API_KEY")
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent?key={api_key}"
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
                res = await client.post(url, json=payload)
                res.raise_for_status()
                data = res.json()
                return data["candidates"][0]["content"]["parts"][0]["text"]
        elif self.provider == "openai":
            import httpx
            api_key = os.getenv("OPENAI_API_KEY")
            url = "https://api.openai.com/v1/chat/completions"
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
                res = await client.post(url, json=payload, headers={"Authorization": f"Bearer {api_key}"})
                res.raise_for_status()
                data = res.json()
                return data["choices"][0]["message"]["content"]
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
