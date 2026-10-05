from __future__ import annotations

import asyncio
from types import SimpleNamespace

from astrbot.api.message_components import At
from astrbot_plugin_group_reply_gate.gate import GateDecision
from astrbot_plugin_group_reply_gate.main import GroupReplyGatePlugin


class FakeConversationManager:
    def __init__(self, conversation=None) -> None:
        self.conversation = conversation

    async def get_curr_conversation_id(self, umo: str):
        return "cid" if self.conversation else None

    async def get_conversation(self, umo: str, conversation_id: str):
        return self.conversation


class FakeContext:
    def __init__(self, *, builtin_active: bool = False, conversation=None) -> None:
        self.builtin_active = builtin_active
        self.conversation_manager = FakeConversationManager(conversation)
        self.llm_calls = []
        self.llm_responses = {}

    def get_config(self, *, umo: str):
        return {
            "provider_ltm_settings": {"active_reply": {"enable": self.builtin_active}},
            "provider_settings": {"default_image_caption_provider_id": ""},
        }

    async def get_current_chat_provider_id(self, umo: str):
        return "current-model"

    async def llm_generate(self, **kwargs):
        self.llm_calls.append(kwargs)
        return SimpleNamespace(
            completion_text=self.llm_responses[kwargs["chat_provider_id"]]
        )


class FakeEvent:
    def __init__(
        self,
        text: str = "普通消息",
        *,
        direct: bool = False,
        group_id: str = "1",
        sender_id: str = "user",
        sender_name: str = "测试用户",
        components: list | None = None,
    ) -> None:
        self.message_str = text
        self.is_at_or_wake_command = direct
        self.group_id = group_id
        self.sender_id = sender_id
        self.sender_name = sender_name
        self.unified_msg_origin = f"default:GroupMessage:{group_id}"
        self.message_obj = SimpleNamespace(message=components or [])
        self.stopped = False

    def get_group_id(self):
        return self.group_id

    def get_sender_id(self):
        return self.sender_id

    def get_self_id(self):
        return "bot"

    def get_sender_name(self):
        return self.sender_name

    def stop_event(self):
        self.stopped = True

    def request_llm(self, **kwargs):
        return kwargs


async def collect(async_generator) -> list:
    return [item async for item in async_generator]


def make_plugin(*, builtin_active: bool = False, conversation=None):
    return GroupReplyGatePlugin(
        FakeContext(
            builtin_active=builtin_active,
            conversation=conversation,
        ),
        {
            "bot_aliases": "Denia",
            "cooldown_seconds": 0,
            "quiet_period_seconds": 0,
        },
    )


def test_direct_messages_are_left_to_astrbot() -> None:
    plugin = make_plugin()
    event = FakeEvent("@Denia 你好", direct=True)
    assert asyncio.run(collect(plugin.gate_group_message(event))) == []
    assert plugin.state.recent(event.unified_msg_origin, 10) == []


def test_builtin_active_reply_disables_gate_to_prevent_duplicates() -> None:
    plugin = make_plugin(builtin_active=True)
    event = FakeEvent("Denia 你怎么看")
    assert asyncio.run(collect(plugin.gate_group_message(event))) == []
    assert len(plugin.state.recent(event.unified_msg_origin, 10)) == 1


def test_ignore_decision_sends_nothing_and_releases_inflight() -> None:
    conversation = SimpleNamespace(persona_id="daniya_agent")
    plugin = make_plugin(conversation=conversation)
    event = FakeEvent("Denia 你怎么看")

    async def classify(*args, **kwargs):
        return GateDecision("IGNORE", 0.95, "无需参与")

    plugin._classify = classify
    assert asyncio.run(collect(plugin.gate_group_message(event))) == []
    assert plugin.state.begin(event.unified_msg_origin)


def test_respond_decision_uses_current_conversation() -> None:
    conversation = SimpleNamespace(persona_id="daniya_agent")
    plugin = make_plugin(conversation=conversation)
    event = FakeEvent("Denia 你怎么看")

    async def classify(*args, **kwargs):
        assert "daniya_agent" in kwargs["aliases"]
        return GateDecision("RESPOND", 0.95, "明确征求意见")

    plugin._classify = classify
    results = asyncio.run(collect(plugin.gate_group_message(event)))
    assert len(results) == 1
    assert "昵称：测试用户" in results[0]["prompt"]
    assert "账号：user" in results[0]["prompt"]
    assert "当前消息：Denia 你怎么看" in results[0]["prompt"]
    assert results[0]["conversation"] is conversation


