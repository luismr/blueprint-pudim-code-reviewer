import json
import os
import re

from github import Auth, Github, GithubException
from langgraph.graph import END, StateGraph

from graph.nodes import review_node
from graph.prompt_loader import load_prompt
from graph.review_parser import (
    InlineComment,
    ParsedReview,
    build_github_comments,
    filter_valid_inline_comments,
    parse_review_output,
    review_event,
)
from graph.state import ReviewState

REVIEW_MARKER = "## Blueprint Pudim Code Review"

VERDICT_SUFFIX = (
    "\n\nEnd your review with a final line in this exact format: "
    "VERDICT: APPROVE or VERDICT: CHANGES_REQUESTED"
)


def requests_changes(review_text: str) -> bool:
    normalized = review_text.strip().upper()
    if normalized == "CHANGES_REQUESTED":
        return True
    if normalized == "APPROVE":
        return False

    if re.search(r"VERDICT:\s*CHANGES_REQUESTED", review_text, re.IGNORECASE):
        return True
    lower = review_text.lower()
    return any(
        phrase in lower
        for phrase in (
            "changes requested",
            "request changes",
            "changes required",
            "needs changes",
        )
    )


def should_remove_trigger_label(mode: str, review_text: str) -> bool:
    if mode == "never":
        return False
    if mode == "always":
        return True
    return requests_changes(review_text)


def remove_trigger_label(gh: Github, repo_name: str, pr_number: int, label: str) -> None:
    issue = gh.get_repo(repo_name).get_issue(pr_number)
    try:
        issue.remove_from_labels(label)
    except GithubException:
        pass


def resolve_commit_sha(event: dict, pr) -> str:
    event_sha = event.get("pull_request", {}).get("head", {}).get("sha")
    if event_sha:
        return event_sha
    return pr.head.sha


def format_pr_context(pr, commit_sha: str, changed_files: list[str]) -> str:
    files_list = "\n".join(f"- {path}" for path in changed_files)
    return (
        f"PR number: {pr.number}\n"
        f"Title: {pr.title}\n"
        f"Head branch: {pr.head.ref}\n"
        f"Base branch: {pr.base.ref}\n"
        f"Head commit SHA: {commit_sha}\n"
        f"Changed files:\n{files_list}\n"
    )


def get_previous_reviews(pr) -> list:
    return [
        review
        for review in pr.get_reviews()
        if REVIEW_MARKER in (review.body or "")
    ]


def format_previous_reviews(reviews: list) -> str:
    if not reviews:
        return "Previous reviews from this action: none\n"

    parts = ["Previous reviews from this action:"]
    for index, review in enumerate(reviews, start=1):
        state = review.state or "UNKNOWN"
        commit = (review.commit_id or "unknown")[:7]
        submitted = review.submitted_at.isoformat() if review.submitted_at else "unknown"
        body = review.body or ""
        parts.append(
            f"\n--- Review #{index} ({state}, commit {commit}, {submitted}) ---\n{body}"
        )
    return "\n".join(parts) + "\n"


def get_pr_diff(gh: Github, repo_name: str, pr_number: int):
    repo = gh.get_repo(repo_name)
    pr = repo.get_pull(pr_number)
    changed_files: list[str] = []
    parts: list[str] = []
    for file in pr.get_files():
        changed_files.append(file.filename)
        patch = file.patch or "(no patch)"
        parts.append(f"### File: {file.filename}\n{patch}")
    diff = "\n\n".join(parts)
    return diff, pr, changed_files


def get_review_commit(gh: Github, repo_name: str, commit_sha: str):
    return gh.get_repo(repo_name).get_commit(commit_sha)


def build_graph():
    graph = StateGraph(ReviewState)
    graph.add_node("review", review_node)
    graph.set_entry_point("review")
    graph.add_edge("review", END)
    return graph.compile()


