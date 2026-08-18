import json
from unittest.mock import MagicMock, patch

import pytest
from github import GithubException

from graph.review_parser import InlineComment, ParsedReview
from review import (
    REVIEW_MARKER,
    VERDICT_SUFFIX,
    approval_not_permitted,
    build_graph,
    format_previous_reviews,
    format_pr_context,
    get_previous_reviews,
    get_pr_diff,
    get_review_commit,
    main,
    parse_auto_approve,
    post_inline_comments,
    post_issue_comment,
    post_pull_request_review,
    publish_review,
    remove_trigger_label,
    requests_changes,
    resolve_commit_sha,
    should_remove_trigger_label,
    write_github_output,
)


def test_requests_changes_detects_verdict():
    assert requests_changes("CHANGES_REQUESTED")
    assert not requests_changes("APPROVE")
    assert requests_changes("Looks good.\nVERDICT: CHANGES_REQUESTED")
    assert not requests_changes("Looks good.\nVERDICT: APPROVE")


def test_requests_changes_detects_phrases():
    assert requests_changes("Please request changes on the auth module.")
    assert requests_changes("Summary: changes requested before merge.")
    assert requests_changes("This changes required before we can ship.")
    assert requests_changes("The API needs changes to match the spec.")
    assert not requests_changes("LGTM, ship it.")


def test_requests_changes_verdict_is_case_insensitive():
    assert requests_changes("verdict: changes_requested")
    assert requests_changes("Verdict: CHANGES_REQUESTED")


def test_should_remove_trigger_label_modes():
    review = "VERDICT: CHANGES_REQUESTED"
    assert should_remove_trigger_label("changes_requested", review)
    assert should_remove_trigger_label("always", "VERDICT: APPROVE")
    assert not should_remove_trigger_label("never", review)
    assert not should_remove_trigger_label("changes_requested", "VERDICT: APPROVE")


def test_parse_auto_approve():
    assert parse_auto_approve("false") is False
    assert parse_auto_approve("true") is True
    assert parse_auto_approve("1") is True
    assert parse_auto_approve("") is False


def test_approval_not_permitted_detects_github_actions_restriction():
    exc = GithubException(
        422,
        {"message": "Unprocessable Entity", "errors": ["GitHub Actions is not permitted to approve pull requests."]},
    )

    assert approval_not_permitted(exc)


def test_approval_not_permitted_ignores_other_errors():
    exc = GithubException(422, {"message": "batch failed", "errors": ["Path could not be resolved"]})

    assert not approval_not_permitted(exc)


def test_approval_not_permitted_ignores_non_422_status():
    exc = GithubException(403, {"message": "Forbidden"})

    assert not approval_not_permitted(exc)


def test_post_pull_request_review_reraises_when_no_comments_and_not_approval_error(mock_gh):
    pr = MagicMock()
    fake_commit = MagicMock()
    mock_gh.get_repo.return_value.get_commit.return_value = fake_commit
    parsed = ParsedReview(overview="Summary", verdict="APPROVE", inline_comments=[])
    pr.create_review.side_effect = GithubException(500, {"message": "server error"})

    with pytest.raises(GithubException):
        post_pull_request_review(
            pr,
            parsed,
            "abc123",
            mock_gh,
            "luismr/some-repo",
            [],
            auto_approve=True,
        )


def test_approval_not_permitted_detects_self_approval_block():
    exc = GithubException(
        422,
        {"message": "Unprocessable Entity", "errors": ["Review Can not approve your own pull request"]},
    )

    assert approval_not_permitted(exc)


def test_approval_not_permitted_detects_self_request_changes_block():
    exc = GithubException(
        422,
        {"message": "Unprocessable Entity", "errors": ["Review Can not request changes on your own pull request"]},
    )

    assert approval_not_permitted(exc)


def test_resolve_commit_sha_prefers_event_payload():
    pr = MagicMock()
    pr.head.sha = "from-pr"
    event = {"pull_request": {"head": {"sha": "from-event"}}}

    assert resolve_commit_sha(event, pr) == "from-event"


def test_resolve_commit_sha_falls_back_to_pr_head():
    pr = MagicMock()
    pr.head.sha = "from-pr"

    assert resolve_commit_sha({}, pr) == "from-pr"


