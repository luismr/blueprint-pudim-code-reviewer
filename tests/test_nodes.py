import os
from unittest.mock import MagicMock, patch

import pytest

from graph.nodes import build_model, review_node
from graph.state import ReviewState


def test_build_model_anthropic(monkeypatch):
    monkeypatch.setenv("MODEL_PROVIDER", "anthropic")
    monkeypatch.setenv("MODEL_NAME", "claude-sonnet-4-6")
    monkeypatch.setenv("API_KEY", "fake-key")

    with patch("graph.nodes.init_chat_model") as mock_init:
        build_model()
        mock_init.assert_called_once_with(
            "claude-sonnet-4-6", model_provider="anthropic"
        )
        assert os.environ["ANTHROPIC_API_KEY"] == "fake-key"


@pytest.mark.parametrize(
    "provider,key_env",
    [
        ("anthropic", "ANTHROPIC_API_KEY"),
        ("openai", "OPENAI_API_KEY"),
        ("google_genai", "GOOGLE_API_KEY"),
    ],
)
def test_build_model_sets_correct_key_per_provider(monkeypatch, provider, key_env):
    monkeypatch.setenv("MODEL_PROVIDER", provider)
    monkeypatch.setenv("MODEL_NAME", "some-model")
    monkeypatch.setenv("API_KEY", "secret")

    with patch("graph.nodes.init_chat_model"):
        build_model()
        assert os.environ[key_env] == "secret"


@pytest.mark.parametrize(
    "provider,expected_suffix",
    [
        ("anthropic", ""),
        ("openai", "Respond in concise bullet points only."),
        ("google_genai", "Be direct"),
    ],
)
def test_review_node_applies_provider_suffix(monkeypatch, provider, expected_suffix):
    monkeypatch.setenv("MODEL_PROVIDER", provider)
    monkeypatch.setenv("MODEL_NAME", "some-model")
    monkeypatch.setenv("API_KEY", "fake-key")

    fake_response = MagicMock()
    fake_response.content = "Review output"

    with patch("graph.nodes.build_model") as mock_build:
        mock_build.return_value.invoke.return_value = fake_response

        state: ReviewState = {
            "diff": "some diff",
            "prompt": "Review this",
            "context": "Head commit SHA: abc123\n",
            "result": "",
        }
        result = review_node(state)

        invoked_prompt = mock_build.return_value.invoke.call_args[0][0]
        if expected_suffix:
            assert expected_suffix in invoked_prompt
        assert "some diff" in invoked_prompt
        assert "Head commit SHA: abc123" in invoked_prompt
        assert result["result"] == "Review output"


def test_review_node_invokes_model_and_updates_state(monkeypatch):
    monkeypatch.setenv("MODEL_PROVIDER", "anthropic")
    monkeypatch.setenv("MODEL_NAME", "claude-sonnet-4-6")
    monkeypatch.setenv("API_KEY", "fake-key")

    fake_response = MagicMock()
    fake_response.content = "Looks good, one nit on naming."

    with patch("graph.nodes.build_model") as mock_build:
        mock_build.return_value.invoke.return_value = fake_response

        state: ReviewState = {
            "diff": "some diff",
            "prompt": "Review this",
            "context": "Head commit SHA: abc123\n",
            "result": "",
        }
        result = review_node(state)

        assert result["result"] == "Looks good, one nit on naming."
        assert result["diff"] == "some diff"
        mock_build.return_value.invoke.assert_called_once()
