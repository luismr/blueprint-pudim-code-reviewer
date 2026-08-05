from unittest.mock import MagicMock

import pytest


@pytest.fixture
def mock_gh():
    """A fake Github client — no real network calls are ever made."""
    return MagicMock()


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    """Wipe relevant env vars before every test so tests don't leak state
    into one another via os.environ."""
    for var in [
        "ADDITIONAL_RULES",
        "ADDITIONAL_RULES_FILE",
        "MODEL_PROVIDER",
        "MODEL_NAME",
        "API_KEY",
        "ANTHROPIC_API_KEY",
        "OPENAI_API_KEY",
        "GOOGLE_API_KEY",
        "GITHUB_TOKEN",
        "GITHUB_REPOSITORY",
        "GITHUB_EVENT_PATH",
        "GITHUB_OUTPUT",
        "TRIGGER_LABEL",
        "REMOVE_TRIGGER_LABEL",
        "AUTO_APPROVE",
    ]:
        monkeypatch.delenv(var, raising=False)
