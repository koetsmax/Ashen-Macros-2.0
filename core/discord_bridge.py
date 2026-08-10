"""Localhost WebSocket client for the Vencord Discord bridge plugin.

Opt-in via Settings → Experimental → Vencord Discord bridge. When enabled,
Discord actions require the plugin (no keyboard fallback on bridge errors).
When off, callers use keyboard automation.

Guild / channel / emoji snowflakes come from the self-bot
(``POST /macros/discord_bridge_config``) when the experiment is enabled — not
hardcoded in this client.
"""

from __future__ import annotations

import json
import logging
import re
import threading
import time
import uuid
from typing import Any

import requests

from core.auth import auth_headers
from core.settings import config_bool, read_config
from staffcheck.abort import AbortError, check_abort, is_abort_requested

logger = logging.getLogger(__name__)

DEFAULT_PORT = 47832

_DISCORD_CHANNEL_LINK_RE = re.compile(
    r"(?:https?://)?(?:(?:ptb|canary)\.)?discord(?:app)?\.com/channels/"
    r"(?P<guild>\d{5,30}|@me)/(?P<channel>\d{5,30})(?:/(?P<message>\d{5,30}))?",
    re.IGNORECASE,
)
_SNOWFLAKE_RE = re.compile(r"^\d{5,30}$")
_CHANNEL_NAME_RE = re.compile(r"^#?([\w\-]+)$")

_bridge_lock = threading.Lock()
_bridge: "DiscordBridge | None" = None

_meta_lock = threading.Lock()
_meta: dict[str, Any] = {
    "guild_id": "",
    "pending_emoji": {"name": "pending", "id": ""},
    "leave_emojis": {},
    "leave_rules": {},
    "channels": {},
    "fetched_at": 0.0,
}
# Last channel the bridge successfully switched to (staffcheck / queue reuse).
_active_channel_id = ""
_active_guild_id = ""


def note_active_channel(channel_id: str, guild_id: str | None = None) -> None:
    """Remember the channel after a successful bridge switchChannel."""
    global _active_channel_id, _active_guild_id
    cid = str(channel_id or "").strip()
    if not cid:
        return
    _active_channel_id = cid
    if guild_id:
        _active_guild_id = str(guild_id).strip()


def active_channel_id() -> str:
    return str(_active_channel_id or "").strip()


def active_guild_id() -> str:
    return str(_active_guild_id or queue_guild_id() or "").strip()


def is_enabled() -> bool:
    """True when Experimental → Vencord Discord bridge is on."""
    return config_bool("vencord_bridge", "false")


def bridge_port() -> int:
    raw = str(read_config().get("vencord_bridge_port") or DEFAULT_PORT).strip()
    try:
        port = int(raw)
    except ValueError:
        return DEFAULT_PORT
    return port if 1 <= port <= 65535 else DEFAULT_PORT


def bridge_token() -> str:
    return str(read_config().get("vencord_bridge_token") or "").strip()


def get_bridge_meta() -> dict[str, Any]:
    """Cached guild / channels / emoji / leave rules from the bot."""
    with _meta_lock:
        return {
            "guild_id": str(_meta.get("guild_id") or ""),
            "pending_emoji": dict(_meta.get("pending_emoji") or {}),
            "leave_emojis": dict(_meta.get("leave_emojis") or {}),
            "leave_rules": dict(_meta.get("leave_rules") or {}),
            "channels": dict(_meta.get("channels") or {}),
            "fetched_at": float(_meta.get("fetched_at") or 0),
        }


def queue_guild_id() -> str:
    return str(get_bridge_meta().get("guild_id") or "").strip()


def queue_channel_id() -> str:
    channels = get_bridge_meta().get("channels") or {}
    return str(channels.get("queue") or "").strip()


def on_duty_channel_id() -> str:
    """#on-duty-chat snowflake from bot bridge config."""
    channels = get_bridge_meta().get("channels") or {}
    return str(channels.get("on-duty-chat") or "").strip()


def leave_channel_id() -> str:
    """#leave-channel snowflake from bot bridge config."""
    channels = get_bridge_meta().get("channels") or {}
    return str(channels.get("leave-channel") or "").strip()


