# welcomecog

Every server I've run had the same problem: someone joins, nobody says
anything, and they leave an hour later wondering if anyone noticed.
The bots that fix this either want a dashboard and a database, or they
greet people with a message you can't change without editing code.

welcomecog is the middle ground — one file-sized cog you drop into a
discord.py bot. New members get a DM and a message in your welcome
channel, both written as templates you can change from Discord itself,
and you can preview exactly what a joiner will see before it goes live.

## Quickstart

You need Python 3.10+ and a bot token from the
[Discord developer portal](https://discord.com/developers/applications).
Turn on the **Server Members intent** there — without it, Discord never
tells your bot someone joined, and nothing gets sent.

```bash
git clone https://github.com/codewithkrrish/welcomecog.git
cd welcomecog
pip install -r requirements.txt
export DISCORD_TOKEN="your bot token"
python example_bot.py
```

Or load it into a bot you already have:

```python
await bot.load_extension("welcomecog")
```

Then in your server:

```
!welcome setchannel #introductions
!welcome preview channel
```

That's it — the next person who joins gets greeted.

## Commands

All of them need Manage Server, and they all run in the server, not in DMs.

| Command | What it does |
| --- | --- |
| `!welcome` | Show the current setup |
| `!welcome dm <message>` | Set the DM template |
| `!welcome channel <message>` | Set the channel template |
| `!welcome setchannel #channel` | Pick where join messages go |
| `!welcome toggle dm` / `toggle channel` | Turn one message on or off |
| `!welcome preview [dm\|channel] [@member]` | Render a template for a member, before it goes live |
| `!welcome placeholders` | List every placeholder you can use |
| `!welcome reset confirm` | Wipe back to the defaults |

## Placeholders

Templates are plain text with `{placeholders}` in them:

| Placeholder | Becomes |
| --- | --- |
| `{mention}` | An @-mention of the new member |
| `{name}` | Their display name |
| `{username}` | Their username |
| `{server}` | Your server's name |
| `{member_count}` | How many members you have after this join |
| `{id}` | Their Discord user id |

A couple of templates I've actually used:

```
!welcome dm Hey {mention}, welcome to {server}! You're member #{member_count} — grab the rules in #rules and say hi when you're ready.
!welcome channel {mention} just joined {server}. We're {member_count} strong now, say hey!
```

If you typo a placeholder — `{sever}` instead of `{server}` — it stays
in the message as written and the bot tells you it didn't recognise it,
so it shows up in the preview instead of vanishing silently.

## How it stores things

Per-server settings live in `welcomecog-config.json` next to wherever
you run the bot. No database, no extra service. Writes go through a
temp file plus a rename, so a crash mid-save can't corrupt it, and if
the file ever does get mangled the cog moves it aside (with a
timestamp) and starts fresh rather than deleting your templates.

## Limitations

Honest ones, since they decide whether this fits your server:

- **JSON storage, not a database.** Fine for a bot in tens or even
  hundreds of servers. If you're running thousands of guilds, you want
  a real store — this file caps at 5 MB on purpose.
- **DMs can be closed.** If a member has DMs off, the DM quietly
  doesn't arrive. The bot logs it and moves on; there's nothing to fix
  on your side.
- **Plain text only.** No embeds, no images, no buttons. If you want a
  rich card, this cog isn't it.
- **One welcome channel per server.** Most servers only need one; if
  you need more, open an issue and say so.

## Project structure

```
welcomecog/
  __init__.py    # extension entry point
  cog.py         # the cog: listener + !welcome commands
  config.py      # per-guild settings and defaults
  store.py       # JSON storage with atomic writes
  templates.py   # placeholder rendering
tests/           # pytest: rendering, config, storage, cog behaviour
example_bot.py   # minimal bot that loads the cog
```

## Running the tests

```bash
pip install discord.py pytest pytest-asyncio
python -m pytest
```

## License

MIT — see [LICENSE](LICENSE).

## Author

Built by [Krrish](https://github.com/codewithkrrish) — I make Discord
bots and small Python tools. If you use this in your server, tell me
how the welcome messages are working out.