def test_format_pr_context():
    pr = MagicMock()
    pr.number = 42
    pr.title = "Add widget"
    pr.head.ref = "feature/widget"
    pr.base.ref = "main"

    context = format_pr_context(
        pr,
        "abc123def",
        [".github/workflows/pudim-code-review-labeled.yml"],
    )

    assert "PR number: 42" in context
    assert "Title: Add widget" in context
    assert "Head branch: feature/widget" in context
    assert "Base branch: main" in context
    assert "Head commit SHA: abc123def" in context
    assert "Changed files:" in context
    assert "- .github/workflows/pudim-code-review-labeled.yml" in context


def test_get_previous_reviews_filters_by_marker():
    pr = MagicMock()
    ours = MagicMock(body=f"{REVIEW_MARKER}\n\nNeeds work.")
    other = MagicMock(body="Looks good to me.")
    pr.get_reviews.return_value = [other, ours]

    reviews = get_previous_reviews(pr)

    assert reviews == [ours]


def test_format_previous_reviews_when_none():
    assert format_previous_reviews([]) == "Previous reviews from this action: none\n"


def test_format_previous_reviews_includes_metadata():
    from datetime import datetime, timezone

    review = MagicMock()
    review.state = "CHANGES_REQUESTED"
    review.commit_id = "abc123def456"
    review.submitted_at = datetime(2026, 8, 5, 20, 0, tzinfo=timezone.utc)
    review.body = f"{REVIEW_MARKER}\n\nFix the workflow docs."

    formatted = format_previous_reviews([review])

    assert "Previous reviews from this action:" in formatted
    assert "Review #1 (CHANGES_REQUESTED, commit abc123d" in formatted
    assert "Fix the workflow docs." in formatted


def test_get_review_commit(mock_gh):
    commit = get_review_commit(mock_gh, "luismr/some-repo", "abc123")

    mock_gh.get_repo.assert_called_once_with("luismr/some-repo")
    mock_gh.get_repo.return_value.get_commit.assert_called_once_with("abc123")
    assert commit is mock_gh.get_repo.return_value.get_commit.return_value


def test_remove_trigger_label_calls_github(mock_gh):
    issue = MagicMock()
    mock_gh.get_repo.return_value.get_issue.return_value = issue

    remove_trigger_label(mock_gh, "luismr/some-repo", 42, "pudim-code-review")

    mock_gh.get_repo.assert_called_once_with("luismr/some-repo")
    mock_gh.get_repo.return_value.get_issue.assert_called_once_with(42)
    issue.remove_from_labels.assert_called_once_with("pudim-code-review")


def test_remove_trigger_label_ignores_missing_label(mock_gh):
    issue = MagicMock()
    issue.remove_from_labels.side_effect = GithubException(404, {"message": "not found"})
    mock_gh.get_repo.return_value.get_issue.return_value = issue

    remove_trigger_label(mock_gh, "luismr/some-repo", 42, "pudim-code-review")

    issue.remove_from_labels.assert_called_once_with("pudim-code-review")


def test_get_pr_diff_joins_patches(mock_gh):
    pr = MagicMock()
    file_a = MagicMock(filename="src/a.py", patch="diff a")
    file_b = MagicMock(filename="src/b.py", patch=None)
    pr.get_files.return_value = [file_a, file_b]
    mock_gh.get_repo.return_value.get_pull.return_value = pr

    diff, returned_pr, changed_files = get_pr_diff(mock_gh, "luismr/some-repo", 42)

    assert diff == "### File: src/a.py\ndiff a\n\n### File: src/b.py\n(no patch)"
    assert changed_files == ["src/a.py", "src/b.py"]
    assert returned_pr is pr
    mock_gh.get_repo.assert_called_once_with("luismr/some-repo")
    mock_gh.get_repo.return_value.get_pull.assert_called_once_with(42)


def test_build_graph_compiles():
    app = build_graph()
    assert app is not None
    assert hasattr(app, "invoke")


def test_post_inline_comments():
    pr = MagicMock()
    comments = [InlineComment(path="src/a.py", line=4, body="Fix this")]

    post_inline_comments(pr, comments, "abc123")

    pr.create_review_comment.assert_called_once_with(
        body="Fix this",
        commit="abc123",
        path="src/a.py",
        line=4,
    )