def pending_emoji() -> dict[str, str]:
    emoji = get_bridge_meta().get("pending_emoji") or {}
    name = str(emoji.get("name") or "pending").strip() or "pending"
    eid = str(emoji.get("id") or "").strip()
    out: dict[str, str] = {"name": name}
    if eid:
        out["id"] = eid
    return out


def _leave_emoji_raw(key: str) -> dict[str, Any]:
    emojis = get_bridge_meta().get("leave_emojis") or {}
    raw = emojis.get(key) if isinstance(emojis, dict) else None
    return dict(raw) if isinstance(raw, dict) else {}


def leave_mark_emoji(kind: str) -> dict[str, str]:
    """Tick/cross emoji for leave notices (honours animated experimental setting)."""
    use_animated = config_bool("leave_animated_emojis", "false")
    kind = str(kind or "").strip().lower()
    if kind not in ("tick", "cross"):
        kind = "tick"
    key = f"{kind}_animated" if use_animated else kind
    fallbacks = {
        "tick": ("BetterTick", "759587710251434084"),
        "tick_animated": ("bettertickanimated", "801634198058041346"),
        "cross": ("Cross", "705566721448214530"),
        "cross_animated": ("bettercross", "908384563477229588"),
    }
    raw = _leave_emoji_raw(key) or _leave_emoji_raw(kind)
    name_fb, id_fb = fallbacks.get(key) or fallbacks[kind]
    name = str(raw.get("name") or name_fb).strip() or name_fb
    eid = str(raw.get("id") or id_fb).strip() or id_fb
    out: dict[str, str] = {"name": name}
    if eid:
        out["id"] = eid
    return out


def leave_warning_rule(rule_number: str | int = 3) -> str:
    """Full Rule #N warning text from bot scrape (empty if unavailable)."""
    rules = get_bridge_meta().get("leave_rules") or {}
    key = str(rule_number).strip()
    text = str(rules.get(key) or "").strip()
    if text:
        return text
    # Local fallback until the bot scrapes #rules.
    return (
        "Rule #3: While on an active (non-legacy) fleet, you must give a warning "
        "before leaving a ship by using /leave-ship 10 minutes before you plan to "
        "leave the ship. Leaving significantly before or after the 10 minutes is "
        "not acceptable, however, you are allowed to leave earlier if a "
        "replacement is already on your ship."
    )


def queue_channel_jump_url() -> str:
    """discord.com/channels/{guild}/{queue} for Ctrl+K paste fallback."""
    gid = queue_guild_id()
    cid = queue_channel_id()
    if gid and cid:
        return f"https://discord.com/channels/{gid}/{cid}"
    return ""


def channel_id_for_name(name: str) -> str | None:
    """Map ``#on-duty-chat`` / ``on-duty-chat`` to a snowflake from bot config."""
    raw = (name or "").strip()
    if not raw:
        return None
    match = _CHANNEL_NAME_RE.match(raw)
    if not match:
        return None
    key = match.group(1).lower()
    channels = get_bridge_meta().get("channels") or {}
    cid = channels.get(key)
    return str(cid).strip() if cid else None


