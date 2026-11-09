#!/usr/bin/env python3
"""
Inspect available models on Groq for the configured GROQ_API_KEY.
Usage:
    python scripts/list_groq_models.py
"""
import os
import sys
from pathlib import Path
import httpx

# Load .env if present
env_file = Path(__file__).resolve().parent.parent / ".env"
if env_file.exists():
    with open(env_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

def main():
    api_key = os.getenv("GROQ_API_KEY") or os.getenv("LLM_API_KEY")
    if not api_key:
        print("[ERROR] GROQ_API_KEY is not set in environment or .env file.")
        sys.exit(1)

    url = "https://api.groq.com/openai/v1/models"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    try:
        res = httpx.get(url, headers=headers, timeout=15.0)
        if res.status_code != 200:
            print(f"[ERROR] Groq API returned status {res.status_code}: {res.text}")
            sys.exit(1)

        data = res.json()
        models = data.get("data", [])
        print(f"Total Groq models available: {len(models)}\n")
        print(f"{'Model ID':<35} | {'Owned By':<15} | {'Active'}")
        print("-" * 65)
        for m in sorted(models, key=lambda x: x.get("id", "")):
            mid = m.get("id", "")
            owner = m.get("owned_by", "")
            active = m.get("active", True)
            print(f"{mid:<35} | {owner:<15} | {active}")

    except Exception as e:
        print(f"[ERROR] Failed to query Groq models endpoint: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()

