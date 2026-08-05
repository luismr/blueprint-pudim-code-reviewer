"""
Resolves the review prompt using a fallback chain:

1. Inline `prompt` input (REVIEW_PROMPT env var)
2. Local file in the consumer repo (PROMPT_FILE env var)
3. Remote file fetched from another GitHub repo (PROMPT_REPO / PROMPT_REPO_PATH / PROMPT_REPO_REF)
4. Built-in default string
"""

import os

from github import Github

DEFAULT_PROMPT = "Review this diff for bugs, security issues, and style problems."


def _build_remote_client(base_gh: Github) -> Github:
    """Use a dedicated token for the prompt repo if one was supplied,
    otherwise reuse the client passed in (typically authenticated with
    the consumer repo's GITHUB_TOKEN)."""
    remote_token = os.environ.get("PROMPT_REPO_TOKEN", "").strip()
    if remote_token:
        return Github(remote_token)
    return base_gh


def load_prompt(gh: Github) -> str:
    # 1. Explicit inline override
    inline = os.environ.get("REVIEW_PROMPT", "").strip()
    if inline:
        return inline

    # 2. Local file in the consumer repo
    local_path = os.environ.get("PROMPT_FILE", "").strip()
    if local_path and os.path.exists(local_path):
        return open(local_path, encoding="utf-8").read()

    # 3. Remote file from another repo
    remote_repo = os.environ.get("PROMPT_REPO", "").strip()
    if remote_repo:
        remote_path = os.environ.get("PROMPT_REPO_PATH", "CLAUDE_REVIEW.md")
        remote_ref = os.environ.get("PROMPT_REPO_REF", "main")
        try:
            client = _build_remote_client(gh)
            repo = client.get_repo(remote_repo)
            content_file = repo.get_contents(remote_path, ref=remote_ref)
            return content_file.decoded_content.decode("utf-8")
        except Exception as e:
            print(f"::warning::Could not fetch prompt from {remote_repo}: {e}")

    # 4. Built-in fallback
    return DEFAULT_PROMPT
