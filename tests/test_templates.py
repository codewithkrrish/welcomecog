"""Tests for placeholder rendering."""

from welcomecog.templates import PLACEHOLDERS, render_template, values_for_member


def _values() -> dict:
    return {
        "mention": "<@123>",
        "name": "Krrish",
        "username": "krrish",
        "user": "krrish",
        "server": "SYNCORE",
        "member_count": 42,
        "member_no": 42,
        "id": 123,
    }


def test_plain_text_renders_unchanged():
    result = render_template("Welcome to the server!", _values())
    assert result.text == "Welcome to the server!"
    assert result.unknown == ()


def test_known_placeholders_are_replaced():
    result = render_template("Hey {mention}, welcome to {server} — #{member_count}!", _values())
    assert result.text == "Hey <@123>, welcome to SYNCORE — #42!"


def test_all_documented_placeholders_have_values():
    # Every placeholder in the docs must render when values exist.
    template = " ".join("{%s}" % name for name in PLACEHOLDERS)
    result = render_template(template, _values())
    assert "{" not in result.text
    assert result.unknown == ()


def test_unknown_placeholder_left_in_place_and_reported():
    result = render_template("Welcome to {sever}, {mention}!", _values())
    assert result.text == "Welcome to {sever}, <@123>!"
    assert result.unknown == ("sever",)


def test_typo_placeholder_does_not_eat_the_braces():
    # A typo should stay visible in the preview so the admin notices it.
    result = render_template("{membr_count} members", _values())
    assert "{membr_count}" in result.text


def test_repeated_placeholder_replaced_every_time():
    result = render_template("{server} {server} {server}", _values())
    assert result.text == "SYNCORE SYNCORE SYNCORE"


def test_empty_template():
    result = render_template("", _values())
    assert result.text == ""


def test_non_placeholder_braces_untouched():
    # Code-ish text like {foo: bar} isn't a placeholder shape we match.
    result = render_template("react with {x} to get a role", _values())
    assert result.text == "react with {x} to get a role"
    assert result.unknown == ("x",)


def test_values_for_member_builds_every_placeholder():
    member = type("Member", (), {
        "mention": "<@7>", "display_name": "Krrish", "name": "krrish", "id": 7,
    })()
    guild = type("Guild", (), {"name": "Test Server", "member_count": 100})()
    values = values_for_member(member, guild)
    assert values["mention"] == "<@7>"
    assert values["name"] == "Krrish"
    assert values["server"] == "Test Server"
    assert values["member_count"] == 100
    assert values["member_no"] == 100
    assert values["id"] == 7


def test_values_for_member_tolerates_missing_attributes():
    values = values_for_member(object(), object())
    assert values["name"] == "someone"
    assert values["server"] == "the server"
    assert values["member_count"] == 0
