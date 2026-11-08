import uuid
from typing import List, Dict, Any, Optional
from state.schemas import Finding, Conflict, Task, Evidence

ORDINAL_MAP: Dict[str, int] = {
    "strongly_oppose": -2,
    "reject": -2,
    "oppose": -1,
    "proceed_with_limits": -1,
    "neutral": 0,
    "needs_more_info": 0,
    "support": 1,
    "proceed": 1,
    "strongly_support": 2
}

def detect_contradictory_recommendations(findings: List[Finding]) -> List[Conflict]:
    """
    Flags conflicts only when ordinal distance between recommendations is >= 2.
    For example: oppose (-1) vs support (+1) = 2 (conflict).
    support (+1) vs strongly_support (+2) = 1 (NOT a conflict).
    Degraded agent findings are excluded.
    """
    conflicts: List[Conflict] = []
    valid_findings = [f for f in findings if not getattr(f, "degraded", False)]

    seen_pairs = set()
    for i in range(len(valid_findings)):
        for j in range(i + 1, len(valid_findings)):
            f1 = valid_findings[i]
            f2 = valid_findings[j]
            score1 = ORDINAL_MAP.get(f1.recommendation.lower(), 0)
            score2 = ORDINAL_MAP.get(f2.recommendation.lower(), 0)

            if abs(score1 - score2) >= 2:
                pair_key = tuple(sorted([f1.agent, f2.agent]))
                if pair_key in seen_pairs:
                    continue
                seen_pairs.add(pair_key)

                conflicts.append(Conflict(
                    id=f"conf_rec_{uuid.uuid4().hex[:6]}",
                    type="contradictory_recommendations",
                    agents=[f1.agent, f2.agent],
                    disputed_item="decision_recommendation",
                    evidence=f1.evidence + f2.evidence,
                    status="resolved",
                    resolution=None,
                    simulation_ids=[],
                    sides=[
                        {"agent": f1.agent, "recommendation": f1.recommendation, "score": score1},
                        {"agent": f2.agent, "recommendation": f2.recommendation, "score": score2}
                    ]
                ))
    return conflicts


def detect_non_overlapping_ranges(findings: List[Finding]) -> List[Conflict]:
    """
    Groups parameter conflicts PER PARAMETER NAME (one conflict per parameter, not NxN pairs).
    Degraded findings are excluded.
    """
    conflicts: List[Conflict] = []
    valid_findings = [f for f in findings if not getattr(f, "degraded", False)]

    assumptions_by_name: Dict[str, List[tuple[str, Any]]] = {}
    for f in valid_findings:
        for asm in f.assumptions:
            assumptions_by_name.setdefault(asm.name, []).append((f.agent, asm))

    for name, agent_asms in assumptions_by_name.items():
        if len(agent_asms) < 2:
            continue

        # Check if any pair has non-overlapping ranges
        has_divergence = False
        for i in range(len(agent_asms)):
            for j in range(i + 1, len(agent_asms)):
                _, asm1 = agent_asms[i]
                _, asm2 = agent_asms[j]
                if asm1.high < asm2.low or asm2.high < asm1.low:
                    has_divergence = True
                    break
            if has_divergence:
                break

        if has_divergence:
            evidence_list = []
            sides = []
            agents = []
            for agent, asm in agent_asms:
                agents.append(agent)
                sides.append({
                    "agent": agent,
                    "base": asm.base,
                    "range": [asm.low, asm.high]
                })
                evidence_list.append(Evidence(
                    source_type="calculation",
                    source_ref=f"{agent}.{name}",
                    snippet=f"{agent} proposed range [{asm.low}, {asm.high}] with base {asm.base}"
                ))

            conflicts.append(Conflict(
                id=f"conf_range_{uuid.uuid4().hex[:6]}",
                type="non_overlapping_ranges",
                agents=sorted(list(set(agents))),
                disputed_item=name,
                evidence=evidence_list,
                resolution=None,
                simulation_ids=[],
                status="resolved",
                sides=sides
            ))

    return conflicts


def detect_missing_evidence(findings: List[Finding]) -> List[Conflict]:
    """
    Flags missing evidence on empirical claims.
    Missing sources result in 'unresolved_material' status.
    """
    conflicts: List[Conflict] = []
    valid_findings = [f for f in findings if not getattr(f, "degraded", False)]

    for f in valid_findings:
        for asm in f.assumptions:
            if asm.provenance in ["verified_data", "external_research"] and not asm.source_ref:
                conflicts.append(Conflict(
                    id=f"conf_evi_{uuid.uuid4().hex[:6]}",
                    type="missing_evidence",
                    agents=[f.agent],
                    disputed_item=asm.name,
                    evidence=[],
                    resolution=f"Unresolved: {f.agent} cited {asm.name} as {asm.provenance} without a verifiable source reference.",
                    simulation_ids=[],
                    unresolved=True,
                    status="unresolved_material",
                    sides=[{"agent": f.agent, "parameter": asm.name, "provenance": asm.provenance}]
                ))
    return conflicts


def detect_all_conflicts(findings: List[Finding]) -> List[Conflict]:
    all_c = []
    all_c.extend(detect_contradictory_recommendations(findings))
    all_c.extend(detect_non_overlapping_ranges(findings))
    all_c.extend(detect_missing_evidence(findings))
    return all_c

