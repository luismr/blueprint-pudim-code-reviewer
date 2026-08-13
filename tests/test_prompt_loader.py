from graph.prompt_loader import (
    ADDITIONAL_RULES_DEFAULT,
    DEFAULT_PROMPT,
    _collect_additional_rules,
    load_prompt,
)


def test_collect_additional_rules_returns_none_when_empty(monkeypatch):
    assert _collect_additional_rules() is None


def test_default_prompt_forbids_double_escaped_newlines():
    assert "Do not double-escape" in DEFAULT_PROMPT
    assert "real line breaks" in DEFAULT_PROMPT
    assert "**single** JSON" in DEFAULT_PROMPT


def test_load_prompt_keeps_default_placeholder_when_empty(monkeypatch):
    result = load_prompt()

    assert result == DEFAULT_PROMPT
    assert ADDITIONAL_RULES_DEFAULT in result
    assert "## Additional code review rules (optional)" in result
    step2_index = result.index("## Step 2")
    rules_index = result.index(ADDITIONAL_RULES_DEFAULT)
    step3_index = result.index("## Step 3")
    assert step2_index < rules_index < step3_index


def test_load_prompt_replaces_default_with_inline_rules(monkeypatch):
    monkeypatch.setenv("ADDITIONAL_RULES", "Require unit tests for every public method.")

    result = load_prompt()

    assert ADDITIONAL_RULES_DEFAULT not in result
    assert "Require unit tests for every public method." in result
    rules_index = result.index("Require unit tests for every public method.")
    step3_index = result.index("## Step 3")
    assert rules_index < step3_index


def test_load_prompt_replaces_default_with_rules_file(monkeypatch, tmp_path):
    rules_file = tmp_path / "rules.md"
    rules_file.write_text("Never approve without migration notes.")
    monkeypatch.setenv("ADDITIONAL_RULES_FILE", str(rules_file))

    result = load_prompt()

    assert ADDITIONAL_RULES_DEFAULT not in result
    assert "Never approve without migration notes." in result
    assert result.index("Never approve without migration notes.") < result.index("## Step 3")


def test_load_prompt_keeps_default_when_rules_file_missing(monkeypatch):
    monkeypatch.setenv("ADDITIONAL_RULES_FILE", "/nonexistent/rules.md")

    result = load_prompt()

    assert result == DEFAULT_PROMPT
    assert ADDITIONAL_RULES_DEFAULT in result


def test_load_prompt_keeps_default_when_rules_file_empty(monkeypatch, tmp_path):
    rules_file = tmp_path / "rules.md"
    rules_file.write_text("   \n")
    monkeypatch.setenv("ADDITIONAL_RULES_FILE", str(rules_file))

    assert _collect_additional_rules() is None
    assert load_prompt() == DEFAULT_PROMPT


def test_load_prompt_combines_file_then_inline_rules(monkeypatch, tmp_path):
    rules_file = tmp_path / "rules.md"
    rules_file.write_text("File rule one.")
    monkeypatch.setenv("ADDITIONAL_RULES_FILE", str(rules_file))
    monkeypatch.setenv("ADDITIONAL_RULES", "Inline rule two.")

    result = load_prompt()

    file_index = result.index("File rule one.")
    inline_index = result.index("Inline rule two.")
    step3_index = result.index("## Step 3")
    assert file_index < inline_index < step3_index
