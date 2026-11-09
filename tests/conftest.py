import os
import pytest

@pytest.fixture(autouse=True)
def test_environment_isolation(monkeypatch, request):
    """
    Isolates pytest test execution:
    - Default LLM_MODE to 'mock' for repeatable unit tests
    - Clear live API keys for configuration tests that assert missing-key errors
    """
    # Keep LLM_MODE as mock for offline test suite unless explicitly running live LLM tests
    if os.getenv("RUN_LIVE_LLM") != "1":
        monkeypatch.setenv("LLM_MODE", "mock")

    # For tests explicitly checking configuration failures when keys/models are absent
    test_name = request.node.name.lower()
    if any(k in test_name for k in ["missing_key", "configuration_checks", "readiness"]):
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.delenv("LLM_MODEL", raising=False)

