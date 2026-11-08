"""Tests for the JSON config store."""

import json

import pytest

from welcomecog.config import GuildConfig
from welcomecog.store import ConfigStore, StoreError


def test_missing_file_starts_empty(tmp_path):
    store = ConfigStore(tmp_path / "config.json")
    assert store.guild_count == 0
    assert store.get(1) == GuildConfig()


def test_save_and_reload_round_trip(tmp_path):
    path = tmp_path / "config.json"
    store = ConfigStore(path)
    cfg = GuildConfig(dm_template="hi {name}", channel_id=99)
    store.set(111, cfg)

    reloaded = ConfigStore(path)
    assert reloaded.get(111) == cfg
    assert reloaded.get(222) == GuildConfig()  # unknown guild -> defaults


def test_save_is_atomic_no_tmp_files_left(tmp_path):
    path = tmp_path / "config.json"
    store = ConfigStore(path)
    store.set(1, GuildConfig())
    leftovers = [p for p in tmp_path.iterdir() if p.suffix == ".tmp"]
    assert leftovers == []
    assert json.loads(path.read_text())["1"]["dm_enabled"] is True


def test_empty_file_is_not_an_error(tmp_path):
    path = tmp_path / "config.json"
    path.write_text("", encoding="utf-8")
    store = ConfigStore(path)
    assert store.guild_count == 0


def test_corrupt_file_is_moved_aside_not_deleted(tmp_path):
    path = tmp_path / "config.json"
    path.write_text('{"111": {"dm_enabled": tru', encoding="utf-8")
    store = ConfigStore(path)
    assert store.guild_count == 0  # starts empty, doesn't crash
    backups = list(tmp_path.glob("config.corrupt-*.json"))
    assert len(backups) == 1
    assert "tru" in backups[0].read_text()  # the original content survives
    # And the store can still save fresh config afterwards.
    store.set(111, GuildConfig(channel_id=5))
    assert ConfigStore(path).get(111).channel_id == 5


def test_non_dict_json_is_treated_as_corrupt(tmp_path):
    path = tmp_path / "config.json"
    path.write_text('["not", "a", "dict"]', encoding="utf-8")
    store = ConfigStore(path)
    assert store.guild_count == 0
    assert list(tmp_path.glob("config.corrupt-*.json"))


def test_delete_removes_guild_and_persists(tmp_path):
    path = tmp_path / "config.json"
    store = ConfigStore(path)
    store.set(111, GuildConfig())
    store.delete(111)
    assert ConfigStore(path).get(111) == GuildConfig()
    assert ConfigStore(path).guild_count == 0


def test_unreadable_directory_raises_store_error(tmp_path):
    # Saving into a path whose parent is a file can't work — must raise
    # StoreError, not a raw OSError, so callers can show a human message.
    blocker = tmp_path / "blocker"
    blocker.write_text("x")
    store = ConfigStore(blocker / "config.json")
    with pytest.raises(StoreError):
        store.set(1, GuildConfig())