def apply_bridge_meta(payload: dict | None) -> bool:
    """Store bot-provided bridge config. Returns True when channels were applied."""
    if not isinstance(payload, dict):
        return False
    guild_id = str(payload.get("guild_id") or "").strip()
    channels_raw = payload.get("channels")
    channels: dict[str, str] = {}
    if isinstance(channels_raw, dict):
        for key, value in channels_raw.items():
            k = str(key or "").strip().lstrip("#").lower()
            v = str(value or "").strip()
            if k and v and _SNOWFLAKE_RE.match(v):
                channels[k] = v
    emoji_raw = payload.get("pending_emoji")
    emoji: dict[str, str] = {"name": "pending", "id": ""}
    if isinstance(emoji_raw, dict):
        emoji["name"] = str(emoji_raw.get("name") or "pending").strip() or "pending"
        emoji["id"] = str(emoji_raw.get("id") or "").strip()

    leave_emojis: dict[str, dict[str, Any]] = {}
    leave_raw = payload.get("leave_emojis")
    if isinstance(leave_raw, dict):
        for key, value in leave_raw.items():
            if not isinstance(value, dict):
                continue
            k = str(key or "").strip().lower()
            if not k:
                continue
            leave_emojis[k] = {
                "name": str(value.get("name") or "").strip(),
                "id": str(value.get("id") or "").strip(),
                "animated": bool(value.get("animated")),
                "ok": bool(value.get("ok", True)),
            }

    leave_rules: dict[str, str] = {}
    rules_raw = payload.get("leave_rules")
    if isinstance(rules_raw, dict):
        for key, value in rules_raw.items():
            k = str(key or "").strip()
            v = str(value or "").strip()
            if k and v:
                leave_rules[k] = v

    if not guild_id and not channels and not leave_emojis and not leave_rules:
        return False
    with _meta_lock:
        if guild_id:
            _meta["guild_id"] = guild_id
        if channels:
            _meta["channels"] = channels
        if emoji.get("id") or emoji.get("name"):
            _meta["pending_emoji"] = emoji
        if leave_emojis:
            _meta["leave_emojis"] = leave_emojis
        if leave_rules:
            _meta["leave_rules"] = leave_rules
        _meta["fetched_at"] = time.time()
    logger.info(
        "Discord bridge meta loaded (guild=%s channels=%s leave_rules=%s)",
        guild_id or "?",
        ",".join(sorted(channels)) or "none",
        ",".join(sorted(leave_rules)) or "none",
    )
    return True


def fetch_bridge_meta(*, force: bool = False) -> bool:
    """POST /macros/discord_bridge_config when the experiment is on.

    No-op when disabled. Safe to call on launch and after enabling the toggle.
    """
    if not is_enabled():
        return False
    if not force:
        with _meta_lock:
            if _meta.get("channels") and _meta.get("guild_id"):
                return True
    try:
        api_url = read_config().get("api_url") or ""
        if not api_url:
            return False
        response = requests.post(
            f"{api_url.rstrip('/')}/macros/discord_bridge_config",
            json={},
            timeout=8,
            headers=auth_headers(),
        )
        if response.status_code != 200:
            logger.warning(
                "discord_bridge_config HTTP %s", response.status_code
            )
            return False
        data = response.json()
        return apply_bridge_meta(data if isinstance(data, dict) else None)
    except Exception:
        logger.warning("Failed to fetch discord_bridge_config", exc_info=True)
        return False


def parse_discord_channel_link(text: str) -> dict[str, str | None]:
    """Parse discord.com/channels/{guild}/{channel}[/{message}] links.

    Returns keys guild_id, channel_id, message_id (values may be None).
    """
    empty: dict[str, str | None] = {
        "guild_id": None,
        "channel_id": None,
        "message_id": None,
    }
    raw = (text or "").strip()
    if not raw:
        return empty
    match = _DISCORD_CHANNEL_LINK_RE.search(raw)
    if not match:
        return empty
    guild = match.group("guild")
    return {
        "guild_id": None if guild == "@me" else guild,
        "channel_id": match.group("channel"),
        "message_id": match.group("message"),
    }


def resolve_channel_id(channel: str) -> str | None:
    """Resolve jump URL, snowflake, or #name (via bot meta) to a channel id."""
    raw = (channel or "").strip()
    if not raw:
        return None
    parsed = parse_discord_channel_link(raw)
    if parsed.get("channel_id"):
        return str(parsed["channel_id"])
    if _SNOWFLAKE_RE.match(raw):
        return raw
    return channel_id_for_name(raw)


def get_bridge() -> "DiscordBridge":
    """Return the shared bridge client (created lazily)."""
    global _bridge
    with _bridge_lock:
        if _bridge is None:
            _bridge = DiscordBridge()
        return _bridge


def is_connected() -> bool:
    if not is_enabled():
        return False
    return get_bridge().is_connected()


def bridge_plugin_version() -> str:
    """Plugin version from the last hello (empty if unknown / disconnected)."""
    if not is_enabled():
        return ""
    return get_bridge().plugin_version()


def prefer_bridge() -> bool:
    """True when Experimental is on and the plugin is connected + authed."""
    if not is_enabled():
        return False
    bridge = get_bridge()
    bridge.ensure_started()
    return bridge.is_connected()


