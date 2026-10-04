from gate.policy import (
    account_is_blocked,
    contains_alias,
    get_mode_policy,
    group_is_allowed,
    parse_string_set,
)


def test_parse_string_set_accepts_common_separators() -> None:
    assert parse_string_set("a,b，c\nd") == {"a", "b", "c", "d"}


def test_blacklist_wins_over_whitelist() -> None:
    assert not group_is_allowed(
        umo="default:GroupMessage:1",
        group_id="1",
        whitelist={"1"},
        blacklist={"default:GroupMessage:1"},
    )


def test_empty_whitelist_allows_group() -> None:
    assert group_is_allowed(
        umo="default:GroupMessage:1",
        group_id="1",
        whitelist=set(),
        blacklist=set(),
    )


def test_alias_matching_is_case_insensitive() -> None:
    assert contains_alias("Denia 你怎么看", {"denia"})


def test_account_blacklist_matches_sender_only() -> None:
    assert account_is_blocked(
        sender_id="100",
        blacklist={"100"},
    )
    assert not account_is_blocked(
        sender_id="200",
        blacklist={"100"},
    )


def test_unknown_mode_uses_balanced_policy() -> None:
    assert get_mode_policy("unknown") == get_mode_policy("balanced")
