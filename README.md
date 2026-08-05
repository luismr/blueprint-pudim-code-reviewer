# blueprint-pudim-code-reviewer

[![Tests](https://github.com/luismr/blueprint-pudim-code-reviewer/actions/workflows/test.yml/badge.svg)](https://github.com/luismr/blueprint-pudim-code-reviewer/actions/workflows/test.yml)
[![Coverage](https://img.shields.io/badge/coverage-100%25-brightgreen)](https://github.com/luismr/blueprint-pudim-code-reviewer/actions/workflows/test.yml)
[![Python 3.13](https://img.shields.io/badge/python-3.13-blue)](https://www.python.org/downloads/release/python-3130/)
[![License: MIT](https://img.shields.io/badge/license-MIT-lightgrey)](LICENSE)
[![Marketplace](https://img.shields.io/badge/marketplace-blueprint--pudim--code--reviewer-2ea44f?logo=github)](https://github.com/marketplace/actions/blueprint-pudim-code-reviewer)

A GitHub Action that reviews pull request diffs using a swappable LLM backend
(Anthropic, OpenAI, or Gemini) via LangGraph/LangChain's model abstraction.

## Requirements

- Python **3.13**
- pip

## Local development setup

### 1. Install Python 3.13

Check what you have first:

```bash
python3 --version
```

If you don't have 3.13 yet:

**macOS (Homebrew)**
```bash
brew install python@3.13
```

**Ubuntu / Debian**
```bash
sudo add-apt-repository ppa:deadsnakes/ppa
sudo apt update
sudo apt install python3.13 python3.13-venv
```

**Windows**
Download the installer from [python.org/downloads](https://www.python.org/downloads/release/python-3130/)
and make sure "Add python.exe to PATH" is checked during install.

### 2. Create the virtual environment

From the repo root:

```bash
python3.13 -m venv .venv
```

This creates a `.venv/` folder containing an isolated Python 3.13 interpreter
and its own `site-packages`, so project dependencies never touch your system
Python.

### 3. Activate it

**macOS / Linux**
```bash
source .venv/bin/activate
```

**Windows (PowerShell)**
```powershell
.venv\Scripts\Activate.ps1
```

**Windows (cmd.exe)**
```cmd
.venv\Scripts\activate.bat
```

Your shell prompt should now be prefixed with `(.venv)`. Confirm you're
pointed at the right interpreter:

```bash
python --version   # should print Python 3.13.x
which python        # (or `where python` on Windows) should point inside .venv/
```

### 4. Install dependencies

Runtime dependencies only:
```bash
pip install -r requirements.txt
```

For development/testing (this pulls in `requirements.txt` automatically,
plus pytest and coverage tooling):
```bash
pip install -r requirements-dev.txt
```

### 5. Deactivate when done

```bash
deactivate
```

## Running tests

With the venv active:

```bash
pytest --cov --cov-report=term-missing
```

Coverage is configured in `pyproject.toml` with `fail_under = 100`, so the
command exits non-zero if any line or branch isn't exercised.

## Recreating the environment from scratch

If dependencies drift or something breaks:

```bash
deactivate            # if currently active
rm -rf .venv
python3.13 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements-dev.txt
```

## Usage in a workflow

Add a workflow file under `.github/workflows/` in the **consumer** repository
(the repo whose PRs you want reviewed). Store your provider API key as a
repository secret (e.g. `ANTHROPIC_API_KEY`).

See `action.yml` for the full list of inputs and their defaults.

The action always starts from the built-in review workflow in
[`prompts/default_review.md`](prompts/default_review.md). Optionally append
team-specific rules with `additional_rules` (inline) or
`additional_rules_file` (path in the consumer repo — requires
`actions/checkout` first). Rules replace the default placeholder after Step 2;
when none are provided, the built-in placeholder is kept as-is.

The model returns JSON with `commit_id` (head SHA for inline comments),
`overview` (core review summary posted as the PR review body), `inline_comments`
(per-line findings), and `verdict` (`APPROVE` or `CHANGES_REQUESTED`). The action
exposes the commit used for posting as the `commit_sha` output.

By default, `auto_approve` is `false`: an `APPROVE` verdict is posted as a
comment-only review and does **not** approve the PR. Set `auto_approve: true`
to submit a real GitHub approval when the verdict is `APPROVE`.

**Note:** GitHub Actions' default `GITHUB_TOKEN` **cannot approve pull
requests** — if `auto_approve: true` with the default token, the action posts a
comment-only review instead and logs a warning. Use a personal access token (PAT)
with pull-request write access for real approvals.

#### `auto_approve` in this repo (Option B)

This repository uses **Option B** in its dogfood workflow
([`.github/workflows/pudim-code-review-labeled.yml`](.github/workflows/pudim-code-review-labeled.yml)):

```yaml
# auto_approve: true — requires a PAT from a separate bot account (not the PR author).
auto_approve: true
github_token: ${{ secrets.PUDIM_GITHUB_PAT != '' && secrets.PUDIM_GITHUB_PAT || github.token }}
```

`auto_approve: true` is **enabled for this repo's reviews** on purpose. Two GitHub
rules prevent automatic approval today:

1. **`GITHUB_TOKEN` cannot approve PRs** in Actions (falls back to comment-only).
2. **A PAT owned by the PR author cannot approve their own PR** — even with a PAT,
   reviews on PRs you open yourself stay comment-only unless the token belongs to a
   **separate bot account** with pull-request write access.

Add repository secret **`PUDIM_GITHUB_PAT`** from a dedicated bot user to get real
approvals. The dogfood workflow uses it automatically when present.

| Option | `auto_approve` | Token | Result on APPROVE verdict |
|---|---|---|---|
| **A** (safer default) | `false` | `GITHUB_TOKEN` | Comment-only review |
| **B** (this repo, no PAT yet) | `true` | `GITHUB_TOKEN` | Comment-only review (automatic fallback + warning) |
| **B + bot PAT** | `true` | `PUDIM_GITHUB_PAT` (non-author account) | Real GitHub PR approval |

Most consumer repos should start with **Option A** (`auto_approve: false`).
Switch to **Option B with a PAT** when you want the bot to actually approve PRs.
See [`examples/pudim-code-review-labeled.yml`](examples/pudim-code-review-labeled.yml)
for both options documented in the template header.

### Choosing a workflow variant

| Variant | Trigger | Best for |
|---|---|---|
| **Every new PR** | `opened`, `synchronize`, `reopened` | Continuous review on every push |
| **Label-triggered** | `pudim-code-review` label applied | Opt-in reviews; re-add label after fixes |

Copy the labeled example from [`examples/pudim-code-review-labeled.yml`](examples/pudim-code-review-labeled.yml).
This repo dogfoods the same workflow from
[`.github/workflows/pudim-code-review-labeled.yml`](.github/workflows/pudim-code-review-labeled.yml)
using `uses: ./` instead of the published action, with **Option B**
(`auto_approve: true`) enabled for this repo's reviews.

### Model and settings

| Setting | Recommendation |
|---|---|
| **Model** | `claude-sonnet-4-6` for nuanced, high-quality reviews. Use `claude-haiku-4-5` when cost or latency matters more than depth. |
| **`auto_approve`** | **Option B** (`true`) in this repo's dogfood workflow — falls back to comment-only with `GITHUB_TOKEN`. Consumer repos: start with **Option A** (`false`) or use **Option B + PAT** for real approvals. |
| **`remove_trigger_label`** | `changes_requested` (default) removes the label after a changes-requested verdict so re-reviews are opt-in. Use `always` or `never` to change that behavior. |
| **`additional_rules`** | Inline markdown appended to the built-in prompt (e.g. team coding standards). |
| **`additional_rules_file`** | Path to a rules file in the consumer repo (requires `actions/checkout`). |

### Review every new PR

Runs on every pull request when it is opened, updated, or reopened.
`auto_approve` defaults to `false` here — a conservative choice for continuous
review on every push.

```yaml
# .github/workflows/pudim-code-review.yml
name: Pudim Code Review

on:
  pull_request:
    types: [opened, synchronize, reopened]

permissions:
  contents: read
  pull-requests: write

jobs:
  review:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: luismr/blueprint-pudim-code-reviewer@v1
        with:
          provider: anthropic
          model: claude-sonnet-4-6
          api_key: ${{ secrets.ANTHROPIC_API_KEY }}
          github_token: ${{ secrets.GITHUB_TOKEN }}
          additional_rules_file: .github/pudim-review-rules.md
          # additional_rules: |
          #   - Flag missing tests for auth changes
          #   - Require migration notes for schema changes
```

### Review only PRs labeled `pudim-code-review`

Runs when a PR gets the label. When the review requests changes, the action
removes the label automatically so the next review is opt-in: fix the code,
then add `pudim-code-review` again when you are ready for another pass.

**Minimal example — Option A** (comment-only approvals, recommended for most repos):

```yaml
# .github/workflows/pudim-code-review-labeled.yml
name: Pudim Code Review (labeled)

on:
  pull_request:
    types: [labeled]

permissions:
  contents: read
  pull-requests: write
  issues: write

jobs:
  review:
    if: github.event.label.name == 'pudim-code-review'
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: luismr/blueprint-pudim-code-reviewer@v1
        with:
          provider: anthropic
          model: claude-sonnet-4-6
          api_key: ${{ secrets.ANTHROPIC_API_KEY }}
          github_token: ${{ secrets.GITHUB_TOKEN }}
          auto_approve: false
          trigger_label: pudim-code-review
          remove_trigger_label: changes_requested
```

**Option B — with `GITHUB_TOKEN`** (falls back to comment-only; same as this repo):

```yaml
      - uses: luismr/blueprint-pudim-code-reviewer@v1
        with:
          provider: anthropic
          model: claude-sonnet-4-6
          api_key: ${{ secrets.ANTHROPIC_API_KEY }}
          github_token: ${{ secrets.GITHUB_TOKEN }}
          auto_approve: true
          trigger_label: pudim-code-review
          remove_trigger_label: changes_requested
```

**Option B — real GitHub approvals** (requires a PAT secret):

```yaml
      - uses: luismr/blueprint-pudim-code-reviewer@v1
        with:
          provider: anthropic
          model: claude-sonnet-4-6
          api_key: ${{ secrets.ANTHROPIC_API_KEY }}
          github_token: ${{ secrets.PUDIM_GITHUB_PAT }}
          auto_approve: true
          trigger_label: pudim-code-review
          remove_trigger_label: changes_requested
```

**Faster/cheaper model** (Haiku instead of Sonnet):

```yaml
      - uses: luismr/blueprint-pudim-code-reviewer@v1
        with:
          provider: anthropic
          model: claude-haiku-4-5
          api_key: ${{ secrets.ANTHROPIC_API_KEY }}
          github_token: ${{ secrets.GITHUB_TOKEN }}
          auto_approve: false
          trigger_label: pudim-code-review
```

**Full example** with team rules (matches [`examples/pudim-code-review-labeled.yml`](examples/pudim-code-review-labeled.yml)):

```yaml
# .github/workflows/pudim-code-review-labeled.yml
name: Pudim Code Review (labeled)

on:
  pull_request:
    types: [labeled]

permissions:
  contents: read
  pull-requests: write
  issues: write

jobs:
  review:
    if: github.event.label.name == 'pudim-code-review'
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: luismr/blueprint-pudim-code-reviewer@v1
        with:
          provider: anthropic
          model: claude-sonnet-4-6
          api_key: ${{ secrets.ANTHROPIC_API_KEY }}
          github_token: ${{ secrets.GITHUB_TOKEN }}
          auto_approve: true
          additional_rules: |
            Treat missing observability on new endpoints as Major.
            Require rollback notes for production config changes.
          trigger_label: pudim-code-review
          remove_trigger_label: changes_requested
```

Set `remove_trigger_label: always` to drop the label after every review
(approved or not). Set `never` to keep the label.

**Re-review loop**

1. Add the `pudim-code-review` label when you want a review.
2. The action runs and posts feedback with `verdict: APPROVE` or
   `verdict: CHANGES_REQUESTED` (plus inline comments on changed lines).
3. When changes are requested, the label is removed automatically.
4. Address the feedback and push your fixes.
5. Add the label again — the model receives prior reviews from this action in
   context and should include a **Previous review follow-up** section.

Because the label is removed after a changes-requested verdict, incidental
pushes do not re-trigger the reviewer. Only a fresh label application starts
a new review.

## Contributing

Contributions are welcome via the standard fork-and-pull-request workflow:

1. **Fork** this repo by clicking "Fork" at the top of the
   [GitHub page](https://github.com/luismr/blueprint-pudim-code-reviewer).

2. **Clone your fork** locally:
   ```bash
   git clone https://github.com/luismr/blueprint-pudim-code-reviewer.git
   cd blueprint-pudim-code-reviewer
   ```

3. **Set up the dev environment** — follow the
   [venv setup instructions](#local-development-setup) above.

4. **Create a feature branch**:
   ```bash
   git checkout -b feature/short-description
   ```

5. **Make your changes**, keeping tests and coverage green:
   ```bash
   pytest --cov --cov-report=term-missing
   ```
   New code should come with tests — the project enforces `fail_under = 100`
   in `pyproject.toml`, so a PR that drops coverage below 100% will fail CI.

6. **Commit and push** to your fork:
   ```bash
   git add .
   git commit -m "Add: short description of the change"
   git push origin feature/short-description
   ```

7. **Open a pull request** from your fork's branch into
   `luismr/blueprint-pudim-code-reviewer:main`. Describe what changed and why,
   and link any related issues.

8. A maintainer will review, may request changes, and will merge once CI
   passes and the review is approved.

### Guidelines

- Keep PRs focused — one logical change per PR is easier to review.
- Match the existing code style (see `graph/` for conventions).
- Update the README if you add/change inputs, providers, or behavior.
- Be respectful and constructive in review discussions.

## Author

**Luis Machado Reis** — Strategic Software Architect

- 🌐 Portfolio & more projects: [luismachadoreis.dev](https://luismachadoreis.dev)
- 🐙 GitHub: [@luismr](https://github.com/luismr)

For deeper background on the architecture patterns and tooling philosophy
behind this project, check out the write-ups on
[luismachadoreis.dev](https://luismachadoreis.dev).
