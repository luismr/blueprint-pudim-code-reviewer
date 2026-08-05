from unittest.mock import patch

from graph.prompt_loader import DEFAULT_PROMPT, load_prompt


def test_inline_prompt_wins(monkeypatch, mock_gh):
    monkeypatch.setenv("REVIEW_PROMPT", "Custom inline prompt")
    assert load_prompt(mock_gh) == "Custom inline prompt"


def test_local_file_used_when_no_inline(monkeypatch, mock_gh, tmp_path):
    prompt_file = tmp_path / "prompt.md"
    prompt_file.write_text("Local file prompt")
    monkeypatch.setenv("PROMPT_FILE", str(prompt_file))
    assert load_prompt(mock_gh) == "Local file prompt"


def test_local_file_path_set_but_missing_falls_through(monkeypatch, mock_gh):
    # covers the `os.path.exists` False branch
    monkeypatch.setenv("PROMPT_FILE", "/nonexistent/path.md")
    assert load_prompt(mock_gh) == DEFAULT_PROMPT


def test_remote_repo_success(monkeypatch, mock_gh):
    monkeypatch.setenv("PROMPT_REPO", "luismr/review-standards")
    monkeypatch.setenv("PROMPT_REPO_PATH", "prompts/review.md")
    monkeypatch.setenv("PROMPT_REPO_REF", "main")

    content_file = mock_gh.get_repo.return_value.get_contents.return_value
    content_file.decoded_content = b"Remote prompt content"

    result = load_prompt(mock_gh)

    assert result == "Remote prompt content"
    mock_gh.get_repo.assert_called_once_with("luismr/review-standards")
    mock_gh.get_repo.return_value.get_contents.assert_called_once_with(
        "prompts/review.md", ref="main"
    )


def test_remote_repo_uses_default_path_and_ref(monkeypatch, mock_gh):
    # covers the .get(...) default fallback for path/ref env vars
    monkeypatch.setenv("PROMPT_REPO", "luismr/review-standards")
    content_file = mock_gh.get_repo.return_value.get_contents.return_value
    content_file.decoded_content = b"content"

    load_prompt(mock_gh)

    mock_gh.get_repo.return_value.get_contents.assert_called_once_with(
        "CLAUDE_REVIEW.md", ref="main"
    )


def test_remote_repo_uses_dedicated_token_when_provided(monkeypatch, mock_gh):
    monkeypatch.setenv("PROMPT_REPO", "luismr/review-standards")
    monkeypatch.setenv("PROMPT_REPO_TOKEN", "dedicated-token")

    with patch("graph.prompt_loader.Github") as mock_github_cls:
        remote_client = mock_github_cls.return_value
        content_file = remote_client.get_repo.return_value.get_contents.return_value
        content_file.decoded_content = b"Remote via dedicated token"

        result = load_prompt(mock_gh)

        mock_github_cls.assert_called_once_with("dedicated-token")
        assert result == "Remote via dedicated token"
        # base client must NOT have been used when a dedicated token exists
        mock_gh.get_repo.assert_not_called()


def test_remote_repo_failure_falls_back_to_default(monkeypatch, mock_gh, capsys):
    monkeypatch.setenv("PROMPT_REPO", "luismr/review-standards")
    mock_gh.get_repo.side_effect = Exception("404 not found")

    result = load_prompt(mock_gh)

    assert result == DEFAULT_PROMPT
    assert "::warning::" in capsys.readouterr().out


def test_no_config_returns_default(monkeypatch, mock_gh):
    assert load_prompt(mock_gh) == DEFAULT_PROMPT
