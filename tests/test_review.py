import json
from unittest.mock import MagicMock, patch

from review import build_graph, get_pr_diff, main


def test_get_pr_diff_joins_patches(mock_gh):
    pr = MagicMock()
    file_a = MagicMock(patch="diff a")
    file_b = MagicMock(patch=None)  # covers the `f.patch or ""` fallback
    pr.get_files.return_value = [file_a, file_b]
    mock_gh.get_repo.return_value.get_pull.return_value = pr

    diff, returned_pr = get_pr_diff(mock_gh, "luismr/some-repo", 42)

    assert diff == "diff a\n"
    assert returned_pr is pr
    mock_gh.get_repo.assert_called_once_with("luismr/some-repo")
    mock_gh.get_repo.return_value.get_pull.assert_called_once_with(42)


def test_build_graph_compiles():
    app = build_graph()
    assert app is not None
    assert hasattr(app, "invoke")


def test_main_posts_comment_without_output_file(monkeypatch, tmp_path):
    event = {"number": 7}
    event_path = tmp_path / "event.json"
    event_path.write_text(json.dumps(event))

    monkeypatch.setenv("GITHUB_TOKEN", "fake-token")
    monkeypatch.setenv("GITHUB_REPOSITORY", "luismr/some-repo")
    monkeypatch.setenv("GITHUB_EVENT_PATH", str(event_path))
    monkeypatch.setenv("REVIEW_PROMPT", "Review it")
    monkeypatch.delenv("GITHUB_OUTPUT", raising=False)

    fake_pr = MagicMock()

    with patch("review.Github") as mock_github_cls, \
         patch("review.get_pr_diff") as mock_get_diff, \
         patch("review.build_graph") as mock_build_graph:

        mock_get_diff.return_value = ("some diff", fake_pr)
        mock_build_graph.return_value.invoke.return_value = {"result": "All good."}

        main()

        mock_github_cls.assert_called_once_with("fake-token")
        fake_pr.create_issue_comment.assert_called_once()
        comment_body = fake_pr.create_issue_comment.call_args[0][0]
        assert "All good." in comment_body
        assert "Blueprint Pudim Code Review" in comment_body


def test_main_writes_github_output_when_present(monkeypatch, tmp_path):
    event = {"number": 3}
    event_path = tmp_path / "event.json"
    event_path.write_text(json.dumps(event))

    output_path = tmp_path / "output.txt"

    monkeypatch.setenv("GITHUB_TOKEN", "fake-token")
    monkeypatch.setenv("GITHUB_REPOSITORY", "luismr/some-repo")
    monkeypatch.setenv("GITHUB_EVENT_PATH", str(event_path))
    monkeypatch.setenv("REVIEW_PROMPT", "Review it")
    monkeypatch.setenv("GITHUB_OUTPUT", str(output_path))

    fake_pr = MagicMock()

    with patch("review.Github"), \
         patch("review.get_pr_diff") as mock_get_diff, \
         patch("review.build_graph") as mock_build_graph:

        mock_get_diff.return_value = ("some diff", fake_pr)
        mock_build_graph.return_value.invoke.return_value = {"result": "Fine."}

        main()

        written = output_path.read_text()
        assert "review<<EOF" in written
        assert "Fine." in written
        assert "EOF" in written
