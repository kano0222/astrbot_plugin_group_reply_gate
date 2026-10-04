# Collaboration Guidelines

## Project boundaries

- Keep changes scoped to this plugin by default. Do not modify AstrBot core or another plugin unless the user explicitly expands the task; if the problem belongs there, explain that instead of hiding it behind a local workaround.
- Direct mentions, replies to the bot, and explicit wake-ups belong to AstrBot's normal reply path. This plugin gates ambient group-chat participation, while its configured group and account blacklists may stop an event before the normal path.
- Treat silence as the safe fallback for ambient participation. Classifier failures, timeouts, malformed output, or unresolved uncertainty must not produce an unsolicited reply.
- Do not log full group-chat content, credentials, provider responses, private URLs, or image URLs.
- Keep persona behavior outside the plugin. Avoid unnecessary platform coupling, and keep `metadata.yaml` compatibility declarations aligned with behavior that is actually supported and tested.

## Engineering approach

- Read the relevant implementation, tests, and AstrBot APIs before changing behavior. A requested implementation may point to the wrong layer; when it does, explain the mismatch and prefer the smaller, more appropriate solution.
- Use public AstrBot APIs where practical and follow the repository's existing structure, naming, and dependencies.
- Keep changes focused and reviewable. Avoid unrelated refactors, speculative abstractions, and compatibility mechanisms without a concrete use case.
- For low-risk, reversible local changes, use reasonable engineering judgment without asking for approval at every step. Ask only when missing information would materially change behavior, risk, or scope.
- Update user documentation and `metadata.yaml` when user-visible behavior or declared compatibility changes.

## Validation

- Add or update focused tests when behavior changes. Choose checks based on the affected files and risk rather than running unrelated work mechanically.
- The standard checks for Python behavior changes are:

  ```powershell
  python -m pytest -q
  ruff check .
  ruff format --check .
  git diff --check
  ```

- Documentation-only changes normally require `git diff --check` plus any existing documentation-specific checks. Do not add a new lint dependency solely for one edit.
- Report what was actually validated and identify any relevant check that could not be run.

## Repository side effects

- Do not commit, push, publish, create a release or remote repository, or otherwise modify remote state without explicit authorization.
- Preserve unrelated user changes in the working tree. Do not use destructive Git or filesystem commands to simplify cleanup.
