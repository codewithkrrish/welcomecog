"""The welcome cog itself.

Two jobs, kept separate on purpose:

* ``on_member_join`` — the listener. Renders the guild's templates and
  sends them. It never raises: a member with closed DMs or a deleted
  welcome channel is normal, not a crash.
* ``!welcome`` — the admin command group. Everything an admin needs to
  set templates, pick a channel, toggle each message, and preview the
  result before it goes out to a real person.

All commands need Manage Server. Preview renders against a real member
(by default the admin running it), so what you see is what the next
joiner gets.
"""

from __future__ import annotations

import logging
from pathlib import Path

import discord
from discord.ext import commands

from .config import DEFAULT_CHANNEL_TEMPLATE, DEFAULT_DM_TEMPLATE, GuildConfig
from .store import ConfigStore, StoreError
from .templates import PLACEHOLDERS, RenderResult, render_template, values_for_member

__all__ = ["WelcomeCog"]

log = logging.getLogger("welcomecog")

# Discord caps a plain message at 2000 characters. Templates longer
# than that can never be delivered, so refuse them at set-time instead
# of failing silently on every join.
MAX_TEMPLATE_LENGTH = 1900

# Where configs live when the cog is loaded as an extension with no
# explicit path. Next to the bot's working directory, easy to find.
DEFAULT_STORE_PATH = Path("welcomecog-config.json")


