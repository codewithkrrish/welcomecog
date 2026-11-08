"""Placeholder rendering for welcome messages.

A template is plain text with ``{placeholders}`` in it, e.g.::

    "Hey {mention}, welcome to {server} — you're member #{member_count}!"

Only placeholders we know about get replaced. Anything else is left
exactly as written and reported back, so a typo like ``{sever}`` shows
up in the preview instead of silently vanishing.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

__all__ = ["PLACEHOLDERS", "RenderResult", "render_template"]

# The placeholders a template may use, and what each one means.
PLACEHOLDERS: dict[str, str] = {
    "mention": "an @-mention of the new member",
    "name": "the member's display name",
    "username": "the member's username (no @, no discriminator)",
    "user": "username, same as {username} — kept because people type it first",
    "server": "the server's name",
    "member_count": "how many members the server has after this join",
    "member_no": "same as {member_count}, shorter to type",
    "id": "the member's Discord user id",
}

_PLACEHOLDER_RE = re.compile(r"\{([a-zA-Z_][a-zA-Z0-9_]*)\}")


@dataclass(frozen=True)
class RenderResult:
    """The rendered message plus any placeholders we did not recognise."""

    text: str
    unknown: tuple[str, ...] = ()

    @property
    def has_unknown(self) -> bool:
        """True when the template used a placeholder we don't know."""
        return bool(self.unknown)


def render_template(template: str, values: dict[str, object]) -> RenderResult:
    """Render *template* against *values*.

    Known placeholders are replaced with their value (anything is
    stringified). Unknown placeholders are left untouched and listed in
    ``RenderResult.unknown`` so the caller can warn about them.

    A template with no placeholders at all renders unchanged — plain
    text is a perfectly good welcome message.
    """
    unknown: list[str] = []

    def replace(match: re.Match[str]) -> str:
        key = match.group(1)
        if key in PLACEHOLDERS and key in values:
            return str(values[key])
        if key not in PLACEHOLDERS:
            unknown.append(key)
        return match.group(0)

    return RenderResult(text=_PLACEHOLDER_RE.sub(replace, template), unknown=tuple(unknown))


def values_for_member(member: object, guild: object) -> dict[str, object]:
    """Build the placeholder values for a member joining a guild.

    Takes duck-typed ``discord.Member`` / ``discord.Guild`` objects so
    this stays testable without a live connection. Only reads attributes
    that exist on every member and guild.
    """
    display_name = getattr(member, "display_name", None) or getattr(member, "name", "someone")
    username = getattr(member, "name", "someone")
    member_count = getattr(guild, "member_count", None) or 0
    return {
        "mention": getattr(member, "mention", f"@{display_name}"),
        "name": display_name,
        "username": username,
        "user": username,
        "server": getattr(guild, "name", "the server"),
        "member_count": member_count,
        "member_no": member_count,
        "id": getattr(member, "id", 0),
    }
