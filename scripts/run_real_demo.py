"""
Runs the full free-plan workflow in LLM_MODE=record, saving cassette files,
updating data/known_good_run.json, and writing docs/REAL_RUN_REPORT.md.
Requires valid API key (e.g. GEMINI_API_KEY, OPENAI_API_KEY).
"""
import os
import sys
import time
import json
import asyncio
from datetime import datetime, timezone
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

from orchestrator.supervisor import Supervisor
from orchestrator.parser import parse_decision_query
from agents.llm_client import LLMClient

async def main():
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("[ERROR] Cannot record without an API key. Put GEMINI_API_KEY and LLM_MODEL in your .env file.")
        print("RECORDING PENDING: put GEMINI_API_KEY and LLM_MODEL in .env, then run scripts/check_gemini.py and LLM_MODE=record python scripts/run_real_demo.py.")
        sys.exit(1)

    provider = os.getenv("LLM_PROVIDER") or ("gemini" if os.getenv("GEMINI_API_KEY") else "openai")
    model = os.getenv("LLM_MODEL")
    if not model:
        print("[ERROR] LLM_MODEL is not set in environment or .env file.")
        print("Run python scripts/list_gemini_models.py to list available models, then set LLM_MODEL in .env.")
        sys.exit(1)

    t0 = time.time()
    print(f"Launching workflow in RECORD mode using {provider} ({model})...")
    client = LLMClient(mode="record", provider=provider, model=model)
    supervisor = Supervisor(llm_client=client)

    decision = parse_decision_query("Should we launch a free plan?")
    state = await supervisor.execute_workflow(decision)
    total_time = round(time.time() - t0, 2)

    output_path = Path("data/known_good_run.json")
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(state.model_dump_json(indent=2))

    # Compile REAL_RUN_REPORT.md
    prov_counts = {"verified_data": 0, "external_research": 0, "ai_assumption": 0, "simulated_estimate": 0, "fallback_degraded": 0}
    findings_summary = []
    for f in state.findings:
        findings_summary.append(f"- **{f.agent}**: recommendation='{f.recommendation}', confidence={f.confidence:.2f}, claim='{f.claim}'")
        for a in f.assumptions:
            if a.provenance in prov_counts:
                prov_counts[a.provenance] += 1

    conflicts_summary = []
    for c in state.conflicts:
        conflicts_summary.append(f"- Disputed item: `{c.disputed_item}` between {c.agents}. Status: {c.status}. Resolution: {c.resolution or 'N/A'}")

    report_content = f"""# Real LLM Run Report

- **Date / Time:** {datetime.now(timezone.utc).isoformat()}
- **LLM Mode:** record
- **Provider:** {provider}
- **Model:** {model}
- **Total Execution Time:** {total_time}s
- **Total LLM Invocations:** {client.call_count}
- **Workflow Status:** {state.status}

## Agent Findings & Recommendations
{chr(10).join(findings_summary) if findings_summary else "No findings recorded."}

## Provenance Breakdown
- `verified_data`: {prov_counts['verified_data']}
- `external_research`: {prov_counts['external_research']}
- `ai_assumption`: {prov_counts['ai_assumption']}
- `simulated_estimate`: {prov_counts['simulated_estimate']}
- `fallback_degraded`: {prov_counts['fallback_degraded']}

## Ignored / Clamped Parameters
- Ignored parameters: {state.ignored_assumptions or 'None'}

## Conflict Resolution
{chr(10).join(conflicts_summary) if conflicts_summary else "No conflicts detected."}

## Verification Results
- Verified: {state.verification_result.verified if state.verification_result else 'N/A'}
- Checks Passed: {len([c for c in (state.verification_result.checks if state.verification_result else []) if c.passed])}
- Tamper Flag: {state.verification_result.tamper_detected if state.verification_result else False}
"""
    report_file = Path("docs/REAL_RUN_REPORT.md")
    report_file.parent.mkdir(parents=True, exist_ok=True)
    with open(report_file, "w", encoding="utf-8") as f:
        f.write(report_content)

    print(f"\n[SUCCESS] Workflow completed with status: {state.status}")
    print(f"Saved recorded state to {output_path}")
    print(f"Generated real run audit in {report_file}")

if __name__ == "__main__":
    asyncio.run(main())