class WelcomeCog(commands.Cog):
    """Welcome DMs and server join messages, per guild."""

    def __init__(self, bot: commands.Bot, store_path: str | Path = DEFAULT_STORE_PATH) -> None:
        self.bot = bot
        try:
            self.store = ConfigStore(store_path)
        except StoreError as exc:
            # A store that can't even load shouldn't take the whole bot
            # down, but an admin needs to know configs aren't saving.
            log.error("welcomecog: %s — running with in-memory config only", exc)
            self.store = ConfigStore.__new__(ConfigStore)
            self.store.path = Path(store_path)
            self.store._configs = {}  # noqa: SLF001 — fallback, see above

    # -- join handling -------------------------------------------------

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member) -> None:
        """Send the guild's welcome DM and channel message, if enabled."""
        guild = member.guild
        config = self.store.get(guild.id)
        values = values_for_member(member, guild)

        if config.dm_enabled:
            await self._send_dm(member, config, values)
        if config.channel_enabled and config.channel_id is not None:
            await self._send_channel_message(guild, config, values)

    async def _send_dm(
        self, member: discord.Member, config: GuildConfig, values: dict[str, object]
    ) -> None:
        result = render_template(config.dm_template, values)
        try:
            await member.send(result.text)
        except discord.Forbidden:
            # DMs closed or blocked — the member's choice, not an error.
            log.info("could not DM %s (%s): DMs closed", member, member.id)
        except discord.HTTPException as exc:
            log.warning("failed to DM %s (%s): %s", member, member.id, exc)

    async def _send_channel_message(
        self, guild: discord.Guild, config: GuildConfig, values: dict[str, object]
    ) -> None:
        channel = guild.get_channel(config.channel_id)  # type: ignore[arg-type]
        if channel is None or not isinstance(channel, discord.TextChannel):
            log.warning(
                "welcome channel %s in %s is gone or not a text channel — skipping",
                config.channel_id,
                guild.id,
            )
            return
        result = render_template(config.channel_template, values)
        try:
            await channel.send(result.text)
        except discord.Forbidden:
            log.warning("no permission to send in #%s (%s)", channel.name, channel.id)
        except discord.HTTPException as exc:
            log.warning("failed to send welcome in #%s: %s", channel.name, exc)

    # -- admin commands ------------------------------------------------

    @commands.group(name="welcome", invoke_without_command=True)
    @commands.has_permissions(manage_guild=True)
    async def welcome(self, ctx: commands.Context) -> None:
        """Show the current welcome setup for this server."""
        await self._show_config(ctx)

    @welcome.command(name="show")
    @commands.has_permissions(manage_guild=True)
    async def welcome_show(self, ctx: commands.Context) -> None:
        """Show the current welcome setup for this server."""
        await self._show_config(ctx)

    async def _show_config(self, ctx: commands.Context) -> None:
        config = self._guild_config(ctx)
        channel = f"<#{config.channel_id}>" if config.channel_id else "not set"
        lines = [
            f"**Welcome DMs:** {'on' if config.dm_enabled else 'off'}",
            f"> {config.dm_template}",
            f"**Channel message:** {'on' if config.channel_enabled else 'off'} → {channel}",
            f"> {config.channel_template}",
            "",
            "Change them with `!welcome dm ...`, `!welcome channel ...`, "
            "`!welcome setchannel #channel`, `!welcome toggle dm|channel`, "
            "and check the result with `!welcome preview`.",
        ]
        await ctx.send("\n".join(lines))

    @welcome.command(name="dm")
    @commands.has_permissions(manage_guild=True)
    async def welcome_set_dm(self, ctx: commands.Context, *, message: str) -> None:
        """Set the DM template. Example: !welcome dm Hey {mention}, welcome to {server}!"""
        await self._set_template(ctx, kind="dm", message=message)

    @welcome.command(name="channel")
    @commands.has_permissions(manage_guild=True)
    async def welcome_set_channel(self, ctx: commands.Context, *, message: str) -> None:
        """Set the channel template. Example: !welcome channel {mention} just joined!"""
        await self._set_template(ctx, kind="channel", message=message)

    async def _set_template(self, ctx: commands.Context, *, kind: str, message: str) -> None:
        if len(message) > MAX_TEMPLATE_LENGTH:
            await ctx.send(
                f"That template is {len(message)} characters — Discord messages "
                f"cap at 2000, so keep it under {MAX_TEMPLATE_LENGTH}."
            )
            return
        config = self._guild_config(ctx)
        result = render_template(message, values_for_member(ctx.author, ctx.guild))
        if kind == "dm":
            config.dm_template = message
        else:
            config.channel_template = message
        if not self._save(ctx, config):
            return
        reply = f"Saved. It will look like this:\n> {result.text}"
        if result.has_unknown:
            reply += (
                "\nNote: I didn't recognise "
                + ", ".join(f"`{{{name}}}`" for name in result.unknown)
                + " — check the spelling, or see `!welcome placeholders`."
            )
        await ctx.send(reply)

    @welcome.command(name="setchannel")
    @commands.has_permissions(manage_guild=True)
    async def welcome_set_channel_id(
        self, ctx: commands.Context, channel: discord.TextChannel
    ) -> None:
        """Pick the channel join messages go to. Example: !welcome setchannel #general"""
        config = self._guild_config(ctx)
        config.channel_id = channel.id
        if not self._save(ctx, config):
            return
        await ctx.send(f"Join messages will go to {channel.mention} from now on.")

    @welcome.command(name="toggle")
    @commands.has_permissions(manage_guild=True)
    async def welcome_toggle(self, ctx: commands.Context, target: str) -> None:
        """Turn one message on or off. Example: !welcome toggle dm"""
        target = target.lower()
        if target not in ("dm", "channel"):
            await ctx.send("Toggle what — `dm` or `channel`? Example: `!welcome toggle dm`")
            return
        config = self._guild_config(ctx)
        if target == "dm":
            config.dm_enabled = not config.dm_enabled
            state = "on" if config.dm_enabled else "off"
        else:
            config.channel_enabled = not config.channel_enabled
            state = "on" if config.channel_enabled else "off"
        if not self._save(ctx, config):
            return
        await ctx.send(f"Welcome {target}s are now **{state}**.")

    @welcome.command(name="preview")
    @commands.has_permissions(manage_guild=True)
    async def welcome_preview(
        self,
        ctx: commands.Context,
        kind: str = "dm",
        member: discord.Member | None = None,
    ) -> None:
        """Render a template for a member before it goes live.

        Example: !welcome preview dm — renders the DM for you.
        Example: !welcome preview channel @Someone — renders the channel
        message as that member would see it.
        """
        kind = kind.lower()
        if kind not in ("dm", "channel"):
            await ctx.send("Preview what — `dm` or `channel`? Example: `!welcome preview dm`")
            return
        config = self._guild_config(ctx)
        who = member or ctx.author
        template = config.dm_template if kind == "dm" else config.channel_template
        result = render_template(template, values_for_member(who, ctx.guild))
        await ctx.send(f"Preview of the {kind} message for {who.mention}:\n> {result.text}")

    @welcome.command(name="placeholders")
    @commands.has_permissions(manage_guild=True)
    async def welcome_placeholders(self, ctx: commands.Context) -> None:
        """List every placeholder you can use in a template."""
        lines = ["**Placeholders you can use in any template:**", ""]
        lines += [f"`{{{name}}}` — {desc}" for name, desc in PLACEHOLDERS.items()]
        lines += ["", "Example: `!welcome dm Hey {mention}, welcome to {server}!`"]
        await ctx.send("\n".join(lines))

    @welcome.command(name="reset")
    @commands.has_permissions(manage_guild=True)
    async def welcome_reset(self, ctx: commands.Context, confirm: str = "") -> None:
        """Reset this server's welcome setup to the defaults.

        Asks for confirmation on purpose — this wipes custom templates.
        Example: !welcome reset confirm
        """
        if confirm.lower() != "confirm":
            await ctx.send(
                "This wipes your custom templates and channel back to the defaults. "
                "If you're sure, run `!welcome reset confirm`."
            )
            return
        self.store.delete(ctx.guild.id)
        await ctx.send("Welcome setup reset to the defaults.")

    # -- helpers --------------------------------------------------------

    def _guild_config(self, ctx: commands.Context) -> GuildConfig:
        if ctx.guild is None:
            raise commands.NoPrivateMessage("welcome commands only work in a server.")
        return self.store.get(ctx.guild.id)

    def _save(self, ctx: commands.Context, config: GuildConfig) -> bool:
        """Persist a config change; tell the admin plainly if it fails."""
        if ctx.guild is None:
            return False
        try:
            self.store.set(ctx.guild.id, config)
        except StoreError as exc:
            log.error("could not save welcome config for %s: %s", ctx.guild.id, exc)
            return False
        return True

    # -- errors ----------------------------------------------------------

    @welcome.error
    @welcome_show.error
    @welcome_set_dm.error
    @welcome_set_channel.error
    @welcome_set_channel_id.error
    @welcome_toggle.error
    @welcome_preview.error
    @welcome_placeholders.error
    @welcome_reset.error
    async def _welcome_error(self, ctx: commands.Context, error: commands.CommandError) -> None:
        """Human replies for the usual mistakes — never a traceback."""
        if isinstance(error, commands.MissingPermissions):
            await ctx.send("You need Manage Server to change the welcome setup.")
        elif isinstance(error, commands.MissingRequiredArgument):
            await ctx.send(
                f"Missing something — try `!welcome {ctx.command}` with the argument "
                "shown in `!help welcome`."
            )
        elif isinstance(error, commands.BadArgument):
            await ctx.send(f"Couldn't use that argument: {error}")
        elif isinstance(error, commands.NoPrivateMessage):
            await ctx.send("Welcome commands only work inside a server, not in DMs.")
        else:
            log.exception("unexpected error in !welcome", exc_info=error)
            await ctx.send("Something went wrong on my side — try again in a bit.")


async def setup(bot: commands.Bot) -> None:
    """Entry point for ``bot.load_extension("welcomecog.cog")``."""
    await bot.add_cog(WelcomeCog(bot))