def sync_bridge_lifecycle() -> None:
    """Start or stop the background client to match the Experimental toggle."""
    bridge = get_bridge()
    if is_enabled():
        fetch_bridge_meta(force=True)
        bridge.ensure_started()
    else:
        bridge.stop()


class DiscordBridgeError(RuntimeError):
    """Bridge request failed or returned ok=false."""


class DiscordBridge:
    """Background WebSocket client talking to the Vencord plugin on localhost."""

    def __init__(self) -> None:
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._ws = None
        self._send_lock = threading.Lock()
        self._pending_lock = threading.Lock()
        self._pending: dict[str, dict[str, Any]] = {}
        self._connected = threading.Event()
        self._authed = threading.Event()
        self._auth_failed = False
        self._last_error = ""
        self._plugin_version = ""
        self._start_lock = threading.Lock()

    def is_connected(self) -> bool:
        return self._connected.is_set() and self._authed.is_set() and not self._auth_failed

    def plugin_version(self) -> str:
        return str(self._plugin_version or "").strip()

    def _capture_plugin_version(self, data: dict) -> None:
        """Store bridge plugin version from hello/auth/pong — not Discord payloads.

        Slash/messageCommand results include ``version`` as the application
        command snowflake; treating those as the plugin version makes the hub
        status show a long id after the first command.
        """
        ver = str(data.get("version") or "").strip()
        if not ver:
            return
        msg_type = str(data.get("type") or "")
        if data.get("plugin") or msg_type in ("hello", "needsAuth") or data.get("pong") is True:
            self._plugin_version = ver

    def last_error(self) -> str:
        return self._last_error

    def ensure_started(self) -> None:
        if not is_enabled():
            return
        with self._start_lock:
            if self._thread and self._thread.is_alive():
                return
            self._stop.clear()
            self._thread = threading.Thread(
                target=self._run, name="discord-bridge", daemon=True
            )
            self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        ws = self._ws
        if ws is not None:
            try:
                ws.close()
            except Exception:
                pass
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=3)
        self._thread = None
        self._connected.clear()
        self._authed.clear()
        self._plugin_version = ""
        self._fail_pending("Bridge stopped")
        with self._pending_lock:
            self._pending.clear()

    def ping(self, *, abort_ctx: Any = None, timeout: float = 10.0, delay_ms: int = 0) -> dict:
        payload: dict[str, Any] = {}
        if delay_ms > 0:
            payload["delayMs"] = int(delay_ms)
            timeout = max(timeout, delay_ms / 1000.0 + 5.0)
        return self.request("ping", abort_ctx=abort_ctx, timeout=timeout, **payload)

    def react(
        self,
        channel_id: str,
        message_id: str,
        emoji: dict | str,
        *,
        guild_id: str | None = None,
        abort_ctx: Any = None,
        timeout: float = 15.0,
    ) -> dict:
        if isinstance(emoji, str):
            emoji_payload: dict[str, Any] = {"name": emoji}
        else:
            emoji_payload = dict(emoji)
        payload: dict[str, Any] = {
            "channelId": str(channel_id),
            "messageId": str(message_id),
            "emoji": emoji_payload,
        }
        if guild_id:
            payload["guildId"] = str(guild_id)
        return self.request("react", abort_ctx=abort_ctx, timeout=timeout, **payload)

    def edit(
        self,
        channel_id: str,
        message_id: str,
        content: str,
        *,
        abort_ctx: Any = None,
        timeout: float = 15.0,
    ) -> dict:
        return self.request(
            "edit",
            abort_ctx=abort_ctx,
            timeout=timeout,
            channelId=str(channel_id),
            messageId=str(message_id),
            content=content,
        )

    def send(
        self,
        channel_id: str,
        content: str,
        *,
        abort_ctx: Any = None,
        timeout: float = 15.0,
    ) -> dict:
        return self.request(
            "send",
            abort_ctx=abort_ctx,
            timeout=timeout,
            channelId=str(channel_id),
            content=content,
        )

    def switch_channel(
        self,
        channel_id: str,
        *,
        guild_id: str | None = None,
        abort_ctx: Any = None,
        timeout: float = 15.0,
    ) -> dict:
        payload: dict[str, Any] = {"channelId": str(channel_id)}
        if guild_id:
            payload["guildId"] = str(guild_id)
        return self.request(
            "switchChannel", abort_ctx=abort_ctx, timeout=timeout, **payload
        )

    def message_command(
        self,
        name: str,
        channel_id: str,
        message_id: str,
        *,
        guild_id: str | None = None,
        abort_ctx: Any = None,
        timeout: float = 20.0,
    ) -> dict:
        payload: dict[str, Any] = {
            "name": name,
            "channelId": str(channel_id),
            "messageId": str(message_id),
        }
        if guild_id:
            payload["guildId"] = str(guild_id)
        return self.request(
            "messageCommand", abort_ctx=abort_ctx, timeout=timeout, **payload
        )

    def slash_command(
        self,
        name: str,
        channel_id: str,
        options: list[dict] | None = None,
        *,
        guild_id: str | None = None,
        abort_ctx: Any = None,
        timeout: float = 20.0,
        choice_index: int | None = None,
        wait_for_response: bool = False,
        wait_ms: int = 15000,
    ) -> dict:
        payload: dict[str, Any] = {
            "name": name.lstrip("/"),
            "channelId": str(channel_id),
            "options": list(options or []),
        }
        if guild_id:
            payload["guildId"] = str(guild_id)
        if choice_index is not None:
            payload["choiceIndex"] = int(choice_index)
        if wait_for_response:
            payload["waitForResponse"] = True
            payload["waitMs"] = max(500, int(wait_ms or 15000))
        # Autocomplete option resolution can take a few seconds per option.
        # Waiting for the ephemeral response needs extra headroom.
        timeout = max(timeout, 12.0 + 5.0 * len(payload["options"]))
        if wait_for_response:
            wait_s = max(payload.get("waitMs", 15000), 15000) / 1000.0
            timeout = max(timeout, wait_s + 10.0)
        result = self.request(
            "slashCommand", abort_ctx=abort_ctx, timeout=timeout, **payload
        )
        if wait_for_response and not str(result.get("messageId") or "").strip():
            # Distinguishes "plugin ignored waitForResponse" (ok + no id) from
            # a timeout error (ok: false), which raises earlier.
            raise DiscordBridgeError(
                f"slashCommand /{name.lstrip('/')} did not return messageId "
                f"(ephemerals do have ids — wait/match failed or plugin needs "
                f"reload so waitForResponse is honored: {result!r})"
            )
        return result

    def click_button(
        self,
        channel_id: str,
        message_id: str | None = None,
        *,
        label: str,
        guild_id: str | None = None,
        abort_ctx: Any = None,
        timeout: float = 15.0,
    ) -> dict:
        """Click a message component button by exact label.

        ``message_id`` is optional: the plugin uses the last slashCommand
        waitForResponse ephemeral (Discord has no Copy Message ID on those).
        """
        lab = str(label or "").strip()
        if not lab:
            raise DiscordBridgeError("click_button requires label")
        payload: dict[str, Any] = {
            "channelId": str(channel_id),
            "label": lab,
        }
        mid = str(message_id or "").strip()
        if mid:
            payload["messageId"] = mid
        if guild_id:
            payload["guildId"] = str(guild_id)
        # Ashen may edit Confirm/Cancel in after the ephemeral create.
        return self.request(
            "clickButton", abort_ctx=abort_ctx, timeout=max(timeout, 20.0), **payload
        )

    def autocomplete(
        self,
        name: str,
        channel_id: str,
        option_name: str,
        query: str,
        *,
        guild_id: str | None = None,
        options: list[dict] | None = None,
        choice_index: int | None = None,
        abort_ctx: Any = None,
        timeout: float = 12.0,
    ) -> dict:
        """Ask the Ashen bot (via Discord) for slash-option autocomplete choices.

        Returns choices like ``{"name": "5: Max -- …", "value": "<uuid>"}`` plus
        a ``picked`` entry (first / best match, or ``choice_index``).
        """
        payload: dict[str, Any] = {
            "name": name.lstrip("/"),
            "channelId": str(channel_id),
            "optionName": option_name,
            "query": query,
        }
        if guild_id:
            payload["guildId"] = str(guild_id)
        if options:
            payload["options"] = list(options)
        if choice_index is not None:
            payload["choiceIndex"] = int(choice_index)
        return self.request(
            "autocomplete", abort_ctx=abort_ctx, timeout=timeout, **payload
        )

    def cancel(self, request_id: str | None = None) -> None:
        """Cancel one in-flight request, or all if request_id is None."""
        ids: list[str]
        with self._pending_lock:
            if request_id:
                ids = [request_id] if request_id in self._pending else []
            else:
                ids = list(self._pending.keys())
        for rid in ids:
            try:
                # Plugin treats id as the target when targetId is omitted.
                self._send_raw({"id": rid, "type": "cancel", "targetId": rid})
            except Exception:
                logger.debug("Failed to send cancel for %s", rid, exc_info=True)
            with self._pending_lock:
                entry = self._pending.get(rid)
                if entry is not None:
                    entry["response"] = {
                        "id": rid,
                        "type": "result",
                        "ok": False,
                        "error": "cancelled",
                        "cancelled": True,
                    }
                    entry["event"].set()

    def request(
        self,
        type: str,
        *,
        abort_ctx: Any = None,
        timeout: float = 15.0,
        **payload: Any,
    ) -> dict:
        if not is_enabled():
            raise DiscordBridgeError("Vencord bridge is disabled")
        if abort_ctx is not None:
            check_abort(abort_ctx)

        self.ensure_started()
        if not self._wait_until_ready(timeout=min(timeout, 8.0), abort_ctx=abort_ctx):
            err = self._last_error or "Bridge not connected"
            raise DiscordBridgeError(err)

        if abort_ctx is not None:
            check_abort(abort_ctx)

        request_id = str(uuid.uuid4())
        event = threading.Event()
        with self._pending_lock:
            self._pending[request_id] = {"event": event, "response": None}

        message = {"id": request_id, "type": type, **payload}
        try:
            self._send_raw(message)
            deadline = time.time() + timeout
            while not event.wait(0.05):
                if abort_ctx is not None and is_abort_requested(abort_ctx):
                    self.cancel(request_id)
                    raise AbortError()
                if time.time() >= deadline:
                    self.cancel(request_id)
                    raise DiscordBridgeError(f"Bridge request timed out ({type})")
            with self._pending_lock:
                entry = self._pending.get(request_id) or {}
                response = entry.get("response")
            if not isinstance(response, dict):
                raise DiscordBridgeError(f"Empty bridge response ({type})")
            if response.get("cancelled"):
                if abort_ctx is not None and is_abort_requested(abort_ctx):
                    raise AbortError()
                raise DiscordBridgeError("Bridge request cancelled")
            if response.get("ok") is False:
                err = str(response.get("error") or f"Bridge {type} failed")
                # Always land Vencord-side failures in ashen-macros.log.
                logger.warning("Discord bridge %s failed: %s", type, err)
                if (
                    "Application command not found in index" in err
                    or "Open the Apps / slash menu once" in err
                ):
                    try:
                        from staffcheck.qt_ui import warn_command_index_miss

                        warn_command_index_miss(err)
                    except Exception:
                        pass
                raise DiscordBridgeError(err)
            return response
        finally:
            with self._pending_lock:
                self._pending.pop(request_id, None)

    def _wait_until_ready(self, *, timeout: float, abort_ctx: Any) -> bool:
        deadline = time.time() + timeout
        while time.time() < deadline:
            if abort_ctx is not None:
                check_abort(abort_ctx)
            if self.is_connected():
                return True
            if self._auth_failed:
                return False
            time.sleep(0.05)
        return self.is_connected()

    def _send_raw(self, payload: dict) -> None:
        ws = self._ws
        if ws is None:
            raise DiscordBridgeError("Bridge socket not connected")
        data = json.dumps(payload)
        with self._send_lock:
            ws.send(data)

    def _fail_pending(self, error: str) -> None:
        with self._pending_lock:
            for entry in self._pending.values():
                if entry.get("response") is None:
                    entry["response"] = {
                        "type": "result",
                        "ok": False,
                        "error": error,
                    }
                entry["event"].set()

    def _run(self) -> None:
        try:
            import websocket
        except ImportError:
            self._last_error = "websocket-client not installed"
            logger.error("websocket-client is required for the Vencord Discord bridge")
            return

        while not self._stop.is_set():
            if not is_enabled():
                break
            port = bridge_port()
            url = f"ws://127.0.0.1:{port}"
            self._auth_failed = False
            self._connected.clear()
            self._authed.clear()
            self._last_error = ""
            try:
                self._ws = websocket.WebSocketApp(
                    url,
                    on_open=self._on_open,
                    on_message=self._on_message,
                    on_error=self._on_error,
                    on_close=self._on_close,
                )
                self._ws.run_forever(ping_interval=20, ping_timeout=10)
            except Exception as exc:
                self._last_error = str(exc)
                logger.debug("Discord bridge run error: %s", exc)
            self._ws = None
            self._connected.clear()
            self._authed.clear()
            self._fail_pending(self._last_error or "Bridge disconnected")
            if self._stop.wait(3):
                break

    def _on_open(self, _ws) -> None:
        self._connected.set()
        self._last_error = ""
        token = bridge_token()
        auth_id = str(uuid.uuid4())
        event = threading.Event()
        with self._pending_lock:
            self._pending[auth_id] = {"event": event, "response": None}
        try:
            self._send_raw({"id": auth_id, "type": "auth", "token": token})
        except Exception as exc:
            self._auth_failed = True
            self._last_error = f"Auth send failed: {exc}"
            with self._pending_lock:
                self._pending.pop(auth_id, None)
            try:
                _ws.close()
            except Exception:
                pass
            return

        def _await_auth() -> None:
            if not event.wait(8):
                self._auth_failed = True
                self._last_error = "Bridge auth timed out"
                with self._pending_lock:
                    self._pending.pop(auth_id, None)
                try:
                    _ws.close()
                except Exception:
                    pass
                return
            with self._pending_lock:
                entry = self._pending.pop(auth_id, {}) or {}
                response = entry.get("response") or {}
            if response.get("ok") is False or response.get("type") == "auth_failed":
                self._auth_failed = True
                self._last_error = str(
                    response.get("error") or "Bridge auth failed"
                )
                try:
                    _ws.close()
                except Exception:
                    pass
                return
            if (
                response.get("ok") is True
                or response.get("type") in ("auth_ok", "authenticated", "result")
            ):
                self._capture_plugin_version(response)
                self._authed.set()
                self._auth_failed = False
                self._last_error = ""
                logger.info("Discord bridge authenticated on port %s", bridge_port())
                return
            self._auth_failed = True
            self._last_error = str(
                response.get("error") or "Unexpected auth response"
            )
            try:
                _ws.close()
            except Exception:
                pass

        threading.Thread(target=_await_auth, name="discord-bridge-auth", daemon=True).start()

    def _on_message(self, _ws, message: str) -> None:
        try:
            data = json.loads(message)
        except json.JSONDecodeError:
            logger.warning("Invalid Discord bridge JSON")
            return
        if not isinstance(data, dict):
            return

        msg_type = str(data.get("type") or "")
        if msg_type in ("hello", "needsAuth"):
            self._capture_plugin_version(data)
            return

        request_id = data.get("id")
        if request_id is None:
            return
        with self._pending_lock:
            entry = self._pending.get(str(request_id))
            if entry is None:
                return
            # Normalize auth failure shapes.
            if msg_type in ("auth_failed", "error") and "ok" not in data:
                data = {**data, "ok": False, "error": data.get("error") or msg_type}
            elif msg_type in ("auth_ok", "authenticated") and "ok" not in data:
                data = {**data, "ok": True}
            entry["response"] = data
            entry["event"].set()
            if data.get("ok") is not False:
                self._capture_plugin_version(data)
    def _on_error(self, _ws, error) -> None:
        self._last_error = str(error)
        # Avoid noisy logs while the plugin is simply not running.
        logger.debug("Discord bridge error: %s", error)

    def _on_close(self, _ws, status_code, msg) -> None:
        self._connected.clear()
        self._authed.clear()
        self._plugin_version = ""
        logger.debug("Discord bridge closed: %s %s", status_code, msg)
