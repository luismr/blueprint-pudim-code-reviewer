import json

import pytest

from graph.review_parser import (
    InlineComment,
    ParsedReview,
    build_github_comments,
    filter_valid_inline_comments,
    normalize_escaped_markdown,
    parse_review_output,
    review_event,
)


def _sample_payload(**overrides):
    payload = {
        "overview": "## Summary\nLooks mostly good.",
        "verdict": "CHANGES_REQUESTED",
        "inline_comments": [
            {
                "path": "src/main.py",
                "line": 12,
                "body": "🟡 **Major** — Missing null check.",
            }
        ],
    }
    payload.update(overrides)
    return payload


def test_normalize_escaped_markdown_noop_without_backslash():
    assert normalize_escaped_markdown("## PR info\n- Branch: feature") == (
        "## PR info\n- Branch: feature"
    )


def test_normalize_escaped_markdown_decodes_double_escaped_whitespace():
    leftover = "- PR info\\n  - Branch: SHSAI-2435\\n\\n- Summary\\tgap"
    assert normalize_escaped_markdown(leftover) == (
        "- PR info\n  - Branch: SHSAI-2435\n\n- Summary\tgap"
    )


def test_normalize_escaped_markdown_decodes_escaped_crlf():
    assert normalize_escaped_markdown("a\\r\\nb\\rc") == "a\nb\nc"


def test_parse_review_output_unescapes_double_escaped_overview_and_body():
    """Regression: model copies prompt `\\n` as a second JSON escape layer.

    After json.loads the overview still contains the two-character sequence
    backslash-n, which GitHub renders as a single unreadable line.
    """
    payload = {
        "overview": "- PR info\\n  - Branch: SHSAI-2435\\n  - Base: master",
        "verdict": "CHANGES_REQUESTED",
        "inline_comments": [
            {
                "path": "src/main.py",
                "line": 12,
                "body": "🟡 **Major** — Missing check.\\n\\n**What:** null.\\n**Why:** crash.",
            }
        ],
    }

    parsed = parse_review_output(json.dumps(payload))

    assert parsed is not None
    assert parsed.overview == (
        "- PR info\n  - Branch: SHSAI-2435\n  - Base: master"
    )
    assert "\\n" not in parsed.overview
    assert parsed.inline_comments[0].body == (
        "🟡 **Major** — Missing check.\n\n**What:** null.\n**Why:** crash."
    )
    assert "\\n" not in parsed.inline_comments[0].body


def test_parse_review_output_from_raw_json():
    parsed = parse_review_output(json.dumps(_sample_payload()))

    assert parsed == ParsedReview(
        overview="## Summary\nLooks mostly good.",
        verdict="CHANGES_REQUESTED",
        inline_comments=[
            InlineComment(
                path="src/main.py",
                line=12,
                body="🟡 **Major** — Missing null check.",
            )
        ],
    )


def test_parse_review_output_from_fenced_json():
    parsed = parse_review_output(
        "Here is the review:\n```json\n"
        + json.dumps(_sample_payload(verdict="APPROVE", inline_comments=[]))
        + "\n```"
    )

    assert parsed is not None
    assert parsed.verdict == "APPROVE"
    assert parsed.inline_comments == []


def test_parse_review_output_returns_none_for_invalid_json():
    assert parse_review_output("not json") is None


def test_parse_review_output_returns_none_for_missing_overview():
    assert parse_review_output(json.dumps(_sample_payload(overview=""))) is None


def test_parse_review_output_returns_none_for_invalid_verdict():
    assert parse_review_output(json.dumps(_sample_payload(verdict="MAYBE"))) is None


def test_parse_review_output_skips_invalid_inline_comments(capsys):
    parsed = parse_review_output(
        json.dumps(
            _sample_payload(
                inline_comments=[
                    {"path": "src/main.py", "line": 5, "body": "Valid"},
                    {"path": "", "line": 1, "body": "Missing path"},
                    {"line": 2, "body": "Missing path key"},
                    "not-a-dict",
                ]
            )
        )
    )

    assert parsed is not None
    assert len(parsed.inline_comments) == 1
    assert parsed.inline_comments[0].path == "src/main.py"
    assert "::warning::" in capsys.readouterr().out


def test_parse_review_output_warns_when_inline_comments_not_a_list(capsys):
    parsed = parse_review_output(json.dumps(_sample_payload(inline_comments="bad")))

    assert parsed is not None
    assert parsed.inline_comments == []
    assert "inline_comments must be a list" in capsys.readouterr().out


@pytest.mark.parametrize(
    ("verdict", "auto_approve", "expected"),
    [
        ("APPROVE", False, "COMMENT"),
        ("APPROVE", True, "APPROVE"),
        ("CHANGES_REQUESTED", False, "REQUEST_CHANGES"),
        ("CHANGES_REQUESTED", True, "REQUEST_CHANGES"),
    ],
)
def test_review_event(verdict, auto_approve, expected):
    assert review_event(verdict, auto_approve) == expected


def test_build_github_comments():
    comments = [
        InlineComment(path="a.py", line=1, body="one"),
        InlineComment(path="b.py", line=2, body="two"),
    ]

    assert build_github_comments(comments) == [
        {"path": "a.py", "line": 1, "body": "one"},
        {"path": "b.py", "line": 2, "body": "two"},
    ]


def test_filter_valid_inline_comments_keeps_known_paths(capsys):
    comments = [
        InlineComment(path="src/a.py", line=1, body="one"),
        InlineComment(path="missing.py", line=2, body="two"),
    ]

    valid = filter_valid_inline_comments(
        comments,
        [".github/workflows/pudim-code-review-labeled.yml", "src/a.py"],
    )

    assert valid == [InlineComment(path="src/a.py", line=1, body="one")]
    assert "Review model generated invalid path" in capsys.readouterr().out
