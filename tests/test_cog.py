"""Tests for the cog: joins, DMs, channel messages, admin commands."""

from unittest.mock import AsyncMock, MagicMock

import discord
import pytest

from welcomecog.cog import WelcomeCog
from welcomecog.config import GuildConfig


def _member(*, guild=None, send=None):
    member = MagicMock()
    member.id = 777
    member.name = "newbie"
    member.display_name = "Newbie"
    member.mention = "<@777>"
    member.guild = guild
    member.send = send or AsyncMock()
    return member


def _guild(*, member_count=50, channel=None):
    guild = MagicMock()
    guild.id = 111
    guild.name = "Test Server"
    guild.member_count = member_count
    guild.get_channel.return_value = channel
    return guild


def _channel():
    channel = MagicMock(spec=discord.TextChannel)
    channel.id = 999
    channel.name = "general"
    channel.send = AsyncMock()
    return channel


def _ctx(*, guild=None, author=None):
    ctx = MagicMock()
    ctx.guild = guild
    ctx.author = author or _member(guild=guild)
    ctx.send = AsyncMock()
    return ctx


@pytest.fixture
def cog(tmp_path):
    bot = MagicMock()
    return WelcomeCog(bot, store_path=tmp_path / "config.json")


async def test_join_sends_dm_by_default(cog):
    guild = _guild()
    member = _member(guild=guild)
    await cog.on_member_join(member)
    member.send.assert_awaited_once()
    text = member.send.await_args.args[0]
    assert "<@777>" in text and "Test Server" in text and "#50" in text


async def test_join_skips_dm_when_disabled(cog):
    guild = _guild()
    member = _member(guild=guild)
    cog.store.set(111, GuildConfig(dm_enabled=False))
    await cog.on_member_join(member)
    member.send.assert_not_awaited()


async def test_join_with_closed_dms_does_not_raise(cog):
    guild = _guild()
    member = _member(guild=guild)
    member.send.side_effect = discord.Forbidden(MagicMock(), "Cannot send messages")
    await cog.on_member_join(member)  # must not raise


async def test_join_sends_channel_message_when_channel_set(cog):
    channel = _channel()
    guild = _guild(channel=channel)
    member = _member(guild=guild)
    cog.store.set(111, GuildConfig(channel_id=999))
    await cog.on_member_join(member)
    channel.send.assert_awaited_once()
    assert "<@777>" in channel.send.await_args.args[0]


async def test_join_skips_channel_message_when_no_channel(cog):
    guild = _guild(channel=None)
    member = _member(guild=guild)
    await cog.on_member_join(member)
    guild.get_channel.assert_not_called()


async def test_join_skips_channel_message_when_channel_gone(cog):
    guild = _guild(channel=None)  # get_channel returns None
    member = _member(guild=guild)
    cog.store.set(111, GuildConfig(channel_id=999))
    await cog.on_member_join(member)  # must not raise


async def test_set_dm_template_saves_and_shows_preview(cog):
    ctx = _ctx(guild=_guild())
    await cog.welcome_set_dm.callback(cog, ctx, message="Yo {mention}, welcome to {server}!")
    assert cog.store.get(111).dm_template == "Yo {mention}, welcome to {server}!"
    sent = ctx.send.await_args.args[0]
    assert "Yo <@777>, welcome to Test Server!" in sent


async def test_set_template_warns_about_unknown_placeholder(cog):
    ctx = _ctx(guild=_guild())
    await cog.welcome_set_dm.callback(cog, ctx, message="Hi {sever}!")
    sent = ctx.send.await_args.args[0]
    assert "{sever}" in sent  # left in the preview
    assert "didn't recognise" in sent


async def test_set_template_rejects_overlong_message(cog):
    ctx = _ctx(guild=_guild())
    await cog.welcome_set_dm.callback(cog, ctx, message="x" * 2000)
    assert cog.store.get(111).dm_template != "x" * 2000
    assert "2000" in ctx.send.await_args.args[0]


async def test_toggle_flips_dm_off_then_on(cog):
    ctx = _ctx(guild=_guild())
    await cog.welcome_toggle.callback(cog, ctx, "dm")
    assert cog.store.get(111).dm_enabled is False
    await cog.welcome_toggle.callback(cog, ctx, "dm")
    assert cog.store.get(111).dm_enabled is True


async def test_toggle_rejects_bad_target(cog):
    ctx = _ctx(guild=_guild())
    await cog.welcome_toggle.callback(cog, ctx, "everything")
    assert "dm" in ctx.send.await_args.args[0]
    assert cog.store.get(111).dm_enabled is True  # unchanged


async def test_preview_renders_for_the_invoker(cog):
    ctx = _ctx(guild=_guild())
    await cog.welcome_preview.callback(cog, ctx, "dm", None)
    sent = ctx.send.await_args.args[0]
    assert "Preview of the dm message" in sent
    assert "<@777>" in sent


async def test_reset_needs_confirm_word(cog):
    ctx = _ctx(guild=_guild())
    cog.store.set(111, GuildConfig(dm_template="custom"))
    await cog.welcome_reset.callback(cog, ctx, "")
    assert cog.store.get(111).dm_template == "custom"  # untouched
    await cog.welcome_reset.callback(cog, ctx, "confirm")
    assert cog.store.get(111) == GuildConfig()  # back to defaults
