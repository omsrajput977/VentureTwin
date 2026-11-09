#!/usr/bin/env python3
"""
Lists available models from the Google Gemini API that support generateContent,
highlighting Flash-family models suitable for the free tier.
Usage:
    python scripts/list_gemini_models.py
"""
import os
import sys
import httpx
from pathlib import Path

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
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("[ERROR] GEMINI_API_KEY is not set in environment or .env file.")
        print("To use this script, put your Gemini API key in .env:")
        print("GEMINI_API_KEY=your_key_here")
        sys.exit(1)

    url = "https://generativelanguage.googleapis.com/v1beta/models"
    headers = {
        "x-goog-api-key": api_key,
        "Content-Type": "application/json"
    }

    try:
        with httpx.Client(timeout=30.0) as client:
            res = client.get(url, headers=headers)
            if res.status_code == 400:
                print(f"[ERROR 400] Bad Request: {res.text}")
                sys.exit(1)
            elif res.status_code in (401, 403):
                print(f"[ERROR {res.status_code}] Authentication Failed. Please verify your GEMINI_API_KEY in .env.")
                sys.exit(1)
            elif res.status_code == 429:
                print(f"[ERROR 429] Rate limited / Quota exhausted: {res.text}")
                sys.exit(1)
            res.raise_for_status()
            data = res.json()
    except Exception as e:
        print(f"[ERROR] Failed to query Gemini models endpoint: {e}")
        sys.exit(1)

    models = data.get("models", [])
    print(f"Total models returned: {len(models)}\n")
    print(f"{'Model Name / ID':<45} | {'Methods':<30} | {'Flash Family'}")
    print("-" * 90)

    recommended = []
    for m in models:
        raw_name = m.get("name", "")
        # Remove 'models/' prefix for model ID
        model_id = raw_name.replace("models/", "")
        methods = ", ".join(m.get("supportedGenerationMethods", []))
        if "generateContent" not in methods:
            continue

        is_flash = "flash" in model_id.lower()
        flash_mark = "⚡ YES (Recommended for free tier)" if is_flash else "No"
        print(f"{model_id:<45} | {methods:<30} | {flash_mark}")
        if is_flash:
            recommended.append(model_id)

    print("-" * 90)
    print("\nRecommended Flash-family models for .env (set LLM_MODEL=<model>):")
    for r in recommended:
        print(f"  - {r}")

if __name__ == "__main__":
    main()
