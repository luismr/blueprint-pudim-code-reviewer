import json
import os
import re

from github import Github, GithubException
from langgraph.graph import END, StateGraph

from graph.nodes import review_node
from graph.prompt_loader import load_prompt
from graph.review_parser import (
    InlineComment,
    ParsedReview,
    build_github_comments,
    parse_review_output,
    review_event,
)
from graph.state import ReviewState

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


def format_pr_context(pr, commit_sha: str) -> str:
    return (
        f"PR number: {pr.number}\n"
        f"Title: {pr.title}\n"
        f"Head branch: {pr.head.ref}\n"
        f"Base branch: {pr.base.ref}\n"
        f"Head commit SHA: {commit_sha}\n"
    )


def get_pr_diff(gh: Github, repo_name: str, pr_number: int):
    repo = gh.get_repo(repo_name)
    pr = repo.get_pull(pr_number)
    diff = "\n".join(f.patch or "" for f in pr.get_files())
    return diff, pr


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
    auto_approve: bool = False,
) -> str:
    body = f"## Blueprint Pudim Code Review\n\n{parsed.overview}"
    commit = get_review_commit(gh, repo_name, commit_sha)
    comments = build_github_comments(parsed.inline_comments)
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
        post_inline_comments(pr, parsed.inline_comments, commit_sha)
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
    auto_approve: bool = False,
) -> str:
    parsed = parse_review_output(review_text)
    if parsed:
        return post_pull_request_review(
            pr, parsed, commit_sha, gh, repo_name, auto_approve=auto_approve
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
    gh = Github(os.environ["GITHUB_TOKEN"])
    repo_name = os.environ["GITHUB_REPOSITORY"]
    event_path = os.environ["GITHUB_EVENT_PATH"]

    with open(event_path, encoding="utf-8") as handle:
        event = json.load(handle)
    pr_number = event["number"]

    diff, pr = get_pr_diff(gh, repo_name, pr_number)
    commit_sha = resolve_commit_sha(event, pr)
    context = format_pr_context(pr, commit_sha)
    prompt = load_prompt()

    trigger_label = os.environ.get("TRIGGER_LABEL", "")
    if trigger_label:
        prompt = f"{prompt}{VERDICT_SUFFIX}"

    app = build_graph()
    result = app.invoke({"diff": diff, "prompt": prompt, "context": context, "result": ""})
    review_text = result["result"]
    auto_approve = parse_auto_approve(os.environ.get("AUTO_APPROVE", "false"))

    label_decision_text = publish_review(
        pr, review_text, commit_sha, gh, repo_name, auto_approve=auto_approve
    )

    remove_mode = os.environ.get("REMOVE_TRIGGER_LABEL", "changes_requested")
    if trigger_label and should_remove_trigger_label(remove_mode, label_decision_text):
        remove_trigger_label(gh, repo_name, pr_number, trigger_label)

    write_github_output(review_text, commit_sha)


if __name__ == "__main__":
    main()
