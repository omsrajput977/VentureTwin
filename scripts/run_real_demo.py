"""
Runs the full free-plan workflow in LLM_MODE=record, saving cassette files and updating data/known_good_run.json.
Requires valid API key (e.g. GEMINI_API_KEY, OPENAI_API_KEY).
"""
import os
import sys
import json
import asyncio
from datetime import datetime, timezone
from orchestrator.supervisor import Supervisor
from orchestrator.parser import parse_decision_query
from agents.llm_client import LLMClient

async def main():
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("[ERROR] Cannot record without an API key. Set GEMINI_API_KEY or OPENAI_API_KEY in your environment.")
        print("RECORDING PENDING: run python scripts/run_real_demo.py locally with a key, then commit the cassettes.")
        sys.exit(1)

    provider = "gemini" if os.getenv("GEMINI_API_KEY") else "openai"
    model = os.getenv("LLM_MODEL") or ("gemini-1.5-pro" if provider == "gemini" else "gpt-4o")

    client = LLMClient(mode="record", provider=provider, model=model)
    supervisor = Supervisor(llm_client=client)

    decision = parse_decision_query("Should we launch a free plan?")
    print(f"Launching workflow in RECORD mode using {provider} ({model})...")
    state = await supervisor.execute_workflow(decision)

    output_path = "data/known_good_run.json"
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(state.model_dump_json(indent=2))

    print(f"Workflow completed with status: {state.status}")
    print(f"Saved recorded state to {output_path}")

if __name__ == "__main__":
    asyncio.run(main())