def test_post_inline_comments_ignores_individual_failures(capsys):
    pr = MagicMock()
    pr.create_review_comment.side_effect = GithubException(422, {"message": "invalid line"})
    comments = [InlineComment(path="src/a.py", line=4, body="Fix this")]

    post_inline_comments(pr, comments, "abc123")

    assert "::warning::Failed inline comment" in capsys.readouterr().out


def test_post_pull_request_review_with_inline_comments(mock_gh):
    pr = MagicMock()
    fake_commit = MagicMock()
    mock_gh.get_repo.return_value.get_commit.return_value = fake_commit
    parsed = ParsedReview(
        overview="Summary",
        verdict="CHANGES_REQUESTED",
        inline_comments=[InlineComment(path="src/a.py", line=4, body="Fix this")],
    )

    verdict = post_pull_request_review(
        pr,
        parsed,
        "abc123",
        mock_gh,
        "luismr/some-repo",
        ["src/a.py"],
    )

    assert verdict == "CHANGES_REQUESTED"
    pr.create_review.assert_called_once_with(
        body="## Blueprint Pudim Code Review\n\nSummary",
        event="REQUEST_CHANGES",
        commit=fake_commit,
        comments=[{"path": "src/a.py", "line": 4, "body": "Fix this"}],
    )


def test_post_pull_request_review_filters_unknown_paths(mock_gh, capsys):
    pr = MagicMock()
    fake_commit = MagicMock()
    mock_gh.get_repo.return_value.get_commit.return_value = fake_commit
    parsed = ParsedReview(
        overview="Summary",
        verdict="CHANGES_REQUESTED",
        inline_comments=[
            InlineComment(path="wrong/path.yml", line=4, body="Fix this"),
        ],
    )

    post_pull_request_review(
        pr,
        parsed,
        "abc123",
        mock_gh,
        "luismr/some-repo",
        [".github/workflows/pudim-code-review-labeled.yml"],
    )

    pr.create_review.assert_called_once_with(
        body="## Blueprint Pudim Code Review\n\nSummary",
        event="REQUEST_CHANGES",
        commit=fake_commit,
    )
    assert "Review model generated invalid path" in capsys.readouterr().out


def test_post_pull_request_review_without_inline_comments(mock_gh):
    pr = MagicMock()
    fake_commit = MagicMock()
    mock_gh.get_repo.return_value.get_commit.return_value = fake_commit
    parsed = ParsedReview(overview="Summary", verdict="APPROVE", inline_comments=[])

    verdict = post_pull_request_review(
        pr,
        parsed,
        "abc123",
        mock_gh,
        "luismr/some-repo",
        [],
        auto_approve=False,
    )

    assert verdict == "APPROVE"
    pr.create_review.assert_called_once_with(
        body="## Blueprint Pudim Code Review\n\nSummary",
        event="COMMENT",
        commit=fake_commit,
    )


def test_post_pull_request_review_auto_approves_when_enabled(mock_gh):
    pr = MagicMock()
    fake_commit = MagicMock()
    mock_gh.get_repo.return_value.get_commit.return_value = fake_commit
    parsed = ParsedReview(overview="Summary", verdict="APPROVE", inline_comments=[])

    post_pull_request_review(
        pr,
        parsed,
        "abc123",
        mock_gh,
        "luismr/some-repo",
        [".github/workflows/pudim-code-review-labeled.yml"],
        auto_approve=True,
    )

    pr.create_review.assert_called_once_with(
        body="## Blueprint Pudim Code Review\n\nSummary",
        event="APPROVE",
        commit=fake_commit,
    )


def test_post_pull_request_review_falls_back_to_issue_comment_when_approval_not_permitted(
    mock_gh, capsys
):
    pr = MagicMock()
    fake_commit = MagicMock()
    mock_gh.get_repo.return_value.get_commit.return_value = fake_commit
    parsed = ParsedReview(overview="Summary", verdict="APPROVE", inline_comments=[])
    pr.create_review.side_effect = GithubException(
        422,
        {
            "message": "Unprocessable Entity",
            "errors": ["GitHub Actions is not permitted to approve pull requests."],
        },
    )

    verdict = post_pull_request_review(
        pr,
        parsed,
        "abc123",
        mock_gh,
        "luismr/some-repo",
        [],
        auto_approve=True,
    )

    assert verdict == "APPROVE"
    assert pr.create_review.call_count == 1
    pr.create_issue_comment.assert_called_once()
    assert "Blueprint Pudim Code Review" in pr.create_issue_comment.call_args[0][0]
    assert "Cannot submit GitHub PR review with this token" in capsys.readouterr().out


