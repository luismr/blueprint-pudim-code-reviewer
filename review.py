import json
import os

from github import Github
from langgraph.graph import END, StateGraph

from graph.nodes import review_node
from graph.prompt_loader import load_prompt
from graph.state import ReviewState


def get_pr_diff(gh: Github, repo_name: str, pr_number: int):
    repo = gh.get_repo(repo_name)
    pr = repo.get_pull(pr_number)
    diff = "\n".join(f.patch or "" for f in pr.get_files())
    return diff, pr


def build_graph():
    graph = StateGraph(ReviewState)
    graph.add_node("review", review_node)
    graph.set_entry_point("review")
    graph.add_edge("review", END)
    return graph.compile()


def main():
    gh = Github(os.environ["GITHUB_TOKEN"])
    repo_name = os.environ["GITHUB_REPOSITORY"]
    event_path = os.environ["GITHUB_EVENT_PATH"]

    with open(event_path, encoding="utf-8") as f:
        event = json.load(f)
    pr_number = event["number"]

    diff, pr = get_pr_diff(gh, repo_name, pr_number)
    prompt = load_prompt(gh)

    app = build_graph()
    result = app.invoke({"diff": diff, "prompt": prompt, "result": ""})

    comment_body = f"## Blueprint Pudim Code Review\n\n{result['result']}"
    pr.create_issue_comment(comment_body)

    output_path = os.environ.get("GITHUB_OUTPUT")
    if output_path:
        with open(output_path, "a", encoding="utf-8") as f:
            f.write(f"review<<EOF\n{result['result']}\nEOF\n")


if __name__ == "__main__":
    main()
