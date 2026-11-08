import uuid
from typing import List, Dict, Any, Optional
from state.schemas import Finding, Conflict, Task, Evidence

def detect_contradictory_recommendations(findings: List[Finding]) -> List[Conflict]:
    conflicts: List[Conflict] = []
    proceed_agents = [f for f in findings if f.recommendation == "proceed"]
    opposing_agents = [f for f in findings if f.recommendation in ["proceed_with_limits", "reject"]]

    if proceed_agents and opposing_agents:
        for p in proceed_agents:
            for opp in opposing_agents:
                conflicts.append(Conflict(
                    id=f"conf_rec_{uuid.uuid4().hex[:6]}",
                    type="contradictory_recommendations",
                    agents=[p.agent, opp.agent],
                    disputed_item="decision_recommendation",
                    evidence=p.evidence + opp.evidence,
                    resolution=None,
                    simulation_ids=[]
                ))
    return conflicts


def detect_non_overlapping_ranges(findings: List[Finding]) -> List[Conflict]:
    conflicts: List[Conflict] = []
    # Collect assumptions by name across agents
    assumptions_by_name: Dict[str, List[tuple[str, Any]]] = {}
    for f in findings:
        for asm in f.assumptions:
            assumptions_by_name.setdefault(asm.name, []).append((f.agent, asm))

    for name, agent_asms in assumptions_by_name.items():
        if len(agent_asms) < 2:
            continue
        # Compare pairwise
        for i in range(len(agent_asms)):
            for j in range(i + 1, len(agent_asms)):
                agent1, asm1 = agent_asms[i]
                agent2, asm2 = agent_asms[j]
                # Non-overlapping range check: asm1.high < asm2.low or asm2.high < asm1.low
                if asm1.high < asm2.low or asm2.high < asm1.low:
                    conflicts.append(Conflict(
                        id=f"conf_range_{uuid.uuid4().hex[:6]}",
                        type="non_overlapping_ranges",
                        agents=[agent1, agent2],
                        disputed_item=name,
                        evidence=[
                            Evidence(
                                source_type="calculation",
                                source_ref=f"{agent1}.{name}",
                                snippet=f"{agent1} proposed range [{asm1.low}, {asm1.high}] with base {asm1.base}"
                            ),
                            Evidence(
                                source_type="calculation",
                                source_ref=f"{agent2}.{name}",
                                snippet=f"{agent2} proposed range [{asm2.low}, {asm2.high}] with base {asm2.base}"
                            )
                        ],
                        resolution=None,
                        simulation_ids=[]
                    ))
    return conflicts


def detect_missing_evidence(findings: List[Finding]) -> List[Conflict]:
    conflicts: List[Conflict] = []
    for f in findings:
        for asm in f.assumptions:
            if asm.provenance in ["verified_data", "external_research"] and not asm.source_ref:
                conflicts.append(Conflict(
                    id=f"conf_evi_{uuid.uuid4().hex[:6]}",
                    type="missing_evidence",
                    agents=[f.agent],
                    disputed_item=asm.name,
                    evidence=[],
                    resolution=None,
                    simulation_ids=[]
                ))
    return conflicts


def detect_all_conflicts(findings: List[Finding]) -> List[Conflict]:
    all_c = []
    all_c.extend(detect_contradictory_recommendations(findings))
    all_c.extend(detect_non_overlapping_ranges(findings))
    all_c.extend(detect_missing_evidence(findings))
    return all_c
