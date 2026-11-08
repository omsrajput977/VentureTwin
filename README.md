# VentureTwin

> **AI Flight Simulator & Operational Digital Twin for SaaS CEOs**  
> *Built for the SwarmFlow: Multi-Agent Task Coordination Engine Hackathon*

[![Test Suite](https://img.shields.io/badge/pytest-84%20passed%2C%201%20skipped-emerald)](file:///Users/omrajput/Desktop/Projects/VentureTwin/tests)
[![UI Verification](https://img.shields.io/badge/UI%20check-no%20fake%20numbers-blue)](file:///Users/omrajput/Desktop/Projects/VentureTwin/ui/scripts/check-no-fake-numbers.mjs)
[![Architecture](https://img.shields.io/badge/Orchestrator-Custom%20Async%20DAG-purple)](#architecture)
[![Coverage](https://img.shields.io/badge/Acceptance%20Criteria-12%2F12%20Verified-blueviolet)](#scorecard)
[![CI](https://github.com/omsrajput977/VentureTwin/actions/workflows/ci.yml/badge.svg)](https://github.com/omsrajput977/VentureTwin/actions)

---

## 🎯 Executive Summary

**VentureTwin** is a decision stress-test platform and operational digital twin for SaaS pricing and packaging decisions. When a founder or leadership team asks a high-stakes question (e.g. *"Should we launch a free plan?"*), VentureTwin orchestrates a virtual executive board of specialized AI agents running in parallel, detects disagreements, resolves conflicts via deterministic simulation rather than voting, survives runtime agent failures, and produces one consolidated, verified decision report.

**Core Pitch:** *"An orchestration engine where agents disagree, conflicts are resolved by simulation instead of voting, no number comes from an LLM, and the system survives an agent failure mid-run."*

---

## 🏆 SwarmFlow Hackathon Milestone Scorecard

| Milestone | Implementation in VentureTwin | Status |
|---|---|---|
| **1. Agent Role Design** | 6 specialized roles (`CFO`, `Growth`, `CTO`, `Customer`, `Product`, `Skeptic`) with divergent objectives, private tools, structured Pydantic `Finding` outputs, and unified `llm_call()` supporting `mock`, `real`, `record`, and `replay` modes. | `[MVP-REAL]` |
| **2. Task Decomposition Engine** | Natural-language query parser + `TaskDAG` generator with explicit Freemium / Free Plan MVP specialization (and friendly v0.2 notices for price changes). Parallel specialist root tasks, critique, bounded discussion, and synthesis nodes with cycle detection. | `[MVP-REAL]` |
| **3. Supervisor Architecture** | Async DAG supervisor dispatching independent tasks concurrently via `asyncio`, managing core vs specialist task states, and emitting typed events over an `EventBus`. | `[MVP-REAL]` |
| **4. Agent Communication Protocol** | Standardized `Finding`, `Assumption`, and `Evidence` schema enforcement with a bounded 1-round peer rebuttal discussion node (`task_agent_discussion`). | `[MVP-REAL]` |
| **5. Shared State Management** | Typed `WorkflowState` tracking findings, assumptions, conflicts, simulation runs, and SQLite checkpointing after each task completion with seamless resume. | `[MVP-REAL]` |
| **6. Conflict Detection & Resolution** | Ordinal contradiction detector ($\ge 2$ step difference required) and grouped parameter range conflict detection. Settle impasses via deterministic isolated-parameter simulation runs. | `[MVP-REAL]` |
| **7. Failure Detection & Recovery** | Fault injection hook (`timeout`, `exception`, `bad_output`), instant timeout simulation, core task resilience (fails fast if CFO/Growth fail terminally), and automated `BackupAnalyst` delegation before degraded mode fallback. | `[MVP-REAL]` |
| **8. Workflow Verification** | `NumberRegistry` tracking every report number with provenance and tolerances, regex prose scanner detecting untraced figures, unit consistency, financial tie-outs, simulation provenance verification, and bounded loopback on verification failure. | `[MVP-REAL]` |
| **9. Final Output Generation** | 10-section consolidated decision report, scenario matrix (conservative/expected/optimistic), sensitivity tornado chart, bisection flip-point search, execution plan gates, dynamic calibration error history, and human approval gate. | `[MVP-REAL]` |

---

## 🏗️ Architecture

```mermaid
graph TD
    User["Founder / Strategy Lead"] --> Intake["Decision Intake & Scope Parser"]
    Intake --> Supervisor["Central Supervisor (Async DAG Engine)"]
    
    subgraph "Core Tasks (Fail-Fast Resilience)"
        Supervisor --> CFO["CFO Agent (Runway & Margins)"]
        Supervisor --> Growth["Growth Agent (Acquisition & Funnel)"]
    end

    subgraph "Specialist Tasks (BackupAnalyst Fallback)"
        Supervisor --> CTO["CTO Agent (Infra & Compute Load)"]
        Supervisor --> Customer["Customer Agent (Retention & Cannibalization)"]
        Supervisor --> Product["Product Agent (Feature Packaging)"]
        CTO -. On Failure .-> Backup["Backup Analyst Agent"]
        Customer -. On Failure .-> Backup
        Product -. On Failure .-> Backup
    end

    CFO --> Skeptic["Skeptic Agent (Auditor & Grounded Benchmarks)"]
    Growth --> Skeptic
    CTO --> Skeptic
    Customer --> Skeptic
    Product --> Skeptic
    Backup --> Skeptic

    Skeptic --> Discussion["Agent Discussion Node (1-Round Bounded Rebuttal)"]
    Discussion --> Conflict["Simulation-Backed Conflict Resolver (Isolated Sim Runs)"]
    Conflict --> Sim["Deterministic SaaS Dynamics Simulator (NumPy 24mo)"]
    Sim --> Verifier["Verification Layer (NumberRegistry + Regex Prose Audit)"]
    Verifier --> Report["10-Section Consolidated Decision Report"]
    Report --> Gate["Human-in-the-Loop Sign-Off Gate"]
    Gate --> History["Decision Calibration & Memory (Dynamic Calculation)"]

    Supervisor -. Checkpoints .-> SQLite[("SQLite State Store")]
    Supervisor -. Live Telemetry .-> SSE["EventBus / SSE Stream"]
    SSE --> UI["React + Tailwind Dashboard (MOCK MODE & DEGRADED Badges)"]
```

---

## ⚖️ Real vs. Mocked (Strict Transparency)

- **What is REAL (`[MVP-REAL]`):**
  - Multi-agent orchestration, task DAG decomposition, parallel execution with core vs specialist task distinction.
  - LLM invocation through `llm_call()` supporting `mock`, `real`, `record`, and `replay` modes across Gemini, OpenAI, and Anthropic.
  - Deterministic 24-month SaaS dynamics simulation model with externalized `data/model_config.json` establishing genuine Strategy A vs Strategy B trade-offs.
  - Monte Carlo sampling and One-At-A-Time (OAT) Tornado sensitivity analysis.
  - Bisection root-finding for exact decision flip points.
  - Simulation-based conflict resolution (no voting, no LLM choosing winners) using isolated single-parameter simulations.
  - Runtime fault injection and autonomous recovery (`BackupAnalyst` fallback, instant timeout injection).
  - Verification layer with `NumberRegistry` and regex prose audit ensuring 100% of executive numbers trace to input or simulation.
  - FastAPI backend and React frontend with honest status indicators.
- **What is SEEDED (`[MVP-MOCK]`):**
  - Company dataset: `NimbusDesk` synthetic Series A SaaS telemetry (`data/synthetic_company.json`) with fully grounded metrics.
  - Grounded B2B SaaS benchmarks: `data/benchmarks.json` sourced from industry SaaS research.
  - Historical decisions: 4 seeded past decisions for calibration error analysis (`data/seeded_decisions.json`).
  - LLM Provider: Runs in `mock` mode by default for 100% deterministic, zero-token test runs; swappable to `real` mode with `GEMINI_API_KEY`, `OPENAI_API_KEY`, or `ANTHROPIC_API_KEY`.

---

## 🚀 Getting Started

### 1. Prerequisites
- Python 3.11+
- Node.js v18+ and npm

### 2. Backend Setup
```bash
# Clone the repository
git clone https://github.com/omsrajput977/VentureTwin.git
cd VentureTwin

# Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install Python dependencies
pip install fastapi uvicorn pydantic numpy scipy pytest pytest-asyncio httpx
```

### 3. Frontend Setup
```bash
cd ui
npm install
npm run build
cd ..
```

### 4. Running the Application
```bash
# Start the FastAPI server (serves API and built React UI)
./.venv/bin/uvicorn api.app:app --host 0.0.0.0 --port 8000 --reload
```
Open your browser at **[http://localhost:8000/](http://localhost:8000/)**.

To run the React development server with hot module reloading:
```bash
cd ui
npm run dev
```

---

## 🧪 Automated Test Suite

Run the full pytest suite (84 passed, 1 skipped across unit, integration, and acceptance criteria):
```bash
./.venv/bin/pytest
```

Run UI no-fake-numbers audit:
```bash
node ui/scripts/check-no-fake-numbers.mjs
```

---

## 📜 Demo Script

See [docs/DEMO_SCRIPT.md](file:///Users/omrajput/Desktop/Projects/VentureTwin/docs/DEMO_SCRIPT.md) for a step-by-step 3-minute hackathon judge walkthrough.

