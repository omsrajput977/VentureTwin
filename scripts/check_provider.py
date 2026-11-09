#!/usr/bin/env python3
"""
Universal verification script for whichever LLM provider is active in .env
(OpenAI, Cerebras, Gemini, Anthropic, or OpenAI-compatible).
Usage:
    python scripts/check_provider.py
"""
import os
import sys
import time
import asyncio
from pathlib import Path
from pydantic import BaseModel

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Load .env if present
env_file = Path(__file__).resolve().parent.parent / ".env"
if env_file.exists():
    with open(env_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

class EchoProbe(BaseModel):
    greeting: str
    model_name: str
    status: str
    verified: bool

async def main():
    provider = os.getenv("LLM_PROVIDER", "mock").lower()
    model = os.getenv("LLM_MODEL", "default")
    mode = os.getenv("LLM_MODE", "real").lower()

    # Check provider-specific API keys
    key_map = {
        "openai": "OPENAI_API_KEY",
        "cerebras": "CEREBRAS_API_KEY",
        "groq": "GROQ_API_KEY",
        "gemini": "GEMINI_API_KEY",
        "anthropic": "ANTHROPIC_API_KEY",
        "openai_compatible": "LLM_API_KEY"
    }

    req_key = key_map.get(provider)
    if req_key and not os.getenv(req_key):
        print(f"[ERROR] Provider '{provider}' requires {req_key} to be set in .env.")
        sys.exit(1)

    from agents.llm_client import LLMClient, LLMConfigurationError

    print(f"Testing active LLM provider configuration...")
    print(f"Provider: {provider}")
    print(f"Model:    {model}")
    print(f"Mode:     {mode}")

    try:
        client = LLMClient(mode=mode, provider=provider, model=model)
    except LLMConfigurationError as e:
        print(f"[ERROR] Configuration error: {e}")
        sys.exit(1)

    prompt = (
        'Respond with a JSON object matching this schema exactly: '
        '{"greeting": "Hello from ' + provider + '", "model_name": "' + model + '", "status": "ok", "verified": true}. '
        'Return ONLY valid JSON.'
    )

    t0 = time.time()
    try:
        res: EchoProbe = await client.call(
            prompt=prompt,
            response_model=EchoProbe,
            system_prompt="You are a helpful JSON assistant. Return output strictly in valid JSON.",
            max_retries=3,
            temperature=0.0,
            metadata={"agent_key": "probe"}
        )
        latency = round(time.time() - t0, 2)
        print(f"\n[SUCCESS] Call succeeded!")
        print(f"Latency:  {latency}s")
        print(f"Response: {res.model_dump_json(indent=2)}")
    except Exception as e:
        print(f"\n[FAILURE] Call failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())

