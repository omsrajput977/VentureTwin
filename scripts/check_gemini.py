#!/usr/bin/env python3
"""
Live verification script for Google Gemini API.
Loads .env, makes one tiny structured call (EchoSchema), prints provider, model, latency,
and the validated JSON (never the API key), and exits non-zero on failure.
Usage:
    python scripts/check_gemini.py
"""
import os
import sys
import time
import asyncio
from pathlib import Path
from pydantic import BaseModel

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
    status: str
    verified: bool

async def main():
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("[ERROR] GEMINI_API_KEY is not set in environment or .env file.")
        print("Set GEMINI_API_KEY in your .env file.")
        sys.exit(1)

    model = os.getenv("LLM_MODEL")
    if not model:
        print("[ERROR] LLM_MODEL is not set in environment or .env file.")
        print("Run python scripts/list_gemini_models.py to list available models, then set LLM_MODEL in .env.")
        sys.exit(1)

    provider = os.getenv("LLM_PROVIDER", "gemini").lower()
    if provider != "gemini":
        print(f"[ERROR] LLM_PROVIDER is set to '{provider}', but this script tests the Google Gemini provider.")
        sys.exit(1)

    from agents.llm_client import LLMClient, LLMConfigurationError

    print(f"Testing live Gemini API call...")
    print(f"Provider: {provider}")
    print(f"Model:    {model}")

    try:
        client = LLMClient(mode="real", provider="gemini", model=model)
    except LLMConfigurationError as e:
        print(f"[ERROR] Configuration error: {e}")
        sys.exit(1)

    prompt = (
        'Return a JSON object conforming exactly to this schema:\n'
        '{"greeting": "Hello from Gemini", "status": "ok", "verified": true}'
    )

    start_time = time.time()
    try:
        res: EchoProbe = await client.call(prompt, EchoProbe, temperature=0.0)
        elapsed = time.time() - start_time
    except Exception as e:
        elapsed = time.time() - start_time
        err_msg = str(e)
        if "401" in err_msg or "403" in err_msg:
            print(f"[ERROR 401/403] Authentication failure. Verify your GEMINI_API_KEY in .env.")
        elif "404" in err_msg:
            print(f"[ERROR 404] Model '{model}' not found. Run python scripts/list_gemini_models.py to pick a valid model ID.")
        elif "429" in err_msg:
            print(f"[ERROR 429] Rate limit / quota exceeded. Details: {err_msg}")
        elif "quota limit: 0" in err_msg or "not available on this key's free tier" in err_msg:
            print(f"[ERROR] Model '{model}' quota limit is 0 on free tier. Pick a Flash-family model.")
        else:
            print(f"[ERROR] API call failed: {err_msg}")
        sys.exit(1)

    print("\n[SUCCESS] Live call succeeded!")
    print(f"Latency:  {elapsed:.2f}s")
    print(f"Response: {res.model_dump_json(indent=2)}")
    sys.exit(0)

if __name__ == "__main__":
    asyncio.run(main())
