"""
Builds the review prompt from the built-in default plus optional extra rules.

Optional rules from `additional_rules_file` and `additional_rules` replace the
default placeholder after Step 2. When no rules are configured, the prompt file
is returned unchanged.
"""

import os
from pathlib import Path

_DEFAULT_PROMPT_PATH = Path(__file__).resolve().parent.parent / "prompts" / "default_review.md"
DEFAULT_PROMPT = _DEFAULT_PROMPT_PATH.read_text(encoding="utf-8")
ADDITIONAL_RULES_DEFAULT = "_No additional rules configured._"


def _collect_additional_rules() -> str | None:
    parts: list[str] = []

    rules_file = os.environ.get("ADDITIONAL_RULES_FILE", "").strip()
    if rules_file and os.path.exists(rules_file):
        file_rules = open(rules_file, encoding="utf-8").read().strip()
        if file_rules:
            parts.append(file_rules)

    inline_rules = os.environ.get("ADDITIONAL_RULES", "").strip()
    if inline_rules:
        parts.append(inline_rules)

    if not parts:
        return None

    return "\n\n".join(parts)


def load_prompt() -> str:
    rules = _collect_additional_rules()
    if not rules:
        return DEFAULT_PROMPT

    return DEFAULT_PROMPT.replace(ADDITIONAL_RULES_DEFAULT, rules)
