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

```yaml
- uses: luismr/blueprint-pudim-code-reviewer@v1
  with:
    provider: anthropic          # anthropic | openai | google_genai
    model: claude-sonnet-4-6     # or gpt-4.1, gemini-2.5-pro
    api_key: ${{ secrets.ANTHROPIC_API_KEY }}
    prompt_repo: luismr/review-standards   # optional org-wide default prompt
```

See `action.yml` for the full list of inputs and their defaults.

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