def test_post_pull_request_review_falls_back_to_issue_comment_when_request_changes_not_permitted(
    mock_gh, capsys
):
    pr = MagicMock()
    fake_commit = MagicMock()
    mock_gh.get_repo.return_value.get_commit.return_value = fake_commit
    parsed = ParsedReview(overview="Summary", verdict="CHANGES_REQUESTED", inline_comments=[])
    pr.create_review.side_effect = GithubException(
        422,
        {
            "message": "Unprocessable Entity",
            "errors": ["Review Can not request changes on your own pull request"],
        },
    )

    verdict = post_pull_request_review(
        pr,
        parsed,
        "abc123",
        mock_gh,
        "luismr/some-repo",
        [],
    )

    assert verdict == "CHANGES_REQUESTED"
    assert pr.create_review.call_count == 1
    pr.create_issue_comment.assert_called_once()
    assert "Blueprint Pudim Code Review" in pr.create_issue_comment.call_args[0][0]
    assert "Cannot submit GitHub PR review with this token" in capsys.readouterr().out


def test_post_pull_request_review_falls_back_to_individual_comments(mock_gh, capsys):
    pr = MagicMock()
    fake_commit = MagicMock()
    mock_gh.get_repo.return_value.get_commit.return_value = fake_commit
    parsed = ParsedReview(
        overview="Summary",
        verdict="CHANGES_REQUESTED",
        inline_comments=[InlineComment(path="src/a.py", line=4, body="Fix this")],
    )
    pr.create_review.side_effect = [
        GithubException(422, {"message": "batch failed"}),
        None,
    ]

    verdict = post_pull_request_review(
        pr,
        parsed,
        "abc123",
        mock_gh,
        "luismr/some-repo",
        ["src/a.py"],
    )

    assert verdict == "CHANGES_REQUESTED"
    pr.create_review_comment.assert_called_once_with(
        body="Fix this",
        commit="abc123",
        path="src/a.py",
        line=4,
    )
    assert pr.create_review.call_count == 2
    assert "Batch review failed" in capsys.readouterr().out


def test_post_issue_comment():
    pr = MagicMock()
    post_issue_comment(pr, "Legacy review body")
    pr.create_issue_comment.assert_called_once_with(
        "## Blueprint Pudim Code Review\n\nLegacy review body"
    )


def test_publish_review_uses_structured_output(mock_gh):
    pr = MagicMock()
    payload = {
        "commit_id": "abc123",
        "overview": "Overview only",
        "verdict": "APPROVE",
        "inline_comments": [],
    }

    with patch("review.post_pull_request_review", return_value="APPROVE") as mock_post:
        result = publish_review(
            pr, json.dumps(payload), "abc123", mock_gh, "luismr/some-repo", []
        )

    assert result == "APPROVE"
    mock_post.assert_called_once()
    pr.create_issue_comment.assert_not_called()


def test_publish_review_falls_back_to_issue_comment():
    pr = MagicMock()

    result = publish_review(
        pr, "Plain text review", "abc123", MagicMock(), "luismr/some-repo", []
    )

    assert result == "Plain text review"
    pr.create_issue_comment.assert_called_once()
    pr.create_review.assert_not_called()


def test_write_github_output_writes_review_and_commit(monkeypatch, tmp_path):
    output_path = tmp_path / "output.txt"
    monkeypatch.setenv("GITHUB_OUTPUT", str(output_path))

    write_github_output("Review body", "abc123")

    written = output_path.read_text()
    assert "review<<EOF" in written
    assert "Review body" in written
    assert "commit_sha=abc123" in written