def test_consecutive_senders_are_identified_separately() -> None:
    conversation = SimpleNamespace(persona_id="daniya_agent")
    plugin = make_plugin(conversation=conversation)

    async def classify(*args, **kwargs):
        return GateDecision("RESPOND", 0.95, "明确叫到机器人")

    plugin._classify = classify
    first = FakeEvent(
        "Denia？",
        sender_id="100",
        sender_name="甲",
    )
    second = FakeEvent(
        "Denia 你怎么看",
        sender_id="200",
        sender_name="乙",
    )

    first_result = asyncio.run(collect(plugin.gate_group_message(first)))
    second_result = asyncio.run(collect(plugin.gate_group_message(second)))

    assert "昵称：甲" in first_result[0]["prompt"]
    assert "账号：100" in first_result[0]["prompt"]
    assert "昵称：乙" in second_result[0]["prompt"]
    assert "账号：200" in second_result[0]["prompt"]
    assert "昵称：甲" not in second_result[0]["prompt"]
    assert "账号：100" not in second_result[0]["prompt"]


def test_newer_message_replaces_pending_ambient_boundary() -> None:
    async def exercise() -> tuple[list, list]:
        conversation = SimpleNamespace(persona_id="daniya_agent")
        plugin = make_plugin(conversation=conversation)
        plugin.config["quiet_period_seconds"] = 0.02
        plugin.config["evaluation_probability_percent"] = 100
        classified_texts: list[str] = []

        async def classify(event, *args, **kwargs):
            classified_texts.append(event.message_str)
            return GateDecision("RESPOND", 0.95, "明确征求意见")

        plugin._classify = classify
        first = FakeEvent("这个好像不太对", sender_id="100", sender_name="甲")
        second = FakeEvent("你们觉得应该怎么改", sender_id="200", sender_name="乙")

        first_task = asyncio.create_task(collect(plugin.gate_group_message(first)))
        await asyncio.sleep(0)
        second_task = asyncio.create_task(collect(plugin.gate_group_message(second)))
        first_result, second_result = await asyncio.gather(first_task, second_task)

        assert classified_texts == ["你们觉得应该怎么改"]
        return first_result, second_result

    first_result, second_result = asyncio.run(exercise())
    assert first_result == []
    assert len(second_result) == 1
    assert "昵称：乙" in second_result[0]["prompt"]
    assert "当前消息：你们觉得应该怎么改" in second_result[0]["prompt"]


def test_configured_alias_bypasses_quiet_period() -> None:
    async def exercise() -> list:
        conversation = SimpleNamespace(persona_id="daniya_agent")
        plugin = make_plugin(conversation=conversation)
        plugin.config["quiet_period_seconds"] = 10

        async def classify(*args, **kwargs):
            return GateDecision("RESPOND", 0.95, "明确叫到机器人")

        plugin._classify = classify
        event = FakeEvent("Denia 你怎么看")
        return await asyncio.wait_for(
            collect(plugin.gate_group_message(event)),
            timeout=0.1,
        )

    assert len(asyncio.run(exercise())) == 1


def test_direct_wake_makes_following_ambient_message_skip_sampling() -> None:
    async def exercise() -> list:
        conversation = SimpleNamespace(persona_id="daniya_agent")
        plugin = make_plugin(conversation=conversation)
        plugin.config.update(
            {
                "evaluation_probability_percent": 0,
                "presence_seconds": 120,
            }
        )

        async def classify(*args, **kwargs):
            return GateDecision("RESPOND", 0.95, "正在参与当前话题")

        plugin._classify = classify
        direct = FakeEvent("@Denia 你好", direct=True)
        ambient = FakeEvent("那接下来怎么办")

        await plugin.block_blacklisted_message(direct)
        return await collect(plugin.gate_group_message(ambient))

    assert len(asyncio.run(exercise())) == 1


