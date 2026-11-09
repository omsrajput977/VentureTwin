import os
import pytest
from pydantic import BaseModel
from agents.llm_client import LLMClient

class EchoSchema(BaseModel):
    greeting: str
    status: str

@pytest.mark.skipif(os.getenv("RUN_LIVE_LLM") != "1", reason="Skipped unless RUN_LIVE_LLM=1")
@pytest.mark.live_llm
@pytest.mark.asyncio
async def test_live_gemini_call():
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        pytest.fail("GEMINI_API_KEY is missing from environment")

    model = os.getenv("LLM_MODEL")
    if not model:
        pytest.fail("LLM_MODEL is missing from environment")

    client = LLMClient(mode="real", provider="gemini", model=model)
    prompt = 'Return a JSON matching schema: {"greeting": "hello", "status": "ok"}'
    res = await client.call(prompt, EchoSchema)
    assert isinstance(res, EchoSchema)
    assert res.status == "ok"
