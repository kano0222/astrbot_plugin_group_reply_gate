from __future__ import annotations

import asyncio
from types import SimpleNamespace

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

    def get_config(self, *, umo: str):
        return {
            "provider_ltm_settings": {"active_reply": {"enable": self.builtin_active}}
        }


class FakeEvent:
    def __init__(self, text: str = "普通消息", *, direct: bool = False) -> None:
        self.message_str = text
        self.is_at_or_wake_command = direct
        self.unified_msg_origin = "default:GroupMessage:1"
        self.message_obj = SimpleNamespace(message=[])

    def get_group_id(self):
        return "1"

    def get_sender_id(self):
        return "user"

    def get_self_id(self):
        return "bot"

    def get_sender_name(self):
        return "测试用户"

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
    assert results[0]["prompt"] == "Denia 你怎么看"
    assert results[0]["conversation"] is conversation


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


def test_legacy_enabled_key_no_longer_disables_plugin() -> None:
    conversation = SimpleNamespace(persona_id="daniya_agent")
    plugin = make_plugin(conversation=conversation)
    plugin.config["enabled"] = False
    event = FakeEvent("Denia 你怎么看")

    async def classify(*args, **kwargs):
        return GateDecision("RESPOND", 0.95, "明确征求意见")

    plugin._classify = classify
    assert len(asyncio.run(collect(plugin.gate_group_message(event)))) == 1