def test_main_posts_structured_review(monkeypatch, tmp_path):
    event = {"number": 7, "pull_request": {"head": {"sha": "event-sha"}}}
    event_path = tmp_path / "event.json"
    event_path.write_text(json.dumps(event))

    monkeypatch.setenv("GITHUB_TOKEN", "fake-token")
    monkeypatch.setenv("GITHUB_REPOSITORY", "luismr/some-repo")
    monkeypatch.setenv("GITHUB_EVENT_PATH", str(event_path))
    monkeypatch.delenv("GITHUB_OUTPUT", raising=False)

    fake_pr = MagicMock()
    fake_pr.number = 7
    fake_pr.title = "Test PR"
    fake_pr.head.ref = "feature/test"
    fake_pr.head.sha = "pr-sha"
    fake_pr.base.ref = "main"
    previous_review = MagicMock()
    previous_review.state = "CHANGES_REQUESTED"
    previous_review.commit_id = "oldsha1"
    previous_review.submitted_at = None
    previous_review.body = f"{REVIEW_MARKER}\n\nFix docs."
    fake_pr.get_reviews.return_value = [previous_review]
    structured = json.dumps(
        {
            "commit_id": "event-sha",
            "overview": "All good.",
            "verdict": "APPROVE",
            "inline_comments": [
                {"path": "src/a.py", "line": 1, "body": "Nice refactor."},
            ],
        }
    )

    with patch("review.Auth.Token", return_value="fake-auth") as mock_auth, \
         patch("review.Github") as mock_github_cls, \
         patch("review.get_pr_diff") as mock_get_diff, \
         patch("review.build_graph") as mock_build_graph, \
         patch("review.publish_review") as mock_publish_review:

        mock_get_diff.return_value = ("some diff", fake_pr, ["src/a.py"])
        mock_build_graph.return_value.invoke.return_value = {"result": structured}
        mock_publish_review.return_value = "APPROVE"

        main()

        mock_auth.assert_called_once_with("fake-token")
        mock_github_cls.assert_called_once_with(auth="fake-auth")
        invoke_args = mock_build_graph.return_value.invoke.call_args[0][0]
        assert "Head commit SHA: event-sha" in invoke_args["context"]
        assert "Previous reviews from this action:" in invoke_args["context"]
        assert "Fix docs." in invoke_args["context"]
        mock_publish_review.assert_called_once_with(
            fake_pr,
            structured,
            "event-sha",
            mock_github_cls.return_value,
            "luismr/some-repo",
            ["src/a.py"],
            auto_approve=False,
        )


def test_main_posts_comment_without_output_file(monkeypatch, tmp_path):
    event = {"number": 7}
    event_path = tmp_path / "event.json"
    event_path.write_text(json.dumps(event))

    monkeypatch.setenv("GITHUB_TOKEN", "fake-token")
    monkeypatch.setenv("GITHUB_REPOSITORY", "luismr/some-repo")
    monkeypatch.setenv("GITHUB_EVENT_PATH", str(event_path))
    monkeypatch.delenv("GITHUB_OUTPUT", raising=False)

    fake_pr = MagicMock()
    fake_pr.number = 7
    fake_pr.title = "Test PR"
    fake_pr.head.ref = "feature/test"
    fake_pr.head.sha = "abc123"
    fake_pr.base.ref = "main"
    fake_pr.get_reviews.return_value = []

    with patch("review.Auth.Token", return_value="fake-auth") as mock_auth, \
         patch("review.Github") as mock_github_cls, \
         patch("review.get_pr_diff") as mock_get_diff, \
         patch("review.build_graph") as mock_build_graph:

        mock_get_diff.return_value = ("some diff", fake_pr, ["src/a.py"])
        mock_build_graph.return_value.invoke.return_value = {"result": "All good."}

        main()

        mock_auth.assert_called_once_with("fake-token")
        mock_github_cls.assert_called_once_with(auth="fake-auth")
        fake_pr.create_issue_comment.assert_called_once()
        comment_body = fake_pr.create_issue_comment.call_args[0][0]
        assert "All good." in comment_body
        assert "Blueprint Pudim Code Review" in comment_body


