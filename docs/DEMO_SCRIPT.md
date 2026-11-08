# VentureTwin: 3-Minute Hackathon Demo Script

> **Problem Statement:** SwarmFlow: Multi-Agent Task Coordination Engine  
> **Product:** VentureTwin — Operational Digital Twin & AI Flight Simulator for SaaS CEOs  
> **Pitch:** *"An orchestration engine where agents disagree, conflicts are resolved by simulation instead of voting, no number comes from an LLM, and the system survives an agent failure mid-run."*

---

## Demo Walkthrough (Step-by-Step)

### 1. The Setup: Company Baseline (0:00 - 0:30)
- **Action:** Open VentureTwin at `http://localhost:8000/`.
- **Show:** The **NimbusDesk** operational snapshot:
  - Series A B2B SaaS platform ($110.4k MRR, $1.65M cash, 13.2 months runway, 655 paying customers).
  - Point out the persistent **"Synthetic Data"** badge.
  - Explain: *"VentureTwin is an operational digital twin. CEOs don't need another generic LLM giving advice. They need a flight simulator that stress-tests pricing decisions against real balance sheet constraints."*

### 2. Decision Intake & Parallel Agent Decomposition (0:30 - 1:15)
- **Action:** In the Decision Console, select or type:
  `"Should we launch a free plan?"`
  Click **"Run Simulation"**.
- **Show:**
  - The Supervisor's DAG dynamically decomposes the decision into a dependency graph.
  - 5 specialist agent nodes execute **in parallel** (demonstrated live with concurrent timestamps):
    - **CFO:** Evaluates cash burn and margin risk.
    - **Growth:** Evaluates top-of-funnel acquisition velocity.
    - **CTO:** Evaluates cloud database and compute limits.
    - **Customer:** Evaluates Starter tier cannibalization.
    - **Product:** Evaluates feature gating boundaries.
  - Click on the **Growth** node and **CFO** node to inspect their structured `Finding` objects.
  - Notice the emergent disagreement: Growth recommends `proceed` with 3.5% conversion; CFO recommends `proceed_with_limits` with 1.5% conversion.

### 3. Live Failure Injection & Autonomous Recovery (1:15 - 1:45)
- **Action:** Under **Live Fault Injection**, select target `CTO` and mode `Process Exception (Crash)`, then click **"Inject Failure"**.
- **Show:**
  - The Event Feed displays `agent_failed` for CTO.
  - The Supervisor's fault-tolerant engine detects the crash, initiates backoff retry (`recovery_started`), and safely completes or transitions to degraded mode (`recovery_done`).
  - Checkpoint persistence in SQLite ensures no completed tasks need re-execution.

### 4. Skeptic Audit & Simulation-Backed Conflict Resolution (1:45 - 2:15)
- **Show:**
  - **Skeptic Agent:** Audits Growth's optimistic assumption (3.5% conversion) for lack of self-serve telemetry and downgrades confidence.
  - **Empirical Conflict Resolution:** Point to the conflict panel. Disagreements between CFO and Growth are **not settled by an LLM picking a winner or voting**.
  - The engine ran the deterministic NumPy simulator for both sides. It proved that Strategy B (Usage Caps) preserves the minimum 10-month runway constraint even under the CFO's conservative assumptions, mathematically settling the impasse.

### 5. Consolidated Report, Sensitivity Tornado & Flip Point (2:15 - 2:45)
- **Action:** Click the **"Decision Report"** tab.
- **Show:**
  - **Recommendation:** `Proceed with B usage caps` (Rank #1, Feasible, preserves 12+ mo runway).
  - **Scenario Matrix:** Conservative, Expected, and Optimistic outcomes (strictly data-driven).
  - **Sensitivity Tornado Chart:** Shows which assumption drives the greatest variance.
  - **Flip Point:** Points out the plain-language threshold:
    `"Strategy B beats Strategy C only if free-to-paid conversion stays above 0.62%."`
  - **Assumption Ledger:** Full provenance tags (`verified_data`, `external_research`, `simulated_estimate`, `ai_assumption`).
  - **Deterministic Verification Layer:** 5 automated checks (financial tie-outs, provenance integrity, simulation traceability) all passed.

### 6. Human Approval & Decision Calibration Memory (2:45 - 3:00)
- **Action:** Under the Sign-Off Gate, type: `"Approved for Q1 rollout with 3-seat cap"`, and click **"Approve Recommendation"**.
- **Show:**
  - Navigate to **"Calibration & Memory"**.
  - Show the newly approved decision recorded as `"Awaiting Outcome"`.
  - Review historical seeded decisions comparing predicted vs. actual telemetry with drift error %.
- **Conclusion:** *"VentureTwin demonstrates true multi-agent coordination: autonomous task division, parallel execution, simulation-backed conflict resolution, live fault recovery, deterministic verification, and decision memory."*

