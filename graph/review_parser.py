import json
import re
from dataclasses import dataclass


@dataclass(frozen=True)
class InlineComment:
    path: str
    line: int
    body: str


@dataclass(frozen=True)
class ParsedReview:
    overview: str
    verdict: str
    inline_comments: list[InlineComment]


def _extract_json(text: str) -> str:
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL | re.IGNORECASE)
    if fenced:
        return fenced.group(1)

    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        return text[start : end + 1]

    raise ValueError("No JSON object found")


def _parse_inline_comment(raw: object) -> InlineComment | None:
    if not isinstance(raw, dict):
        print(f"::warning::Skipping invalid inline comment: {raw}")
        return None

    try:
        path = str(raw["path"]).strip()
        line = int(raw["line"])
        body = str(raw["body"]).strip()
    except (KeyError, TypeError, ValueError):
        print(f"::warning::Skipping invalid inline comment: {raw}")
        return None

    if not path or not body or line < 1:
        print(f"::warning::Skipping invalid inline comment: {raw}")
        return None

    return InlineComment(path=path, line=line, body=body)


def parse_review_output(text: str) -> ParsedReview | None:
    try:
        payload = json.loads(_extract_json(text))
    except (ValueError, json.JSONDecodeError):
        return None

    overview = str(payload.get("overview", "")).strip()
    verdict = str(payload.get("verdict", "")).strip().upper()
    if not overview or verdict not in {"APPROVE", "CHANGES_REQUESTED"}:
        return None

    inline_comments: list[InlineComment] = []
    raw_comments = payload.get("inline_comments", [])
    if not isinstance(raw_comments, list):
        print(f"::warning::inline_comments must be a list, got: {type(raw_comments).__name__}")
        raw_comments = []

    for raw in raw_comments:
        comment = _parse_inline_comment(raw)
        if comment:
            inline_comments.append(comment)

    return ParsedReview(
        overview=overview,
        verdict=verdict,
        inline_comments=inline_comments,
    )


def review_event(verdict: str, auto_approve: bool = False) -> str:
    if verdict.upper() == "APPROVE":
        return "APPROVE" if auto_approve else "COMMENT"
    return "REQUEST_CHANGES"


def filter_valid_inline_comments(
    comments: list[InlineComment],
    changed_files: list[str],
) -> list[InlineComment]:
    valid_paths = set(changed_files)
    valid: list[InlineComment] = []
    for comment in comments:
        if comment.path in valid_paths:
            valid.append(comment)
        else:
            print(
                f"::warning::Skipping inline comment with unknown path "
                f"{comment.path!r}; changed files: {', '.join(changed_files)}"
            )
    return valid


def build_github_comments(comments: list[InlineComment]) -> list[dict[str, object]]:
    return [
        {"path": comment.path, "line": comment.line, "body": comment.body}
        for comment in comments
    ]
