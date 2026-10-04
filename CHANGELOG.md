# Changelog

## Unreleased

- Show concise setting titles with explanatory hints in AstrBot WebUI.
- Add an independently configurable ambient-message evaluation probability.
- Rename the user-facing plugin to “群聊参与助手” and replace technical wording with plain-language labels.
- Remove the duplicate internal enable switch; AstrBot's plugin switch is now the only enable control.
- Replace the English activity presets with a configurable reply-confidence requirement.
- Populate the decision-model field from AstrBot's configured providers.
- Avoid treating longer ASCII words such as `www` as commands when `ww` is configured.
- Document every setting and distinguish plugin history from AstrBot's group-chat context.

## 0.1.0 - 2026-10-03

- Initial standalone repository.
- Add platform-independent ambient group-message gating.
- Add deterministic filters, per-group cooldown and in-flight suppression.
- Add configurable semantic `RESPOND / IGNORE` decision with fail-closed behavior.
- Preserve AstrBot's default path for direct mentions, replies and wake commands.
