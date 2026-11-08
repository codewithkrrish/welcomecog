"""Tests for per-guild config defaults and loading."""

from welcomecog.config import (
    DEFAULT_CHANNEL_TEMPLATE,
    DEFAULT_DM_TEMPLATE,
    GuildConfig,
)


def test_defaults_are_sane():
    cfg = GuildConfig()
    assert cfg.dm_enabled is True
    assert cfg.channel_enabled is True
    assert cfg.channel_id is None
    assert "{mention}" in cfg.dm_template
    assert "{server}" in cfg.channel_template


def test_round_trip_through_dict():
    cfg = GuildConfig(
        dm_enabled=False,
        dm_template="hi {name}",
        channel_enabled=True,
        channel_template="welcome {mention}",
        channel_id=12345,
    )
    restored = GuildConfig.from_dict(cfg.to_dict())
    assert restored == cfg


def test_missing_keys_fall_back_to_defaults():
    restored = GuildConfig.from_dict({"dm_enabled": False})
    assert restored.dm_enabled is False
    assert restored.dm_template == DEFAULT_DM_TEMPLATE
    assert restored.channel_template == DEFAULT_CHANNEL_TEMPLATE
    assert restored.channel_id is None


def test_none_and_garbage_input_gives_defaults():
    assert GuildConfig.from_dict(None) == GuildConfig()
    assert GuildConfig.from_dict("not a dict") == GuildConfig()  # type: ignore[arg-type]


def test_wrong_types_fall_back_per_field():
    restored = GuildConfig.from_dict({
        "dm_enabled": "yes",       # a string, not a bool
        "dm_template": 42,         # not a string
        "channel_id": "12345",    # a string, not an int
    })
    assert restored.dm_enabled is True
    assert restored.dm_template == DEFAULT_DM_TEMPLATE
    assert restored.channel_id is None


def test_blank_template_falls_back_to_default():
    restored = GuildConfig.from_dict({"dm_template": "   "})
    assert restored.dm_template == DEFAULT_DM_TEMPLATE


def test_unknown_keys_are_ignored():
    restored = GuildConfig.from_dict({"dm_enabled": False, "future_option": True})
    assert restored.dm_enabled is False