def test_main_removes_trigger_label_when_changes_requested(monkeypatch, tmp_path):
    event = {"number": 7, "pull_request": {"head": {"sha": "abc123"}}}
    event_path = tmp_path / "event.json"
    event_path.write_text(json.dumps(event))

    monkeypatch.setenv("GITHUB_TOKEN", "fake-token")
    monkeypatch.setenv("GITHUB_REPOSITORY", "luismr/some-repo")
    monkeypatch.setenv("GITHUB_EVENT_PATH", str(event_path))
    monkeypatch.setenv("TRIGGER_LABEL", "pudim-code-review")
    monkeypatch.setenv("REMOVE_TRIGGER_LABEL", "changes_requested")

    fake_pr = MagicMock()
    fake_pr.number = 7
    fake_pr.title = "Test PR"
    fake_pr.head.ref = "feature/test"
    fake_pr.head.sha = "abc123"
    fake_pr.base.ref = "main"
    fake_issue = MagicMock()
    structured = json.dumps(
        {
            "commit_id": "abc123",
            "overview": "Needs work.",
            "verdict": "CHANGES_REQUESTED",
            "inline_comments": [],
        }
    )

    with patch("review.Github") as mock_github_cls, \
         patch("review.get_pr_diff") as mock_get_diff, \
         patch("review.build_graph") as mock_build_graph, \
         patch("review.post_pull_request_review", return_value="CHANGES_REQUESTED"):

        mock_get_diff.return_value = ("some diff", fake_pr, ["src/a.py"])
        mock_build_graph.return_value.invoke.return_value = {"result": structured}
        mock_github_cls.return_value.get_repo.return_value.get_issue.return_value = fake_issue

        main()

        fake_issue.remove_from_labels.assert_called_once_with("pudim-code-review")


def test_main_keeps_trigger_label_when_approved(monkeypatch, tmp_path):
    event = {"number": 7, "pull_request": {"head": {"sha": "abc123"}}}
    event_path = tmp_path / "event.json"
    event_path.write_text(json.dumps(event))

    monkeypatch.setenv("GITHUB_TOKEN", "fake-token")
    monkeypatch.setenv("GITHUB_REPOSITORY", "luismr/some-repo")
    monkeypatch.setenv("GITHUB_EVENT_PATH", str(event_path))
    monkeypatch.setenv("TRIGGER_LABEL", "pudim-code-review")
    monkeypatch.setenv("REMOVE_TRIGGER_LABEL", "changes_requested")

    fake_pr = MagicMock()
    fake_pr.number = 7
    fake_pr.title = "Test PR"
    fake_pr.head.ref = "feature/test"
    fake_pr.head.sha = "abc123"
    fake_pr.base.ref = "main"
    fake_issue = MagicMock()
    structured = json.dumps(
        {
            "commit_id": "abc123",
            "overview": "All good.",
            "verdict": "APPROVE",
            "inline_comments": [],
        }
    )

    with patch("review.Github") as mock_github_cls, \
         patch("review.get_pr_diff") as mock_get_diff, \
         patch("review.build_graph") as mock_build_graph, \
         patch("review.post_pull_request_review", return_value="APPROVE"):

        mock_get_diff.return_value = ("some diff", fake_pr, ["src/a.py"])
        mock_build_graph.return_value.invoke.return_value = {"result": structured}
        mock_github_cls.return_value.get_repo.return_value.get_issue.return_value = fake_issue

        main()

        fake_issue.remove_from_labels.assert_not_called()


def test_main_removes_trigger_label_when_mode_is_always(monkeypatch, tmp_path):
    event = {"number": 7}
    event_path = tmp_path / "event.json"
    event_path.write_text(json.dumps(event))

    monkeypatch.setenv("GITHUB_TOKEN", "fake-token")
    monkeypatch.setenv("GITHUB_REPOSITORY", "luismr/some-repo")
    monkeypatch.setenv("GITHUB_EVENT_PATH", str(event_path))
    monkeypatch.setenv("TRIGGER_LABEL", "pudim-code-review")
    monkeypatch.setenv("REMOVE_TRIGGER_LABEL", "always")

    fake_pr = MagicMock()
    fake_pr.number = 7
    fake_pr.title = "Test PR"
    fake_pr.head.ref = "feature/test"
    fake_pr.head.sha = "abc123"
    fake_pr.base.ref = "main"
    fake_issue = MagicMock()

    with patch("review.Github") as mock_github_cls, \
         patch("review.get_pr_diff") as mock_get_diff, \
         patch("review.build_graph") as mock_build_graph, \
         patch("review.post_pull_request_review", return_value="APPROVE"):

        mock_get_diff.return_value = ("some diff", fake_pr, ["src/a.py"])
        mock_build_graph.return_value.invoke.return_value = {
            "result": "All good.\nVERDICT: APPROVE",
        }
        mock_github_cls.return_value.get_repo.return_value.get_issue.return_value = fake_issue

        main()

        fake_issue.remove_from_labels.assert_called_once_with("pudim-code-review")


