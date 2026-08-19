# Changelog

## v1.0.3 — 2026-08-19

### Fixed

- **Raw JSON posted as review comment when LLM emits trailing commas** — some
  models occasionally append a trailing comma after the last field of an inline
  comment object (e.g. `"body": "...",\n}`), which is invalid JSON and causes
  `json.loads` to raise `JSONDecodeError`. `parse_review_output` then returns
  `None` and the full raw JSON blob is posted as an issue comment instead of a
  structured review. A `_sanitize_json` step now strips trailing commas before
  parsing so well-formed reviews are never silently discarded.

## v1.0.2 — 2026-08-18

### Fixed

- **Action crashes when PAT owner reviews their own PR** — GitHub returns 422
  `"Review Can not request changes on your own pull request"` for
  `REQUEST_CHANGES` events on self-authored PRs. The error was previously
  uncaught (the guard only covered `APPROVE`), crashing the action with exit
  code 1. Any self-review block (both `APPROVE` and `REQUEST_CHANGES`) now
  falls back to posting a plain issue comment instead of retrying as a formal
  review.

- **Review body rendered as a single line of `\n`** — some models copy the
  prompt's JSON `\n` example as a second escape layer, so after `json.loads`
  the overview still contains the two-character sequence backslash-n. GitHub
  then shows a wall of `\n` instead of markdown. The parser now decodes leftover
  `\n` / `\t` / `\r` in `overview` and inline comment bodies, and the prompt
  now forbids double-escaping.

## v1.0.1 — 2026-08-06

### Fixed

- **Gemini (`google_genai`) support** — normalize LangChain `AIMessage.content` when it
  is returned as a list of text blocks instead of a string, which previously crashed
  JSON parsing with `TypeError: expected string or bytes-like object, got 'list'`.

### Documentation

- Added LLM provider table and Gemini workflow example to the README.
- Updated consumer example template with Gemini model notes.

## v1.0.0 — 2026-08-06

Initial release: structured PR reviews with inline comments, multi-provider LLM
support (Anthropic, OpenAI, Gemini), label-triggered workflows, optional
`auto_approve`, previous-review context, and team `additional_rules`.
