# Changelog

## 1.0.1 - 2026-10-05

- Wait for a configurable quiet period before evaluating ambient group messages that do not explicitly address the bot.
- Let newer messages replace older pending trigger boundaries while retaining them as decision context.
- Keep a configurable per-group presence window after the bot is explicitly addressed, bypassing random sampling while preserving model judgment.
- Record direct wake-ups before AstrBot's normal reply path can stop lower-priority handlers, including raw At and Reply components before the wake flag is available.
- Use Chinese labels for debug decisions and ignore reasons.
- Renew the per-group presence window whenever a decision passes the reply threshold, while ignored or low-confidence messages do not extend it.
- Explain low-confidence skips explicitly in debug logs instead of reporting them as replies.

## 1.0.0 - 2026-10-04

- Show concise setting titles with explanatory hints in AstrBot WebUI.
- Add an independently configurable ambient-message evaluation probability.
- Rename the user-facing plugin to “群聊主动回复管理” and replace technical wording with plain-language labels.
- Remove the duplicate internal enable switch; AstrBot's plugin switch is now the only enable control.
- Replace the English activity presets with a configurable reply-confidence requirement.
- Populate the decision-model field from AstrBot's configured providers.
- Split image description from reply judgment so each step can use its own provider.
- Replace the special-purpose other-bot field with a sender-only account blacklist.
- Block all reply paths for blacklisted groups and senders, including direct mentions.
- Identify the current sender explicitly when generating a reply so activity from different group members is not conflated.
- Declare OneBot v11 (`aiocqhttp`) as the supported platform.
- Remove command-prefix filtering to avoid guessing intent from ordinary chat text.
- Document every setting and distinguish plugin history from AstrBot's group-chat context.
- Add reproducible release packaging and tag-driven GitHub Releases.

## 0.1.0 - 2026-10-03

- Initial standalone repository.
- Add platform-independent ambient group-message gating.
- Add deterministic filters, per-group cooldown and in-flight suppression.
- Add configurable semantic `RESPOND / IGNORE` decision with fail-closed behavior.
- Preserve AstrBot's default path for direct mentions, replies and wake commands.
