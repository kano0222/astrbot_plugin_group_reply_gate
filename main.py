from __future__ import annotations

import asyncio
import random
from collections.abc import Iterable
from typing import Any

from astrbot.api import AstrBotConfig, logger
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.message_components import At, Image
from astrbot.api.star import Context, Star

from .gate import (
    SYSTEM_PROMPT,
    GroupGateState,
    HistoryEntry,
    build_decision_prompt,
    contains_alias,
    get_mode_policy,
    group_is_allowed,
    parse_gate_decision,
    parse_string_set,
    starts_with_ignored_prefix,
)

PLUGIN_NAME = "Group Chat Companion"


class GroupReplyGatePlugin(Star):
    def __init__(self, context: Context, config: AstrBotConfig | None = None) -> None:
        super().__init__(context)
        self.config = config if config is not None else {}
        self.state = GroupGateState()
        self._warned_builtin_active: set[str] = set()

    def _bool(self, key: str, default: bool) -> bool:
        value = self.config.get(key, default)
        if isinstance(value, bool):
            return value
        return str(value).strip().lower() in {"1", "true", "yes", "on"}

    def _int(self, key: str, default: int, *, minimum: int = 0) -> int:
        try:
            return max(minimum, int(self.config.get(key, default)))
        except (TypeError, ValueError):
            return default

    def _float(
        self,
        key: str,
        default: float,
        *,
        minimum: float,
        maximum: float,
    ) -> float:
        try:
            value = float(self.config.get(key, default))
        except (TypeError, ValueError):
            value = default
        return min(maximum, max(minimum, value))

    @staticmethod
    def _components(event: AstrMessageEvent) -> tuple[Any, ...]:
        messages = getattr(getattr(event, "message_obj", None), "message", None)
        if not isinstance(messages, Iterable) or isinstance(messages, (str, bytes)):
            return ()
        return tuple(messages)

    def _builtin_active_reply_enabled(self, event: AstrMessageEvent) -> bool:
        try:
            settings = self.context.get_config(umo=event.unified_msg_origin).get(
                "provider_ltm_settings",
                {},
            )
            active = settings.get("active_reply", {})
            return bool(active.get("enable", False))
        except Exception:
            return False

    def _group_allowed(self, event: AstrMessageEvent) -> bool:
        return group_is_allowed(
            umo=event.unified_msg_origin,
            group_id=str(event.get_group_id() or ""),
            whitelist=parse_string_set(self.config.get("group_whitelist", "")),
            blacklist=parse_string_set(self.config.get("group_blacklist", "")),
        )

    def _is_other_bot_target(self, event: AstrMessageEvent) -> bool:
        other_bot_ids = parse_string_set(self.config.get("other_bot_ids", ""))
        if not other_bot_ids:
            return False
        self_id = str(event.get_self_id() or "")
        mentioned = {
            str(component.qq)
            for component in self._components(event)
            if isinstance(component, At) and str(component.qq) not in {self_id, "all"}
        }
        return bool(mentioned & other_bot_ids)

    def _history_entry(self, event: AstrMessageEvent, has_images: bool) -> HistoryEntry:
        text = " ".join(str(event.message_str or "").split())
        if has_images:
            text = f"{text} [图片]".strip()
        return HistoryEntry(
            sender_name=event.get_sender_name() or "未知用户",
            text=text,
        )

    async def _image_paths(
        self,
        components: tuple[Any, ...],
        *,
        limit: int,
    ) -> list[str]:
        paths: list[str] = []
        for component in components:
            if not isinstance(component, Image):
                continue
            if len(paths) >= limit:
                break
            try:
                paths.append(await component.convert_to_file_path())
            except Exception:
                logger.warning(
                    f"{PLUGIN_NAME}: failed to prepare an image for decision"
                )
        return paths

    async def _classify(
        self,
        event: AstrMessageEvent,
        *,
        aliases: set[str],
        history: list[HistoryEntry],
        has_images: bool,
        image_paths: list[str],
    ):
        provider_id = str(self.config.get("decision_provider_id", "")).strip()
        if not provider_id:
            provider_id = await self.context.get_current_chat_provider_id(
                event.unified_msg_origin,
            )
        prompt = build_decision_prompt(
            bot_aliases=sorted(aliases),
            history=history,
            sender_name=event.get_sender_name() or "未知用户",
            current_text=event.message_str or "",
            has_images=has_images,
        )
        timeout = self._int("decision_timeout_seconds", 15, minimum=1)
        response = await asyncio.wait_for(
            self.context.llm_generate(
                chat_provider_id=provider_id,
                prompt=prompt,
                image_urls=image_paths,
                system_prompt=SYSTEM_PROMPT,
            ),
            timeout=timeout,
        )
        return parse_gate_decision(response.completion_text)

    def _debug(self, event: AstrMessageEvent, message: str) -> None:
        if self._bool("debug_log", False):
            logger.info(f"{PLUGIN_NAME} | {event.unified_msg_origin} | {message}")

    @filter.event_message_type(
        filter.EventMessageType.GROUP_MESSAGE,
        priority=-100,
    )
    async def gate_group_message(self, event: AstrMessageEvent):
        """对未直接唤醒机器人的群消息进行语义发言门控。"""

        if not self._group_allowed(event):
            return
        if event.is_at_or_wake_command:
            return
        if str(event.get_sender_id() or "") == str(event.get_self_id() or ""):
            return

        group_key = event.unified_msg_origin
        components = self._components(event)
        has_images = any(isinstance(component, Image) for component in components)
        history_limit = self._int("context_message_count", 10, minimum=1)
        previous_history = self.state.recent(group_key, history_limit)
        self.state.append(
            group_key,
            self._history_entry(event, has_images),
            history_limit,
        )

        if self._builtin_active_reply_enabled(event):
            if group_key not in self._warned_builtin_active:
                logger.warning(
                    f"{PLUGIN_NAME}: AstrBot built-in active reply is enabled for "
                    f"{group_key}; semantic gate is disabled there to avoid duplicates",
                )
                self._warned_builtin_active.add(group_key)
            return

        text = str(event.message_str or "").strip()
        if not text and not has_images:
            return
        if self._is_other_bot_target(event):
            self._debug(event, "IGNORE rule=other_bot_target")
            return
        if starts_with_ignored_prefix(
            text,
            parse_string_set(self.config.get("ignored_command_prefixes", "")),
        ):
            self._debug(event, "IGNORE rule=ignored_command_prefix")
            return

        cooldown = self._int("cooldown_seconds", 0)
        if self.state.cooling_down(group_key, cooldown):
            self._debug(event, "IGNORE rule=cooldown")
            return
        if not self.state.begin(group_key):
            self._debug(event, "IGNORE rule=decision_inflight")
            return

        try:
            mode = get_mode_policy(self.config.get("mode", "balanced"))
            probability_percent = self._float(
                "evaluation_probability_percent",
                mode.evaluation_probability * 100,
                minimum=0,
                maximum=100,
            )
            evaluation_probability = probability_percent / 100
            confidence_percent = self._float(
                "response_confidence_percent",
                mode.confidence_threshold * 100,
                minimum=0,
                maximum=100,
            )
            confidence_threshold = confidence_percent / 100
            aliases = parse_string_set(self.config.get("bot_aliases", ""))

            conversation_id = (
                await self.context.conversation_manager.get_curr_conversation_id(
                    event.unified_msg_origin,
                )
            )
            if not conversation_id:
                self._debug(event, "IGNORE rule=no_active_conversation")
                return
            conversation = await self.context.conversation_manager.get_conversation(
                event.unified_msg_origin,
                conversation_id,
            )
            if not conversation:
                self._debug(event, "IGNORE rule=conversation_not_found")
                return
            persona_id = str(getattr(conversation, "persona_id", "") or "").strip()
            if persona_id and persona_id not in {"default", "[%None]"}:
                aliases.add(persona_id)

            if (
                not contains_alias(text, aliases)
                and random.random() >= evaluation_probability
            ):
                self._debug(event, "IGNORE rule=activity_sampling")
                return

            image_paths: list[str] = []
            if has_images and self._bool("inspect_images", False):
                image_paths = await self._image_paths(
                    components,
                    limit=self._int("max_decision_images", 1, minimum=1),
                )

            try:
                decision = await self._classify(
                    event,
                    aliases=aliases,
                    history=previous_history,
                    has_images=has_images,
                    image_paths=image_paths,
                )
            except Exception as exc:
                logger.warning(
                    f"{PLUGIN_NAME}: decision failed closed for {group_key}: "
                    f"{type(exc).__name__}",
                )
                return

            if decision is None:
                self._debug(event, "IGNORE rule=invalid_decision")
                return
            self._debug(
                event,
                f"{decision.action} confidence={decision.confidence:.2f} "
                f"reason={decision.reason}",
            )
            if not decision.should_respond:
                return
            if decision.confidence < confidence_threshold:
                return

            main_image_paths = image_paths
            if has_images and not main_image_paths:
                main_image_paths = await self._image_paths(
                    components,
                    limit=self._int("max_decision_images", 1, minimum=1),
                )
            prompt = text or "请自然回应当前群聊中发送的图片。"
            self.state.mark_reply(group_key)
            yield event.request_llm(
                prompt=prompt,
                image_urls=main_image_paths,
                conversation=conversation,
            )
        finally:
            self.state.end(group_key)
