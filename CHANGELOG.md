# Changelog

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
