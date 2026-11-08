import pytest
import asyncio
from httpx import AsyncClient, ASGITransport
from api.app import app, active_workflows, active_supervisors
from orchestrator.parser import parse_decision_query
from orchestrator.supervisor import Supervisor

@pytest.mark.asyncio
async def test_full_api_workflow_cycle():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Company snapshot
        res_comp = await client.get("/api/company")
        assert res_comp.status_code == 200
        assert res_comp.json()["company_name"] == "NimbusDesk"
        assert res_comp.json()["synthetic_data_badge"] is True

        # 2. Company graph
        res_graph = await client.get("/api/graph")
        assert res_graph.status_code == 200
        data_graph = res_graph.json()
        assert "nodes" in data_graph and "edges" in data_graph
        assert len(data_graph["nodes"]) >= 6

        # 3. Submit decision
        res_sub = await client.post("/api/decisions", json={"query": "Should we launch a free plan?"})
        assert res_sub.status_code == 200
        dec_id = res_sub.json()["decision_id"]

        # Run supervisor synchronously for test verification
        sup = active_supervisors[dec_id]
        decision = parse_decision_query("Should we launch a free plan?")
        decision.id = dec_id
        state = await sup.execute_workflow(decision)
        active_workflows[dec_id] = state

        # 4. Status endpoint
        res_status = await client.get(f"/api/decisions/{dec_id}")
        assert res_status.status_code == 200
        assert res_status.json()["status"] in ["completed", "degraded"]
        assert len(res_status.json()["findings"]) >= 5

        # 5. Report endpoint
        res_rep = await client.get(f"/api/decisions/{dec_id}/report")
        assert res_rep.status_code == 200
        rep_data = res_rep.json()
        assert "recommendation" in rep_data
        assert "sections" in rep_data
        assert "executive_summary" in rep_data["sections"]

        # 6. Approval endpoint
        res_app = await client.post(f"/api/decisions/{dec_id}/approve", json={"action": "approve", "notes": "Approved for Q1"})
        assert res_app.status_code == 200
        assert res_app.json()["status"] == "recorded"
        assert res_app.json()["decision_record"]["status"] == "awaiting_outcome"

        # 7. History & Calibration endpoint
        res_hist = await client.get("/api/history")
        assert res_hist.status_code == 200
        hist_data = res_hist.json()
        assert len(hist_data["seeded_decisions"]) >= 3
        assert len(hist_data["live_approved_decisions"]) >= 1
        assert "calibration_summary" in hist_data

