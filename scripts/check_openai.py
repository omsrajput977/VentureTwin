#!/usr/bin/env python3
"""
Verification script for OpenAI API (e.g. gpt-4o, gpt-4o-mini).
Loads .env, makes one structured JSON call (EchoProbe), prints provider, model, latency,
and the validated JSON (never prints the API key), and exits non-zero on failure.
Usage:
    python scripts/check_openai.py
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
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("[ERROR] OPENAI_API_KEY is not set in environment or .env file.")
        print("Set OPENAI_API_KEY=sk-... in your .env file.")
        sys.exit(1)

    model = os.getenv("LLM_MODEL", "gpt-4o-mini")
    provider = os.getenv("LLM_PROVIDER", "openai").lower()

    if provider != "openai":
        print(f"[WARNING] LLM_PROVIDER in .env is '{provider}'. Testing OpenAI directly...")

    from agents.llm_client import LLMClient, LLMConfigurationError

    print(f"Testing OpenAI API configuration...")
    print(f"Provider: openai")
    print(f"Model:    {model}")

    try:
        client = LLMClient(mode="real", provider="openai", model=model)
    except LLMConfigurationError as e:
        print(f"[ERROR] Configuration error: {e}")
        sys.exit(1)

    prompt = (
        'Respond with a JSON object matching this schema exactly: '
        '{"greeting": "Hello from OpenAI", "model_name": "' + model + '", "status": "ok", "verified": true}. '
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

