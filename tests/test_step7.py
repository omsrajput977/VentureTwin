import pytest
from state.schemas import Finding, Assumption, Evidence, Task
from conflict.detector import (
    detect_contradictory_recommendations,
    detect_non_overlapping_ranges,
    detect_missing_evidence,
    detect_all_conflicts
)
from conflict.resolver import resolve_conflict_via_simulation
from agents.registry import default_registry

@pytest.mark.asyncio
async def test_conflict_detection_on_cfo_and_growth():
    cfo = default_registry.get("cfo")
    growth = default_registry.get("growth")

    cfo_f = await cfo.run(Task(id="t_cfo", owner_agent="CFO"), context={})
    growth_f = await growth.run(Task(id="t_growth", owner_agent="Growth"), context={})

    findings = [cfo_f, growth_f]

    # 1. Contradictory recommendations
    conf_recs = detect_contradictory_recommendations(findings)
    assert len(conf_recs) >= 1
    assert "CFO" in conf_recs[0].agents
    assert "Growth" in conf_recs[0].agents

    # 2. Non-overlapping ranges
    conf_ranges = detect_non_overlapping_ranges(findings)
    conv_conf = next((c for c in conf_ranges if c.disputed_item == "free_to_paid_conversion"), None)
    assert conv_conf is not None
    assert set(conv_conf.agents) == {"CFO", "Growth"}

def test_missing_evidence_detector():
    f = Finding(
        agent="Growth",
        task_id="t1",
        claim="Speculative claim",
        recommendation="proceed",
        assumptions=[
            Assumption(
                name="external_metric",
                low=1, base=2, high=3,
                unit="pct",
                provenance="external_research",
                source_ref=None  # Missing source_ref!
            )
        ]
    )
    conflicts = detect_missing_evidence([f])
    assert len(conflicts) == 1
    assert conflicts[0].type == "missing_evidence"

@pytest.mark.asyncio
async def test_conflict_resolution_via_simulation():
    cfo = default_registry.get("cfo")
    growth = default_registry.get("growth")

    cfo_f = await cfo.run(Task(id="t_cfo", owner_agent="CFO"), context={})
    growth_f = await growth.run(Task(id="t_growth", owner_agent="Growth"), context={})

    conflicts = detect_non_overlapping_ranges([cfo_f, growth_f])
    target_conf = conflicts[0]

    resolved = resolve_conflict_via_simulation(target_conf, [cfo_f, growth_f])

    assert len(resolved.simulation_ids) == 2
    assert resolved.resolution is not None
    # Resolution contains real numbers, not placeholder text
    assert "$" in resolved.resolution
    assert "months runway" in resolved.resolution
    assert not resolved.unresolved