def test_main_keeps_trigger_label_when_mode_is_never(monkeypatch, tmp_path):
    event = {"number": 7}
    event_path = tmp_path / "event.json"
    event_path.write_text(json.dumps(event))

    monkeypatch.setenv("GITHUB_TOKEN", "fake-token")
    monkeypatch.setenv("GITHUB_REPOSITORY", "luismr/some-repo")
    monkeypatch.setenv("GITHUB_EVENT_PATH", str(event_path))
    monkeypatch.setenv("TRIGGER_LABEL", "pudim-code-review")
    monkeypatch.setenv("REMOVE_TRIGGER_LABEL", "never")

    fake_pr = MagicMock()
    fake_pr.number = 7
    fake_pr.title = "Test PR"
    fake_pr.head.ref = "feature/test"
    fake_pr.head.sha = "abc123"
    fake_pr.base.ref = "main"
    fake_issue = MagicMock()

    with patch("review.Github") as mock_github_cls, \
         patch("review.get_pr_diff") as mock_get_diff, \
         patch("review.build_graph") as mock_build_graph, \
         patch("review.post_pull_request_review", return_value="CHANGES_REQUESTED"):

        mock_get_diff.return_value = ("some diff", fake_pr, ["src/a.py"])
        mock_build_graph.return_value.invoke.return_value = {
            "result": "Fix the tests.\nVERDICT: CHANGES_REQUESTED",
        }
        mock_github_cls.return_value.get_repo.return_value.get_issue.return_value = fake_issue

        main()

        fake_issue.remove_from_labels.assert_not_called()


def test_main_appends_verdict_suffix_when_trigger_label_set(monkeypatch, tmp_path):
    event = {"number": 7}
    event_path = tmp_path / "event.json"
    event_path.write_text(json.dumps(event))

    monkeypatch.setenv("GITHUB_TOKEN", "fake-token")
    monkeypatch.setenv("GITHUB_REPOSITORY", "luismr/some-repo")
    monkeypatch.setenv("GITHUB_EVENT_PATH", str(event_path))
    monkeypatch.setenv("TRIGGER_LABEL", "pudim-code-review")

    fake_pr = MagicMock()
    fake_pr.number = 7
    fake_pr.title = "Test PR"
    fake_pr.head.ref = "feature/test"
    fake_pr.head.sha = "abc123"
    fake_pr.base.ref = "main"

    with patch("review.Github"), \
         patch("review.get_pr_diff") as mock_get_diff, \
         patch("review.load_prompt", return_value="Base prompt"), \
         patch("review.build_graph") as mock_build_graph, \
         patch("review.publish_review", return_value="Done."):

        mock_get_diff.return_value = ("some diff", fake_pr, ["src/a.py"])
        mock_build_graph.return_value.invoke.return_value = {"result": "Done."}

        main()

        invoke_args = mock_build_graph.return_value.invoke.call_args[0][0]
        assert invoke_args["prompt"] == f"Base prompt{VERDICT_SUFFIX}"


def test_main_writes_github_output_when_present(monkeypatch, tmp_path):
    event = {"number": 3, "pull_request": {"head": {"sha": "out-sha"}}}
    event_path = tmp_path / "event.json"
    event_path.write_text(json.dumps(event))

    output_path = tmp_path / "output.txt"

    monkeypatch.setenv("GITHUB_TOKEN", "fake-token")
    monkeypatch.setenv("GITHUB_REPOSITORY", "luismr/some-repo")
    monkeypatch.setenv("GITHUB_EVENT_PATH", str(event_path))
    monkeypatch.setenv("GITHUB_OUTPUT", str(output_path))

    fake_pr = MagicMock()
    fake_pr.number = 3
    fake_pr.title = "Test PR"
    fake_pr.head.ref = "feature/test"
    fake_pr.head.sha = "out-sha"
    fake_pr.base.ref = "main"

    with patch("review.Github"), \
         patch("review.get_pr_diff") as mock_get_diff, \
         patch("review.build_graph") as mock_build_graph:

        mock_get_diff.return_value = ("some diff", fake_pr, ["src/a.py"])
        mock_build_graph.return_value.invoke.return_value = {"result": "Fine."}

        main()

        written = output_path.read_text()
        assert "review<<EOF" in written
        assert "Fine." in written
        assert "commit_sha=out-sha" in written
        assert "EOF" in written
