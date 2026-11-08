"""Per-guild config for the welcome cog.

One small dataclass per guild, kept deliberately boring: a couple of
booleans, two message templates, one channel id. Defaults are chosen so
a fresh install does something sensible without spamming anyone — DMs
are on, the channel message is on but has nowhere to go until an admin
picks a channel.
"""

from __future__ import annotations

from dataclasses import dataclass, field

__all__ = ["GuildConfig", "DEFAULT_DM_TEMPLATE", "DEFAULT_CHANNEL_TEMPLATE"]

DEFAULT_DM_TEMPLATE = (
    "Hey {mention}, welcome to {server}! You're member #{member_count}. "
    "Have a look around and say hi when you're ready."
)

DEFAULT_CHANNEL_TEMPLATE = (
    "{mention} just joined {server} — welcome! We're {member_count} strong now."
)


@dataclass
class GuildConfig:
    """Welcome settings for one guild."""

    dm_enabled: bool = True
    dm_template: str = DEFAULT_DM_TEMPLATE
    channel_enabled: bool = True
    channel_template: str = DEFAULT_CHANNEL_TEMPLATE
    channel_id: int | None = None

    def to_dict(self) -> dict[str, object]:
        """Serialise to plain JSON-friendly types."""
        return {
            "dm_enabled": self.dm_enabled,
            "dm_template": self.dm_template,
            "channel_enabled": self.channel_enabled,
            "channel_template": self.channel_template,
            "channel_id": self.channel_id,
        }

    @classmethod
    def from_dict(cls, data: dict[str, object] | None) -> GuildConfig:
        """Build from stored data, tolerating missing or mistyped keys.

        A config file edited by hand (or written by an older version)
        should never crash the bot on load — unknown keys are ignored,
        and a wrong type falls back to the default for that field.
        """
        if not isinstance(data, dict):
            return cls()
        return cls(
            dm_enabled=_as_bool(data.get("dm_enabled"), True),
            dm_template=_as_str(data.get("dm_template"), DEFAULT_DM_TEMPLATE),
            channel_enabled=_as_bool(data.get("channel_enabled"), True),
            channel_template=_as_str(data.get("channel_template"), DEFAULT_CHANNEL_TEMPLATE),
            channel_id=_as_int_or_none(data.get("channel_id")),
        )


def _as_bool(value: object, default: bool) -> bool:
    return value if isinstance(value, bool) else default


def _as_str(value: object, default: str) -> str:
    # Empty string is a real choice (send nothing) only if the admin set
    # it deliberately — but an empty template is almost always a mistake,
    # so treat blank as "not set" and fall back to the default.
    return value if isinstance(value, str) and value.strip() else default


def _as_int_or_none(value: object) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None