def test_raw_at_component_marks_presence_before_wake_flag_is_set() -> None:
    async def exercise() -> list:
        conversation = SimpleNamespace(persona_id="daniya_agent")
        plugin = make_plugin(conversation=conversation)
        plugin.config.update(
            {
                "evaluation_probability_percent": 0,
                "presence_seconds": 120,
            }
        )

        async def classify(*args, **kwargs):
            return GateDecision("RESPOND", 0.95, "正在参与当前话题")

        plugin._classify = classify
        direct = FakeEvent(
            "你怎么看",
            direct=False,
            components=[At(qq="bot")],
        )
        ambient = FakeEvent("那么月初和月末呢")

        await plugin.block_blacklisted_message(direct)
        return await collect(plugin.gate_group_message(ambient))

    assert len(asyncio.run(exercise())) == 1


def test_zero_presence_duration_keeps_normal_sampling() -> None:
    async def exercise() -> list:
        conversation = SimpleNamespace(persona_id="daniya_agent")
        plugin = make_plugin(conversation=conversation)
        plugin.config.update(
            {
                "evaluation_probability_percent": 0,
                "presence_seconds": 0,
            }
        )

        async def classify(*args, **kwargs):
            raise AssertionError("classifier should not run")

        plugin._classify = classify
        direct = FakeEvent("@Denia 你好", direct=True)
        ambient = FakeEvent("那接下来怎么办")

        await plugin.block_blacklisted_message(direct)
        return await collect(plugin.gate_group_message(ambient))

    assert asyncio.run(exercise()) == []


def test_successful_ambient_reply_starts_sliding_presence() -> None:
    async def exercise() -> tuple[list, list]:
        conversation = SimpleNamespace(persona_id="daniya_agent")
        plugin = make_plugin(conversation=conversation)
        plugin.config.update(
            {
                "evaluation_probability_percent": 100,
                "presence_seconds": 120,
            }
        )

        async def classify(*args, **kwargs):
            return GateDecision("RESPOND", 0.95, "适合继续对话")

        plugin._classify = classify
        first = await collect(plugin.gate_group_message(FakeEvent("这个怎么选")))
        plugin.config["evaluation_probability_percent"] = 0
        second = await collect(plugin.gate_group_message(FakeEvent("那稳定性呢")))
        return first, second

    first, second = asyncio.run(exercise())
    assert len(first) == 1
    assert len(second) == 1


def test_ignored_text_alias_does_not_start_presence() -> None:
    async def exercise() -> tuple[list, list, int]:
        conversation = SimpleNamespace(persona_id="daniya_agent")
        plugin = make_plugin(conversation=conversation)
        plugin.config.update(
            {
                "evaluation_probability_percent": 0,
                "presence_seconds": 120,
            }
        )
        classify_calls = 0

        async def classify(*args, **kwargs):
            nonlocal classify_calls
            classify_calls += 1
            return GateDecision("IGNORE", 0.95, "只是在提到名字")

        plugin._classify = classify
        named = await collect(plugin.gate_group_message(FakeEvent("Denia 的头像")))
        ambient = await collect(plugin.gate_group_message(FakeEvent("挺好看的")))
        return named, ambient, classify_calls

    named, ambient, classify_calls = asyncio.run(exercise())
    assert named == []
    assert ambient == []
    assert classify_calls == 1


def test_group_blacklist_blocks_direct_mentions_before_default_reply() -> None:
    plugin = make_plugin()
    plugin.config["group_blacklist"] = "1"
    event = FakeEvent("@Denia 你好", direct=True)

    asyncio.run(plugin.block_blacklisted_message(event))

    assert event.stopped


def test_account_blacklist_blocks_direct_mentions_from_that_sender() -> None:
    plugin = make_plugin()
    plugin.config["account_blacklist"] = "100"
    event = FakeEvent("@Denia 你好", direct=True, sender_id="100")

    asyncio.run(plugin.block_blacklisted_message(event))

    assert event.stopped