def post_inline_comments(pr, comments: list[InlineComment], commit_sha: str) -> None:
    for comment in comments:
        try:
            pr.create_review_comment(
                body=comment.body,
                commit=commit_sha,
                path=comment.path,
                line=comment.line,
            )
        except GithubException as exc:
            print(
                f"::warning::Failed inline comment on {comment.path}:{comment.line}: {exc}"
            )


def parse_auto_approve(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "on"}


def post_pull_request_review(
    pr,
    parsed: ParsedReview,
    commit_sha: str,
    gh: Github,
    repo_name: str,
    changed_files: list[str],
    auto_approve: bool = False,
) -> str:
    body = f"## Blueprint Pudim Code Review\n\n{parsed.overview}"
    commit = get_review_commit(gh, repo_name, commit_sha)
    valid_comments = filter_valid_inline_comments(parsed.inline_comments, changed_files)
    comments = build_github_comments(valid_comments)
    review_kwargs = {
        "body": body,
        "event": review_event(parsed.verdict, auto_approve),
        "commit": commit,
    }

    try:
        if comments:
            pr.create_review(**review_kwargs, comments=comments)
        else:
            pr.create_review(**review_kwargs)
    except GithubException as exc:
        print(f"::warning::Batch review failed, posting inline comments individually: {exc}")
        post_inline_comments(pr, valid_comments, commit_sha)
        pr.create_review(**review_kwargs)

    return parsed.verdict


def post_issue_comment(pr, review_text: str) -> None:
    comment_body = f"## Blueprint Pudim Code Review\n\n{review_text}"
    pr.create_issue_comment(comment_body)


def publish_review(
    pr,
    review_text: str,
    commit_sha: str,
    gh: Github,
    repo_name: str,
    changed_files: list[str],
    auto_approve: bool = False,
) -> str:
    parsed = parse_review_output(review_text)
    if parsed:
        return post_pull_request_review(
            pr,
            parsed,
            commit_sha,
            gh,
            repo_name,
            changed_files,
            auto_approve=auto_approve,
        )
    post_issue_comment(pr, review_text)
    return review_text


def write_github_output(review_text: str, commit_sha: str) -> None:
    output_path = os.environ.get("GITHUB_OUTPUT")
    if not output_path:
        return

    with open(output_path, "a", encoding="utf-8") as handle:
        handle.write(f"review<<EOF\n{review_text}\nEOF\n")
        handle.write(f"commit_sha={commit_sha}\n")


def main():
    gh = Github(auth=Auth.Token(os.environ["GITHUB_TOKEN"]))
    repo_name = os.environ["GITHUB_REPOSITORY"]
    event_path = os.environ["GITHUB_EVENT_PATH"]

    with open(event_path, encoding="utf-8") as handle:
        event = json.load(handle)
    pr_number = event["number"]

    diff, pr, changed_files = get_pr_diff(gh, repo_name, pr_number)
    commit_sha = resolve_commit_sha(event, pr)
    context = format_pr_context(pr, commit_sha, changed_files)
    context = f"{context}\n{format_previous_reviews(get_previous_reviews(pr))}"
    prompt = load_prompt()

    trigger_label = os.environ.get("TRIGGER_LABEL", "")
    if trigger_label:
        prompt = f"{prompt}{VERDICT_SUFFIX}"

    app = build_graph()
    result = app.invoke({"diff": diff, "prompt": prompt, "context": context, "result": ""})
    review_text = result["result"]
    auto_approve = parse_auto_approve(os.environ.get("AUTO_APPROVE", "false"))

    label_decision_text = publish_review(
        pr, review_text, commit_sha, gh, repo_name, changed_files, auto_approve=auto_approve
    )

    remove_mode = os.environ.get("REMOVE_TRIGGER_LABEL", "changes_requested")
    if trigger_label and should_remove_trigger_label(remove_mode, label_decision_text):
        remove_trigger_label(gh, repo_name, pr_number, trigger_label)

    write_github_output(review_text, commit_sha)


if __name__ == "__main__":
    main()
