import pytest
from pydantic import BaseModel
from httpx import AsyncClient, ASGITransport
from api.app import app
from agents.llm_client import LLMClient, llm_call, LLMConfigurationError

class SampleOutput(BaseModel):
    message: str
    confidence: float

@pytest.mark.asyncio
async def test_api_root_and_health():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Root endpoint
        res = await client.get("/")
        assert res.status_code == 200

        # Health endpoint in mock mode
        res_health = await client.get("/api/health")
        assert res_health.status_code == 200
        data = res_health.json()
        assert data["status"] == "ok"
        assert data["llm_mode"] == "mock"

@pytest.mark.asyncio
async def test_mock_llm_call_returns_validated_pydantic():
    canned = SampleOutput(message="Validated Mock Output", confidence=0.95)
    client = LLMClient(mode="mock")
    
    result = await llm_call(
        prompt="Analyze pricing impact",
        response_model=SampleOutput,
        client=client,
        canned_response=canned
    )
    
    assert isinstance(result, SampleOutput)
    assert result.message == "Validated Mock Output"
    assert result.confidence == 0.95

@pytest.mark.asyncio
async def test_llm_client_real_mode_missing_key():
    with pytest.raises(LLMConfigurationError):
        LLMClient(mode="real", provider="gemini")