def test_account_blacklist_does_not_block_people_who_only_mention_that_account() -> (
    None
):
    plugin = make_plugin()
    plugin.config["account_blacklist"] = "100"
    event = FakeEvent("@其他机器人 你好", direct=True, sender_id="200")

    asyncio.run(plugin.block_blacklisted_message(event))

    assert not event.stopped


def test_zero_probability_skips_ambient_message() -> None:
    conversation = SimpleNamespace(persona_id="daniya_agent")
    plugin = make_plugin(conversation=conversation)
    plugin.config["evaluation_probability_percent"] = 0
    event = FakeEvent("普通群聊")

    async def classify(*args, **kwargs):
        raise AssertionError("classifier should not run")

    plugin._classify = classify
    assert asyncio.run(collect(plugin.gate_group_message(event))) == []


def test_probability_is_clamped_to_one_hundred() -> None:
    conversation = SimpleNamespace(persona_id="daniya_agent")
    plugin = make_plugin(conversation=conversation)
    plugin.config["evaluation_probability_percent"] = 150
    event = FakeEvent("普通群聊")

    async def classify(*args, **kwargs):
        return GateDecision("RESPOND", 0.95, "值得参与")

    plugin._classify = classify
    assert len(asyncio.run(collect(plugin.gate_group_message(event)))) == 1


def test_custom_confidence_requirement_controls_reply() -> None:
    conversation = SimpleNamespace(persona_id="daniya_agent")
    plugin = make_plugin(conversation=conversation)
    plugin.config["response_confidence_percent"] = 96
    event = FakeEvent("Denia 你怎么看")

    async def classify(*args, **kwargs):
        return GateDecision("RESPOND", 0.95, "值得参与")

    plugin._classify = classify
    assert asyncio.run(collect(plugin.gate_group_message(event))) == []


def test_low_confidence_log_explains_why_reply_was_skipped() -> None:
    conversation = SimpleNamespace(persona_id="daniya_agent")
    plugin = make_plugin(conversation=conversation)
    plugin.config["response_confidence_percent"] = 80
    event = FakeEvent("Denia 你怎么看")
    debug_messages: list[str] = []

    async def classify(*args, **kwargs):
        return GateDecision("RESPOND", 0.79, "可能适合参与")

    plugin._classify = classify
    plugin._debug = lambda _event, message: debug_messages.append(message)

    assert asyncio.run(collect(plugin.gate_group_message(event))) == []
    assert debug_messages == ["忽略 原因=回复把握不足 当前=0.79 要求=0.80"]


def test_legacy_enabled_key_no_longer_disables_plugin() -> None:
    conversation = SimpleNamespace(persona_id="daniya_agent")
    plugin = make_plugin(conversation=conversation)
    plugin.config["enabled"] = False
    event = FakeEvent("Denia 你怎么看")

    async def classify(*args, **kwargs):
        return GateDecision("RESPOND", 0.95, "明确征求意见")

    plugin._classify = classify
    assert len(asyncio.run(collect(plugin.gate_group_message(event)))) == 1


def test_image_description_and_decision_use_separate_models() -> None:
    conversation = SimpleNamespace(persona_id="daniya_agent")
    plugin = make_plugin(conversation=conversation)
    plugin.config["image_provider_id"] = "vision-model"
    plugin.config["decision_provider_id"] = "decision-model"
    plugin.context.llm_responses = {
        "vision-model": "角色正在挥手",
        "decision-model": (
            '{"decision":"RESPOND","confidence":0.9,"reason":"图片适合回应"}'
        ),
    }
    event = FakeEvent("看看这个")

    description = asyncio.run(plugin._describe_images(event, ["image.png"]))
    decision = asyncio.run(
        plugin._classify(
            event,
            aliases={"Denia"},
            history=[],
            has_images=True,
            image_description=description,
        )
    )

    assert description == "角色正在挥手"
    assert decision is not None and decision.should_respond
    assert plugin.context.llm_calls[0]["chat_provider_id"] == "vision-model"
    assert plugin.context.llm_calls[0]["image_urls"] == ["image.png"]
    assert plugin.context.llm_calls[1]["chat_provider_id"] == "decision-model"
    assert "image_urls" not in plugin.context.llm_calls[1]
    assert "图片内容描述：角色正在挥手" in plugin.context.llm_calls[1]["prompt"]
