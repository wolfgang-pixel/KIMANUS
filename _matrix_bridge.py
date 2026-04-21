# -*- coding: utf-8 -*-
"""KIMANUS Matrix-Bruecke: App -> Hermes ueber Matrix-API.

Eingebaut 21.04.2026. Sendet Nachrichten als @kimanus-app in einen DM-Raum
mit @kimanus (Hermes), wartet auf die finale Antwort.
"""

import os
import time as _time
import asyncio
import logging
import re
from aiohttp import ClientSession, ClientTimeout

log = logging.getLogger("kimanus")

MATRIX_HOMESERVER_INTERNAL = os.environ.get("MATRIX_HOMESERVER_INTERNAL", "http://synapse:8008")
MATRIX_APP_TOKEN = os.environ.get("MATRIX_APP_TOKEN", "")
MATRIX_HERMES_ROOM = os.environ.get("MATRIX_HERMES_ROOM", "")
MATRIX_HERMES_USER = os.environ.get("MATRIX_HERMES_USER", "@kimanus:matrix.srv905622.hstgr.cloud")
MATRIX_TIMEOUT = int(os.environ.get("MATRIX_TIMEOUT", "120"))

_since_cache = {}

_SKIP_MARKERS = ("home channel", "/sethome", "cron job results")
_TOOL_RX = re.compile(
    r"^[^A-Za-z0-9]{0,4}(read_file|write_file|edit_file|grep|bash|str_replace|glob|list_dir|run_command|search)[\s:_]",
    re.IGNORECASE,
)


def _should_skip(text):
    if not text:
        return True
    low = text.lower()
    if any(m in low for m in _SKIP_MARKERS) and len(text) < 400:
        return True
    # Tool-Call-Status ("read_file: /opt/vault/...", "grep: pattern")
    if len(text) < 200 and _TOOL_RX.match(text):
        return True
    # Sehr kurze Emoji-Statuszeilen (echtes Emoji-Codepoint, nicht Markdown)
    # Markdown-Zeichen (*, -, #, >, etc.) sind OK und duerfen durch
    if len(text) < 100 and ord(text[0]) > 0x2000 and ord(text[0]) < 0xFE00:
        return True
    return False


def _extract_text(event):
    content = event.get("content") or {}
    relates = content.get("m.relates_to") or {}
    if relates.get("rel_type") == "m.replace":
        new_content = content.get("m.new_content") or {}
        return (new_content.get("body") or "").strip()
    if content.get("msgtype") != "m.text":
        return ""
    return (content.get("body") or "").strip()


async def call_kimanus_via_matrix(message, session_id="default"):
    """Sendet Nachricht an KIMANUS (Hermes) und wartet auf Antwort.

    Rueckgabe: (antwort_text, error_or_None)
    """
    if not MATRIX_APP_TOKEN or not MATRIX_HERMES_ROOM:
        return ("", "Matrix-Bruecke nicht konfiguriert.")

    token = MATRIX_APP_TOKEN
    room_id = MATRIX_HERMES_ROOM
    bot_user = MATRIX_HERMES_USER
    homeserver = MATRIX_HOMESERVER_INTERNAL

    client_timeout = ClientTimeout(total=MATRIX_TIMEOUT + 30)

    try:
        async with ClientSession(timeout=client_timeout) as s:
            # Immer frischen since-Token holen (sonst verpasst Bridge Antworten
            # wenn sie zwischen Requests zu alte Tokens behaelt)
            async with s.get(
                f"{homeserver}/_matrix/client/v3/sync",
                params={"timeout": "0", "access_token": token},
            ) as r:
                if r.status != 200:
                    return ("", f"/sync Initial fehlgeschlagen: HTTP {r.status}")
                initial = await r.json()
                since = initial.get("next_batch")

            # Nachricht senden
            body = f"[session:{session_id}]\n{message}" if session_id != "default" else message
            txn = str(int(_time.time() * 1000))
            async with s.put(
                f"{homeserver}/_matrix/client/v3/rooms/{room_id}/send/m.room.message/{txn}",
                params={"access_token": token},
                json={"msgtype": "m.text", "body": body},
            ) as r:
                if r.status not in (200, 201):
                    txt = await r.text()
                    return ("", f"/send fehlgeschlagen: HTTP {r.status} - {txt[:200]}")

            # Antwort abwarten mit Stille-Detection
            deadline = _time.time() + MATRIX_TIMEOUT
            last_answer = None
            last_change = _time.time()
            QUIET = 3.0  # Sekunden Stille = fertig

            while _time.time() < deadline:
                remaining_ms = int(max(1000, (deadline - _time.time()) * 1000))
                wait_ms = min(remaining_ms, 8000)
                async with s.get(
                    f"{homeserver}/_matrix/client/v3/sync",
                    params={
                        "since": since,
                        "timeout": str(wait_ms),
                        "access_token": token,
                    },
                ) as r:
                    if r.status != 200:
                        return ("", f"/sync fehlgeschlagen: HTTP {r.status}")
                    sync = await r.json()

                since = sync.get("next_batch", since)
                _since_cache[session_id] = since

                room = (sync.get("rooms") or {}).get("join", {}).get(room_id) or {}
                events = (room.get("timeline") or {}).get("events") or []

                for event in events:
                    if event.get("type") != "m.room.message":
                        continue
                    if event.get("sender") != bot_user:
                        continue
                    text = _extract_text(event)
                    if not text or _should_skip(text):
                        continue
                    if text != last_answer:
                        last_answer = text
                        last_change = _time.time()

                if last_answer and (_time.time() - last_change) >= QUIET:
                    return (last_answer, None)

            # Timeout
            if last_answer:
                return (last_answer, None)
            return ("Keine Antwort von KIMANUS (Timeout).", None)

    except asyncio.TimeoutError:
        return ("Network-Timeout im Matrix-Sync.", None)
    except Exception as e:
        log.error(f"Matrix-Bruecke Fehler: {e}")
        return ("", str(e))
