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
- **Action:** Under **Live Fault Injection**, select target `CFO` (or `CTO`), mode `Process Exception (Crash)`, toggle the **"Persistent Failure across all retries"** switch, and click **"Inject Failure"**.
- **Show:**
  - The Event Feed displays `agent_failed` for the targeted agent across attempts.
  - The Supervisor's fault-tolerant engine detects persistent failure and invokes the autonomous **Backup Analyst**.
  - If the backup succeeds, the finding is marked `recovered_via_backup=True`, confidence is capped at Medium, and the agent is tracked in `recovered_agents`.
  - If backup also fails, the engine safely applies a graceful degraded fallback (`fallback_degraded` provenance, confidence <= 0.3), surfaces an honest **Degraded Mode Banner** in the UI, and completes the workflow without crashing.
  - Show contrast: if a central supervisor task (e.g., simulation engine) fails terminally, the system safely halts with `status="failed"`, emits `workflow_failed`, and preserves a resumable SQLite checkpoint.

### 4. Skeptic Audit & Simulation-Backed Conflict Resolution (1:45 - 2:15)
- **Show:**
  - **Skeptic Agent:** Audits Growth's optimistic assumption (3.5% conversion) for lack of self-serve telemetry, audits CFO's conservative range, and checks industry benchmarks.
  - **Bounded Peer Discussion:** 1-round structured rebuttal where agents hold ground (`stance="defend"`) or concede with rationale.
  - **Empirical Conflict Resolution:** Point to the conflict panel. Disagreements between CFO and Growth are **not settled by an LLM picking a winner or voting**.
  - **Simulation Decided:** The engine isolates the disputed parameter (`free_to_paid_conversion`), simulates outcomes under both agent proposals, calculates exact net contribution and runway deltas, and resolves by quantitative evidence.
  - **Transparent Unresolved/Material Conflicts:** If an impasse cannot be settled or falls within tolerance, it is tagged `resolved_immaterial` or `unresolved_material` and reported honestly in the final output rather than hidden.

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

