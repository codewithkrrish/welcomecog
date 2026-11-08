"""welcomecog — a discord.py cog for welcome DMs and join messages.

Install it, load it, and every new member gets a DM plus (once an
admin picks a channel) a message in the server. Both messages are
templates the admins can change with ``!welcome`` commands, and
``!welcome preview`` renders one before it ever goes live.
"""

from __future__ import annotations

from .cog import WelcomeCog

__all__ = ["WelcomeCog"]
__version__ = "1.0.0"


async def setup(bot):  # type: ignore[no-untyped-def]
    """Entry point for ``bot.load_extension("welcomecog")``."""
    await bot.add_cog(WelcomeCog(bot))
