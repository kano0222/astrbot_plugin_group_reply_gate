from gate.policy import (
    contains_alias,
    get_mode_policy,
    group_is_allowed,
    parse_string_set,
    starts_with_ignored_prefix,
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


def test_alias_and_prefix_matching_are_case_insensitive() -> None:
    assert contains_alias("Denia 你怎么看", {"denia"})
    assert starts_with_ignored_prefix("  WW刷新面板", {"ww"})


def test_command_prefix_does_not_match_longer_ascii_word() -> None:
    assert not starts_with_ignored_prefix("www 笑死", {"ww"})
    assert not starts_with_ignored_prefix("ww_foo", {"ww"})
    assert starts_with_ignored_prefix("ww 刷新面板", {"ww"})


def test_unknown_mode_uses_balanced_policy() -> None:
    assert get_mode_policy("unknown") == get_mode_policy("balanced")
