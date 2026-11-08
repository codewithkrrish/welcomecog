"""JSON storage for per-guild welcome configs.

One file, one dict: ``{str(guild_id): config_dict}``. Writes go through
a temp file in the same directory plus ``os.replace``, so a crash
mid-save leaves either the old file or the new one — never half a file.

A corrupt file is never silently overwritten: it gets moved aside with
a timestamped name and the store starts empty, so the admin can still
recover their templates from the moved file.
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
import time
from pathlib import Path

from .config import GuildConfig

__all__ = ["ConfigStore", "StoreError"]

log = logging.getLogger("welcomecog.store")

# Cap the file at a sane size — this is a JSON file, not a database.
# A guild config is ~500 bytes, so this is room for thousands of guilds.
MAX_FILE_BYTES = 5 * 1024 * 1024


class StoreError(Exception):
    """Raised when the config file can't be read or written."""


class ConfigStore:
    """Loads and saves guild configs to a JSON file."""

    def __init__(self, path: str | os.PathLike[str]) -> None:
        self.path = Path(path)
        self._configs: dict[int, GuildConfig] = {}
        self.load()

    def load(self) -> None:
        """Read the file into memory. Missing file means empty config."""
        if not self.path.exists():
            self._configs = {}
            return
        try:
            raw = self.path.read_text(encoding="utf-8")
        except OSError as exc:
            raise StoreError(f"could not read {self.path}: {exc.strerror or exc}") from exc
        if not raw.strip():
            self._configs = {}
            return
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            self._quarantine_corrupt_file(exc)
            self._configs = {}
            return
        if not isinstance(data, dict):
            self._quarantine_corrupt_file(None)
            self._configs = {}
            return
        self._configs = {}
        for guild_id, cfg in data.items():
            try:
                self._configs[int(guild_id)] = GuildConfig.from_dict(cfg)
            except (TypeError, ValueError):
                log.warning("skipping config for guild %r: not a valid id", guild_id)

    def _quarantine_corrupt_file(self, exc: json.JSONDecodeError | None) -> None:
        """Move a broken config aside instead of overwriting it."""
        stamp = time.strftime("%Y%m%d-%H%M%S")
        backup = self.path.with_suffix(f".corrupt-{stamp}.json")
        try:
            self.path.rename(backup)
        except OSError:
            log.exception("could not move corrupt config %s aside", self.path)
            return
        reason = f" (line {exc.lineno}, col {exc.colno})" if exc else ""
        log.warning("config file %s was corrupt%s — moved to %s", self.path, reason, backup)

    def get(self, guild_id: int) -> GuildConfig:
        """Config for a guild, or fresh defaults if we've never seen it."""
        return self._configs.get(guild_id, GuildConfig())

    def set(self, guild_id: int, config: GuildConfig) -> None:
        """Store a guild's config and persist it to disk."""
        self._configs[guild_id] = config
        self.save()

    def delete(self, guild_id: int) -> None:
        """Forget a guild's config (used by reset) and persist."""
        self._configs.pop(guild_id, None)
        self.save()

    def save(self) -> None:
        """Write all configs atomically: temp file + rename."""
        data = {str(gid): cfg.to_dict() for gid, cfg in self._configs.items()}
        payload = json.dumps(data, indent=2, sort_keys=True) + "\n"
        if len(payload.encode("utf-8")) > MAX_FILE_BYTES:
            raise StoreError(
                f"config file would exceed {MAX_FILE_BYTES // (1024 * 1024)} MB — "
                "this store isn't meant for that many guilds"
            )
        tmp_name: str | None = None
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            fd, tmp_name = tempfile.mkstemp(
                prefix=self.path.name + ".", suffix=".tmp", dir=str(self.path.parent)
            )
            with os.fdopen(fd, "w", encoding="utf-8") as tmp:
                tmp.write(payload)
                tmp.flush()
                os.fsync(tmp.fileno())
            os.replace(tmp_name, self.path)
        except OSError as exc:
            if tmp_name is not None:
                try:
                    os.unlink(tmp_name)
                except OSError:
                    pass
            raise StoreError(f"could not write {self.path}: {exc.strerror or exc}") from exc

    @property
    def guild_count(self) -> int:
        """How many guilds have a stored config."""
        return len(self._configs)
