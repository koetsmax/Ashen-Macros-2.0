"""Pick the right Ashen queue line from /prep target or /process member autocomplete.

The Ashen bot's autocomplete for a user id returns every queue line that mentions
that user, so two people queued "with" each other both show up for either id. The
Vencord plugin used to guess the owner line on its own with only a name hint; here
we pick it in Ashen Macros with the full queue snapshot (every queued member's id and
display name), log the real labels, and refuse rather than run the command on the
wrong person when the owner can't be told apart.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Iterable

logger = logging.getLogger(__name__)

_MENTION_RE = re.compile(r"<@!?(\d{16,20})>")
# "2: ALittleLoud -- with mick together" → "ALittleLoud". Accept -- / — / – / | as
# the owner separator; without one the whole text after "N:" is the owner part.
_OWNER_RE = re.compile(r"^\s*\d+\s*[:.)]\s*(.+?)(?:\s+(?:--|—|–|\|)\s|\s*(?:--|—|–)|$)")
_SNOWFLAKE_RE = re.compile(r"^\d{16,20}$")


class QueueMemberPickError(RuntimeError):
    """No autocomplete choice could be tied to the requested queue member."""


def _norm(text: str) -> str:
    text = str(text or "").strip().lstrip("@").strip()
    return re.sub(r"\s+", " ", text).casefold()


def owner_segment(label: str) -> str:
    text = str(label or "")
    m = _OWNER_RE.match(text)
    if m:
        return m.group(1).strip()
    # No "N:" prefix: owner is whatever comes before the first separator.
    return re.split(r"\s+(?:--|—|–)\s*", text, maxsplit=1)[0].strip()


def _segment_names_user(segment: str, names: Iterable[str]) -> bool:
    seg = _norm(segment)
    if not seg:
        return False
    for name in names:
        n = _norm(name)
        if len(n) < 2:
            continue
        if seg == n or seg.startswith(n + " ") or seg.startswith(n + ","):
            return True
    return False


def choice_owner(label: str, names_by_id: dict[str, list[str]]) -> str | None:
    """Resolve the owner user id of one autocomplete label, or None if unknown."""
    seg = owner_segment(label)
    m = _MENTION_RE.search(seg)
    if m:
        return m.group(1)
    if _SNOWFLAKE_RE.match(seg):
        return seg
    matches = [uid for uid, names in names_by_id.items() if _segment_names_user(seg, names)]
    # Two queued people with the same name prefix ("Max" / "Max2") → longest wins.
    if len(matches) > 1:
        def best_len(uid: str) -> int:
            return max(
                (len(_norm(n)) for n in names_by_id[uid] if _segment_names_user(seg, [n])),
                default=0,
            )
        matches.sort(key=best_len, reverse=True)
        if best_len(matches[0]) == best_len(matches[1]):
            return None
    return matches[0] if matches else None


def names_by_user_id(queue: Iterable[dict] | None) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for entry in queue or []:
        uid = str(entry.get("user_id") or "").strip()
        if not uid:
            continue
        names = out.setdefault(uid, [])
        for key in ("display_name", "username", "global_name", "nickname"):
            v = str(entry.get(key) or "").strip()
            if v and v not in names:
                names.append(v)
    return out


def pick_queue_member_choice(
    choices: list[dict[str, Any]],
    user_id: str,
    display_name: str = "",
    queue: Iterable[dict] | None = None,
) -> dict[str, Any]:
    """Return the autocomplete choice whose line belongs to ``user_id``.

    Raises QueueMemberPickError when it can't be told safely.
    """
    uid = str(user_id or "").strip()
    names = names_by_user_id(queue)
    own = names.setdefault(uid, [])
    if display_name and display_name not in own:
        own.insert(0, str(display_name))

    if not choices:
        raise QueueMemberPickError("Ashen returned no queue lines for this member")

    owners = [choice_owner(str(c.get("name") or ""), names) for c in choices]
    mine = [c for c, o in zip(choices, owners) if o == uid]
    if len(mine) == 1:
        return mine[0]
    if len(mine) > 1:
        raise QueueMemberPickError(
            f"{len(mine)} queue lines look like they belong to {display_name or uid}"
        )
    # Nothing names this user as owner: drop lines owned by someone else we
    # recognise (the "with" partner) and accept a single leftover line.
    unknown = [c for c, o in zip(choices, owners) if o is None]
    if len(unknown) == 1:
        return unknown[0]
    raise QueueMemberPickError(
        f"Couldn't tell which queue line is {display_name or uid}'s "
        f"(lines: {', '.join(repr(c.get('name')) for c in choices)})"
    )


def resolve_queue_member_value(
    bridge: Any,
    command: str,
    option_name: str,
    user_id: str,
    *,
    channel_id: str,
    display_name: str = "",
    queue: Iterable[dict] | None = None,
    guild_id: str | None = None,
    abort_ctx: Any = None,
) -> str:
    """Fetch autocomplete choices via the bridge and return the owner line's value."""
    result = bridge.autocomplete(
        command,
        channel_id,
        option_name,
        str(user_id),
        guild_id=guild_id,
        abort_ctx=abort_ctx,
    )
    choices = [c for c in (result or {}).get("choices") or [] if isinstance(c, dict)]
    logger.info(
        "/%s %s autocomplete for %s (%s): %s",
        command,
        option_name,
        display_name,
        user_id,
        [(c.get("name"), c.get("value")) for c in choices],
    )
    picked = pick_queue_member_choice(choices, user_id, display_name, queue)
    logger.info("/%s %s picked %r", command, option_name, picked.get("name"))
    return str(picked.get("value"))
