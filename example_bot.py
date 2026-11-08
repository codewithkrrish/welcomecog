"""Minimal bot that loads the welcome cog — copy this to get started.

Needs the Members intent enabled in the Discord developer portal,
otherwise on_member_join never fires and nobody gets welcomed.

    export DISCORD_TOKEN="your bot token"
    python example_bot.py
"""

import logging
import os
import sys

import discord
from discord.ext import commands

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

TOKEN = os.environ.get("DISCORD_TOKEN")
if not TOKEN:
    print("Set DISCORD_TOKEN first — see the README.", file=sys.stderr)
    sys.exit(2)


intents = discord.Intents.default()
intents.members = True  # required: without this, joins are invisible

bot = commands.Bot(command_prefix="!", intents=intents)


@bot.event
async def on_ready() -> None:
    print(f"Logged in as {bot.user} — try !welcome in a server.")


async def main() -> None:
    async with bot:
        await bot.load_extension("welcomecog")
        await bot.start(TOKEN)


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
