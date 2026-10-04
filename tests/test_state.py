from gate.state import GroupGateState, HistoryEntry


def test_history_is_trimmed_per_group() -> None:
    state = GroupGateState()
    state.append("a", HistoryEntry("1", "one"), 2)
    state.append("a", HistoryEntry("2", "two"), 2)
    state.append("a", HistoryEntry("3", "three"), 2)
    state.append("b", HistoryEntry("4", "other"), 2)
    assert [entry.text for entry in state.recent("a", 10)] == ["two", "three"]
    assert [entry.text for entry in state.recent("b", 10)] == ["other"]


def test_cooldown_is_group_scoped() -> None:
    state = GroupGateState()
    state.mark_reply("a", now=100.0)
    assert state.cooling_down("a", 30, now=129.0)
    assert not state.cooling_down("a", 30, now=130.0)
    assert not state.cooling_down("b", 30, now=101.0)


def test_only_one_decision_can_be_inflight_per_group() -> None:
    state = GroupGateState()
    assert state.begin("a")
    assert not state.begin("a")
    assert state.begin("b")
    state.end("a")
    assert state.begin("a")
