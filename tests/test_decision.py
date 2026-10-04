from gate.decision import parse_gate_decision


def test_parse_valid_decision() -> None:
    decision = parse_gate_decision(
        '{"decision":"RESPOND","confidence":0.82,"reason":"直接征求意见"}'
    )
    assert decision is not None
    assert decision.should_respond is True
    assert decision.confidence == 0.82


def test_parse_json_inside_code_fence() -> None:
    decision = parse_gate_decision(
        '```json\n{"decision":"IGNORE","confidence":0.9,"reason":"他人对话"}\n```'
    )
    assert decision is not None
    assert decision.should_respond is False


def test_unknown_or_out_of_range_output_fails_closed() -> None:
    assert parse_gate_decision('{"decision":"REPLY","confidence":0.8}') is None
    assert parse_gate_decision('{"decision":"RESPOND","confidence":1.2}') is None
    assert parse_gate_decision("RESPOND") is None
