# Collaboration Guidelines

- Keep this plugin platform-independent and persona-independent.
- Do not modify AstrBot core or other plugins as part of changes here.
- Treat silence as the safe fallback: classifier failures, timeouts, and malformed output must not produce a message.
- Direct mentions and replies to the bot remain owned by AstrBot's normal reply path; this plugin only gates ambient group-chat participation.
- Do not log full group-chat content, credentials, provider responses, or image URLs.
- Prefer public AstrBot APIs and keep compatibility declarations in `metadata.yaml` accurate.
- New behavior requires focused tests. Run `python -m pytest -q`, `ruff check .`, `ruff format --check .`, and `git diff --check` before handoff when available.
- Do not commit, push, publish, or create remote repositories without explicit authorization.
