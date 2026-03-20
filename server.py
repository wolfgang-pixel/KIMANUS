#!/usr/bin/env python3
"""
KIMANUS OS Backend - Chat API + Voice Pipeline + Static File Server
Mit Auto-Routing und Streaming Voice (Groq Whisper STT + LLM Stream + Edge TTS)
"""

import asyncio
import json
import os
import re
import io
import base64
import logging
from datetime import datetime, timezone, timedelta
from aiohttp import web, ClientSession, ClientTimeout, FormData, UnixConnector
import edge_tts

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("kimanus")

# Config
LITELLM_URL = os.environ.get("LITELLM_URL", "http://litellm:4000/v1/chat/completions")
LITELLM_KEY = os.environ.get("LITELLM_KEY", "sk-manus-geheimschluessel-1234")
DEFAULT_MODEL = os.environ.get("DEFAULT_MODEL", "deepseek")
WORKSPACE = os.environ.get("WORKSPACE_PATH", "/workspace")
STATIC_DIR = os.environ.get("STATIC_DIR", "/app/static")
MAX_TOKENS = int(os.environ.get("MAX_TOKENS", "4000"))

# Groq Whisper STT
GROQ_API_URL = "https://api.groq.com/openai/v1/audio/transcriptions"
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
GROQ_WHISPER_MODEL = "whisper-large-v3-turbo"

# OpenAI TTS (Premium - natuerliche Stimme wie ChatGPT)
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
OPENAI_TTS_URL = "https://api.openai.com/v1/audio/speech"
OPENAI_TTS_MODEL = "gpt-4o-mini-tts-2025-12-15"  # Neuester Snapshot, 35% besseres Deutsch
TTS_ENGINE = os.environ.get("TTS_ENGINE", "openai" if OPENAI_API_KEY else "edge")

# OpenAI TTS Stimmen (alle verfuegbaren)
OPENAI_VOICE_CATALOG = {
    "alloy":   {"name": "Alloy",   "gender": "n", "style": "Neutral, ausgewogen"},
    "ash":     {"name": "Ash",     "gender": "m", "style": "Warm, gespraechig"},
    "ballad":  {"name": "Ballad",  "gender": "m", "style": "Ausdrucksvoll, erzaehlend"},
    "cedar":   {"name": "Cedar",   "gender": "m", "style": "Ruhig, natuerlich (neu)"},
    "coral":   {"name": "Coral",   "gender": "f", "style": "Warm, freundlich"},
    "echo":    {"name": "Echo",    "gender": "m", "style": "Klar, praezise"},
    "fable":   {"name": "Fable",   "gender": "m", "style": "Britisch, charmant"},
    "marin":   {"name": "Marin",   "gender": "f", "style": "Natuerlich, klar (neu, empfohlen)"},
    "nova":    {"name": "Nova",    "gender": "f", "style": "Warm, natuerlich"},
    "onyx":    {"name": "Onyx",    "gender": "m", "style": "Tief, autoritaer"},
    "sage":    {"name": "Sage",    "gender": "f", "style": "Ruhig, weise"},
    "shimmer": {"name": "Shimmer", "gender": "f", "style": "Hell, optimistisch"},
    "verse":   {"name": "Verse",   "gender": "m", "style": "Vielseitig, lebendig (neu)"},
}

# Standard-Stimmen pro Agent
OPENAI_VOICES = {
    "kai": "onyx",     # Maennlich, tief, autoritaer
    "kim": "nova",     # Weiblich, warm, natuerlich
}
OPENAI_VOICE_DEFAULT = "onyx"

# Edge TTS Stimmen pro Agent (Fallback)
TTS_VOICES = {
    "kai": "de-DE-FlorianMultilingualNeural",
    "kim": "de-DE-SeraphinaMultilingualNeural",
}
TTS_DEFAULT_VOICE = "de-DE-FlorianMultilingualNeural"

# Alle verfuegbaren deutschen Stimmen
AVAILABLE_VOICES = {
    "de-DE-FlorianMultilingualNeural":  {"name": "Florian",  "gender": "m", "style": "Modern, natuerlich", "locale": "DE"},
    "de-DE-SeraphinaMultilingualNeural":{"name": "Seraphina","gender": "f", "style": "Modern, natuerlich", "locale": "DE"},
    "de-DE-ConradNeural":               {"name": "Conrad",   "gender": "m", "style": "Sachlich, klar",     "locale": "DE"},
    "de-DE-KatjaNeural":                {"name": "Katja",    "gender": "f", "style": "Professionell",      "locale": "DE"},
    "de-DE-AmalaNeural":                {"name": "Amala",    "gender": "f", "style": "Warm, freundlich",   "locale": "DE"},
    "de-DE-KillianNeural":              {"name": "Killian",  "gender": "m", "style": "Jung, dynamisch",    "locale": "DE"},
    "de-AT-JonasNeural":                {"name": "Jonas",    "gender": "m", "style": "Oesterreichisch",    "locale": "AT"},
    "de-AT-IngridNeural":               {"name": "Ingrid",   "gender": "f", "style": "Oesterreichisch",    "locale": "AT"},
    "de-CH-JanNeural":                  {"name": "Jan",      "gender": "m", "style": "Schweizerdeutsch",   "locale": "CH"},
    "de-CH-LeniNeural":                 {"name": "Leni",     "gender": "f", "style": "Schweizerdeutsch",   "locale": "CH"},
}

# Session histories
sessions = {}

# === MODELL-KATALOG ===
MODEL_CATALOG = {
    "deepseek":        {"name": "DeepSeek V3",           "speed": "schnell",  "cost": "guenstig"},
    "groq-llama":      {"name": "Groq Llama 70B",        "speed": "blitz",    "cost": "gratis"},
    "gemini-flash":    {"name": "Gemini 2.5 Flash",      "speed": "schnell",  "cost": "guenstig"},
    "or-claude-sonnet":{"name": "Claude Sonnet 4",       "speed": "mittel",   "cost": "premium"},
    "or-gpt4o":        {"name": "GPT-4o",                "speed": "mittel",   "cost": "premium"},
    "qwen-local":      {"name": "Qwen Lokal",            "speed": "langsam",  "cost": "gratis"},
}

# === AUTO-ROUTING LOGIK ===
CODE_KEYWORDS = r'(code|programm|function|def |class |import |bug|debug|script|html|css|python|javascript|sql|api|json|fehler im code|syntax)'
CREATIVE_KEYWORDS = r'(schreib|gedicht|story|geschichte|kreativ|brief|text verfass|formulier|uebersetze|translate|dicht)'
ANALYSIS_KEYWORDS = r'(analysier|zusammenfass|erklaer|vergleich|bewert|recherchier|was ist|wie funktioniert|warum)'
QUICK_PATTERNS = r'^(ja|nein|ok|danke|hi|hallo|hey|gut|genau|stimmt|richtig|klar|mach|weiter)[\s!?.]*$'

# Satz-Trennmuster fuer chunked TTS
# Satz-Split: Bei . ! ? und auch bei , ; : (fuer schnellere Voice-Chunks)
SENTENCE_SPLIT = re.compile(r'(?<=[.!?])\s+|(?<=\.\.\.)\s+|(?<=[,;:])\s+|\n')


def auto_select_model(message, agent):
    """Waehlt intelligent das beste Modell basierend auf der Nachricht."""
    msg_lower = message.lower().strip()
    msg_len = len(message)

    if msg_len < 20 or re.match(QUICK_PATTERNS, msg_lower, re.IGNORECASE):
        return "groq-llama", "Kurze Nachricht -> Groq (blitzschnell)"

    if re.search(CODE_KEYWORDS, msg_lower, re.IGNORECASE):
        return "deepseek", "Code-Aufgabe -> DeepSeek (Code-Spezialist)"

    if re.search(CREATIVE_KEYWORDS, msg_lower, re.IGNORECASE):
        return "groq-llama", "Kreativ-Aufgabe -> Groq Llama (schnell & kreativ)"

    if msg_len > 500 or re.search(ANALYSIS_KEYWORDS, msg_lower, re.IGNORECASE):
        return "gemini-flash", "Analyse/langer Text -> Gemini Flash (grosser Kontext)"

    return "deepseek", "Standard -> DeepSeek V3"


# === WETTER (Open-Meteo, kostenlos, kein API-Key) ===
WEATHER_CACHE = {"data": None, "time": 0}

async def get_weather():
    """Aktuelles Wetter fuer Muenchen via Open-Meteo API."""
    import time
    now = time.time()
    # Cache 15 Minuten
    if WEATHER_CACHE["data"] and (now - WEATHER_CACHE["time"]) < 900:
        return WEATHER_CACHE["data"]
    try:
        url = (
            "https://api.open-meteo.com/v1/forecast?"
            "latitude=50.26&longitude=11.04"  # Ebersdorf bei Coburg
            "&current=temperature_2m,relative_humidity_2m,weather_code,wind_speed_10m"
            "&timezone=Europe/Berlin"
        )
        async with ClientSession() as session:
            async with session.get(url, timeout=ClientTimeout(total=5)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    c = data.get("current", {})
                    wmo = c.get("weather_code", 0)
                    # WMO Wetter-Codes vereinfacht
                    wetter_text = {
                        0: "Klar", 1: "Ueberwiegend klar", 2: "Teilweise bewoelkt",
                        3: "Bedeckt", 45: "Nebel", 48: "Reifnebel",
                        51: "Leichter Nieselregen", 53: "Nieselregen", 55: "Starker Nieselregen",
                        61: "Leichter Regen", 63: "Regen", 65: "Starker Regen",
                        71: "Leichter Schnee", 73: "Schnee", 75: "Starker Schnee",
                        80: "Regenschauer", 81: "Regenschauer", 82: "Starke Regenschauer",
                        95: "Gewitter", 96: "Gewitter mit Hagel", 99: "Starkes Gewitter"
                    }.get(wmo, "Unbekannt")
                    result = (
                        f"Wetter Muenchen: {c.get('temperature_2m', '?')}°C, "
                        f"{wetter_text}, "
                        f"Wind {c.get('wind_speed_10m', '?')} km/h, "
                        f"Luftfeuchtigkeit {c.get('relative_humidity_2m', '?')}%"
                    )
                    WEATHER_CACHE["data"] = result
                    WEATHER_CACHE["time"] = now
                    return result
    except Exception as e:
        log.warning(f"Wetter-Abfrage fehlgeschlagen: {e}")
    return None


def get_datetime_info():
    """Aktuelles Datum und Uhrzeit (deutsche Zeitzone CET/CEST)."""
    # Deutschland: UTC+1 (CET) bzw. UTC+2 (CEST Sommerzeit Maerz-Oktober)
    utc_now = datetime.now(timezone.utc)
    month = utc_now.month
    is_summer = 3 <= month <= 10  # Vereinfacht: Maerz bis Oktober = Sommerzeit
    de_tz = timezone(timedelta(hours=2 if is_summer else 1))
    now = utc_now.astimezone(de_tz)
    tage = ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"]
    tag = tage[now.weekday()]
    return f"Heute ist {tag}, der {now.strftime('%d.%m.%Y')}. Aktuelle Uhrzeit: {now.strftime('%H:%M')} Uhr."


# === SYSTEM PROMPTS ===
SYSTEM_PROMPTS = {
    "kai": (
        "Du bist KAI, der Business-Assistent im KIM Chat System. "
        "Dein Nutzer ist der Gruender von KIMANUS - dein Chef und Visionaer. "
        "Er hat dich erschaffen und arbeitet taeglich mit dir. Du kennst ihn gut. "
        "Du hilfst bei geschaeftlichen Anfragen, Recherche, Analysen "
        "und professionellen Aufgaben. "
        "Antworte auf Deutsch, professionell und effizient. "
        "Halte Antworten kompakt aber informativ. "
        "Sprich den Nutzer NICHT mit Namen an, sage niemals 'Wolfgang'. "
        "Antworte direkt und sachlich, wie ein vertrauter Geschaeftspartner. "
        "WICHTIG: Lies die USER.md im Kontext - dort stehen persoenliche Infos "
        "ueber deinen Nutzer (Wohnort, Familie, Interessen etc.). Nutze dieses Wissen! "
        "Wenn der Nutzer dir persoenliche Infos mitteilt, bestatige kurz dass du es dir merkst. "
        "Wenn nach Manus gefragt wird: Manus ist der Server-Agent fuer komplexe Aufgaben."
    ),
    "kim": (
        "Du bist KIM, der persoenliche Assistent im KIM Chat System. "
        "Dein Nutzer ist dein Schoepfer - ein kreativer Kopf und Visionaer. "
        "Er hat dich erschaffen und ihr arbeitet als Team. Du kennst ihn gut und magst ihn. "
        "Du hilfst bei privaten Anfragen, persoenlichen Aufgaben, "
        "Erinnerungen, Alltag und persoenlichen Fragen. "
        "Antworte auf Deutsch, freundlich, warmherzig und vertraut - wie ein guter Freund. "
        "Sprich den Nutzer NICHT mit Namen an, sage niemals 'Wolfgang'. "
        "Antworte direkt ohne Anrede, locker und persoenlich. "
        "WICHTIG: Lies die USER.md im Kontext - dort stehen persoenliche Infos "
        "ueber deinen Nutzer (Wohnort, Familie, Interessen etc.). Nutze dieses Wissen! "
        "Du KENNST deinen Nutzer. Frag nicht nach Dingen die in USER.md stehen. "
        "Wenn der Nutzer dir neue persoenliche Infos mitteilt, bestatige warmherzig dass du es dir merkst. "
        "Wenn nach Manus gefragt wird: Manus ist der Server-Agent fuer komplexe Aufgaben."
    )
}


def read_file(path):
    try:
        with open(path, "r") as f:
            return f.read()
    except:
        return ""


def build_context():
    """Laedt Gedaechtnis-Dateien als Kontext."""
    parts = []
    for name in ["SOUL.md", "AGENTS.md", "USER.md", "MEMORY.md"]:
        content = read_file(os.path.join(WORKSPACE, name))
        if content.strip():
            parts.append(f"=== {name} ===\n{content}")

    today = datetime.now().strftime("%Y-%m-%d")
    daily = read_file(os.path.join(WORKSPACE, "memory", f"{today}.md"))
    if daily.strip():
        parts.append(f"=== Tagesnotizen {today} ===\n{daily}")

    return "\n".join(parts)


async def extract_and_save_user_info(user_msg):
    """Erkennt persoenliche Infos in Nachrichten via LLM und speichert sie in USER.md.

    Statt fragiler Regex nutzen wir ein schnelles LLM (Groq Llama) um intelligent
    zu erkennen, ob der Nutzer etwas Persoenliches ueber sich erzaehlt hat.
    Kostet fast nichts (~0.001 Cent pro Aufruf) und versteht natuerliche Sprache.
    """
    # Kurze Nachrichten oder Emojis ueberspringen
    if len(user_msg.strip()) < 10:
        return

    # Aktuelle USER.md laden fuer Kontext
    user_md_path = os.path.join(WORKSPACE, "USER.md")
    current_profile = read_file(user_md_path)

    # LLM fragen ob persoenliche Infos in der Nachricht stecken
    extract_prompt = [
        {"role": "system", "content": (
            "Du bist ein Profil-Extraktor. Deine EINZIGE Aufgabe: Erkenne persoenliche Informationen "
            "in Nachrichten und gib sie als Stichpunkte zurueck.\n\n"
            "Persoenliche Infos sind z.B.: Name, Wohnort, PLZ, Familie (Frau, Kinder, Namen), "
            "Beruf, Alter, Geburtstag, Haustiere, Hobbys, Vorlieben, wichtige Termine, "
            "Korrekturen zu bestehenden Infos, oder explizite 'merk dir' Auftraege.\n\n"
            "AKTUELLES PROFIL (was wir schon wissen):\n"
            f"{current_profile}\n\n"
            "REGELN:\n"
            "- Wenn die Nachricht NEUE persoenliche Infos enthaelt die NICHT schon im Profil stehen: "
            "gib sie als '- Kategorie: Info' zurueck (eine Zeile pro Info)\n"
            "- Wenn die Nachricht eine KORREKTUR zu bestehenden Infos enthaelt: "
            "gib sie als '- KORREKTUR Kategorie: Neuer Wert' zurueck\n"
            "- Wenn KEINE persoenlichen Infos in der Nachricht sind: antworte NUR mit 'KEINE'\n"
            "- Schreibe NUR die Stichpunkte, KEINEN anderen Text\n"
            "- Kategorien: Name, Wohnort, PLZ, Familie, Beruf, Alter, Geburtstag, "
            "Haustiere, Interessen, Notiz"
        )},
        {"role": "user", "content": f"Nachricht: \"{user_msg}\""}
    ]

    try:
        # Groq Llama fuer schnelle, guenstige Extraktion
        raw_result, err = await call_llm("groq-llama", extract_prompt, 200)
        result = raw_result if raw_result else ""
        if not result or "KEINE" in result.upper():
            return

        # Ergebnis pruefen - muss Stichpunkte enthalten
        lines = [l.strip() for l in result.strip().split("\n") if l.strip().startswith("- ")]
        if not lines:
            return

        # Korrekturen behandeln
        corrections = [l for l in lines if "KORREKTUR" in l.upper()]
        additions = [l for l in lines if "KORREKTUR" not in l.upper()]

        if corrections:
            # Bei Korrekturen: USER.md komplett neu schreiben lassen
            await _apply_profile_corrections(current_profile, corrections, user_md_path)

        if additions:
            # Neue Infos anhaengen
            timestamp = datetime.now().strftime("%d.%m.%Y %H:%M")
            new_section = f"\n\n## Gelernt am {timestamp}\n" + "\n".join(additions)

            with open(user_md_path, "a") as f:
                f.write(new_section)

            log.info(f"USER.md via LLM aktualisiert: {', '.join(additions)}")

        # IMMER nach Aenderungen: komplette Datei in alle Workspaces sync
        if additions or corrections:
            full_content = read_file(user_md_path)
            await _sync_profile_to_agents(full_content)

        if corrections:
            log.info(f"USER.md Korrekturen angewendet: {', '.join(corrections)}")

    except Exception as e:
        log.warning(f"Profil-Extraktion fehlgeschlagen: {e}")


async def _apply_profile_corrections(current_profile, corrections, user_md_path):
    """Wendet Korrekturen auf das Profil an via LLM."""
    correction_text = "\n".join(corrections)
    rewrite_prompt = [
        {"role": "system", "content": (
            "Du bekommst ein User-Profil und Korrekturen. "
            "Schreibe das Profil NEU mit den Korrekturen eingearbeitet. "
            "Behalte das Markdown-Format bei. Aendere NUR was korrigiert werden muss. "
            "Gib NUR das aktualisierte Profil zurueck, keinen anderen Text."
        )},
        {"role": "user", "content": f"PROFIL:\n{current_profile}\n\nKORREKTUREN:\n{correction_text}"}
    ]
    try:
        raw_profile, err = await call_llm("groq-llama", rewrite_prompt, 1000)
        new_profile = raw_profile if raw_profile else ""
        if new_profile and len(new_profile) > 50:
            with open(user_md_path, "w", encoding="utf-8") as f:
                f.write(new_profile)
            await _sync_profile_to_agents(new_profile)
    except Exception as e:
        log.warning(f"Profil-Korrektur fehlgeschlagen: {e}")


async def _sync_profile_to_agents(content):
    """Kopiert Profil-Inhalt in alle Sub-Agent-Workspaces via Docker API.

    Da die Sub-Agent-Workspaces nicht im kimanus-app Container gemountet sind,
    nutzen wir die Docker Engine API ueber den Unix Socket um 'exec' in
    manus-admin auszufuehren und die Dateien dort zu schreiben.
    """
    connector = UnixConnector(path="/var/run/docker.sock")
    try:
        async with ClientSession(connector=connector) as session:
            for ws in ["workspace-kim", "workspace-kai"]:
                file_path = f"/home/node/.openclaw/{ws}/USER.md"
                # Shell-sicheres Escaping: base64 encode/decode
                encoded = base64.b64encode(content.encode("utf-8")).decode("ascii")
                cmd = f"echo '{encoded}' | base64 -d > {file_path}"
                # Exec erstellen
                resp = await session.post(
                    "http://localhost/containers/manus-admin/exec",
                    json={
                        "Cmd": ["sh", "-c", cmd],
                        "AttachStdin": False,
                        "AttachStdout": True,
                        "AttachStderr": True
                    }
                )
                if resp.status == 201:
                    exec_id = (await resp.json())["Id"]
                    # Exec starten
                    start_resp = await session.post(
                        f"http://localhost/exec/{exec_id}/start",
                        json={"Detach": False}
                    )
                    await start_resp.read()
                    log.info(f"Profil nach {ws} synchronisiert")
                else:
                    log.warning(f"Profil-Sync {ws}: HTTP {resp.status}")
    except Exception as e:
        log.warning(f"Profil-Sync via Docker API fehlgeschlagen: {e}")
    finally:
        await connector.close()


def save_chat(agent, user_msg, bot_msg, model_used):
    """Speichert Chat in Tageslog mit Modell-Info."""
    try:
        memdir = os.path.join(WORKSPACE, "memory")
        os.makedirs(memdir, exist_ok=True)
        logfile = os.path.join(memdir, datetime.now().strftime("%Y-%m-%d") + ".md")
        now = datetime.now().strftime("%H:%M")
        agent_name = "KAI" if agent == "kai" else "KIM"
        model_info = MODEL_CATALOG.get(model_used, {}).get("name", model_used)
        with open(logfile, "a") as f:
            f.write(f"\n### {now} KIMANUS-Chat ({agent_name} via {model_info})\n")
            f.write(f"**Wolfgang:** {user_msg}\n\n")
            f.write(f"**{agent_name}:** {bot_msg}\n")
    except Exception as e:
        log.warning(f"Chat-Log Fehler: {e}")


# === LLM CALLS ===

async def call_llm(model, messages, max_tokens):
    """Sendet Anfrage an LiteLLM Gateway (non-streaming)."""
    payload = {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
        "stream": False
    }

    async with ClientSession() as session:
        async with session.post(
            LITELLM_URL,
            json=payload,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {LITELLM_KEY}"
            },
            timeout=ClientTimeout(total=90)
        ) as resp:
            if resp.status == 200:
                result = await resp.json()
                return result["choices"][0]["message"]["content"], None
            else:
                error = await resp.text()
                return None, f"HTTP {resp.status}: {error[:200]}"


async def call_llm_stream(model, messages, max_tokens):
    """Streamt Tokens von LiteLLM als async Generator."""
    payload = {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
        "stream": True
    }

    async with ClientSession() as session:
        async with session.post(
            LITELLM_URL,
            json=payload,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {LITELLM_KEY}"
            },
            timeout=ClientTimeout(total=120)
        ) as resp:
            if resp.status != 200:
                error = await resp.text()
                raise Exception(f"LLM HTTP {resp.status}: {error[:200]}")
            async for raw_line in resp.content:
                line = raw_line.decode("utf-8").strip()
                if not line.startswith("data: "):
                    continue
                data_str = line[6:]
                if data_str == "[DONE]":
                    break
                try:
                    chunk = json.loads(data_str)
                    delta = chunk.get("choices", [{}])[0].get("delta", {})
                    token = delta.get("content", "")
                    if token:
                        yield token
                except json.JSONDecodeError:
                    continue


# === GROQ WHISPER STT ===

async def transcribe_audio(audio_bytes, content_type="audio/mp4"):
    """Sendet Audio an Groq Whisper, gibt transkribierten Text zurueck."""
    # Dateiendung aus Content-Type ableiten
    if "mp4" in content_type or "m4a" in content_type:
        ext = "mp4"
    elif "webm" in content_type:
        ext = "webm"
    elif "wav" in content_type:
        ext = "wav"
    elif "ogg" in content_type:
        ext = "ogg"
    else:
        ext = "mp4"  # iOS default

    form = FormData()
    form.add_field("file", audio_bytes, filename=f"audio.{ext}", content_type=content_type)
    form.add_field("model", GROQ_WHISPER_MODEL)
    form.add_field("language", "de")
    form.add_field("response_format", "json")

    async with ClientSession() as session:
        async with session.post(
            GROQ_API_URL,
            data=form,
            headers={"Authorization": f"Bearer {GROQ_API_KEY}"},
            timeout=ClientTimeout(total=30)
        ) as resp:
            if resp.status != 200:
                error = await resp.text()
                raise Exception(f"Whisper HTTP {resp.status}: {error[:200]}")
            result = await resp.json()
            return result.get("text", "").strip()


# === CHUNKED TTS ===

# Sprach-Charaktere fuer die TTS-Stimmen
TTS_INSTRUCTIONS = {
    "kai": (
        "Sprich muttersprachliches Hochdeutsch ohne jeden englischen Akzent. "
        "Natuerliches, zuegiges Sprechtempo wie ein deutscher Nachrichtensprecher im Gespraech. "
        "Professionell aber nahbar. Auf den Punkt, keine unnoetige Dramatik. "
        "Deutsche Aussprache fuer alle Woerter, auch Fachbegriffe."
    ),
    "kim": (
        "Sprich muttersprachliches Hochdeutsch ohne jeden englischen Akzent. "
        "Natuerliches, lebendiges Sprechtempo wie ein guter Freund am Telefon. "
        "Warmherzig, locker und entspannt. "
        "Deutsche Aussprache fuer alle Woerter, auch Fachbegriffe."
    )
}
TTS_INSTRUCTION_DEFAULT = TTS_INSTRUCTIONS["kai"]


async def tts_openai(text, voice_name="onyx", agent="kai", demo=False):
    """Generiert MP3 via OpenAI TTS API (ChatGPT-Qualitaet)."""
    if not OPENAI_API_KEY:
        return None
    instructions = TTS_INSTRUCTIONS.get(agent, TTS_INSTRUCTION_DEFAULT)
    # Demo-Modus: langsameres, natuerlicheres Tempo
    speed = 1.05 if demo else 1.2
    # tts-1-hd kennt nur 9 Original-Stimmen, gpt-4o-mini-tts hat alle 13
    LEGACY_VOICES = {"alloy", "ash", "coral", "echo", "fable", "nova", "onyx", "sage", "shimmer"}
    if demo and voice_name in LEGACY_VOICES:
        model = "tts-1-hd"  # HD fuer Demo mit klassischen Stimmen
    else:
        model = OPENAI_TTS_MODEL  # gpt-4o-mini-tts fuer alle Stimmen
    try:
        async with ClientSession() as session:
            async with session.post(
                OPENAI_TTS_URL,
                headers={
                    "Authorization": f"Bearer {OPENAI_API_KEY}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": model,
                    "input": text,
                    "voice": voice_name,
                    "instructions": instructions,
                    "response_format": "mp3",
                    "speed": speed
                },
                timeout=ClientTimeout(total=15)
            ) as resp:
                if resp.status == 200:
                    data = await resp.read()
                    return data if len(data) > 100 else None
                else:
                    error_text = await resp.text()
                    log.warning(f"OpenAI TTS Fehler {resp.status}: {error_text[:200]}")
                    return None
    except Exception as e:
        log.warning(f"OpenAI TTS Fehler: {e}")
        return None


async def tts_edge(text, voice):
    """Generiert MP3 via Edge TTS (Gratis-Fallback)."""
    try:
        communicate = edge_tts.Communicate(text, voice)
        audio_data = io.BytesIO()
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_data.write(chunk["data"])
        audio_data.seek(0)
        data = audio_data.read()
        return data if len(data) > 100 else None
    except Exception as e:
        log.warning(f"Edge TTS Fehler: {e}")
        return None


async def tts_chunk(text, voice, agent="kai", demo=False):
    """Generiert MP3 - OpenAI TTS wenn verfuegbar, sonst Edge TTS."""
    # Markdown/Sonderzeichen entfernen
    clean = re.sub(r'[*_#`~\[\]()>|]', '', text)
    clean = re.sub(r'https?://\S+', 'Link', clean)
    clean = clean.strip()
    if not clean or len(clean) < 2:
        return None

    # OpenAI TTS (Premium)
    if TTS_ENGINE == "openai" and OPENAI_API_KEY:
        openai_voice = OPENAI_VOICES.get(agent, OPENAI_VOICE_DEFAULT)
        result = await tts_openai(clean, openai_voice, agent, demo)
        if result:
            return result
        log.warning("OpenAI TTS fehlgeschlagen, Fallback auf Edge TTS")

    # Edge TTS (Fallback)
    return await tts_edge(clean, voice)


def split_into_sentences(text):
    """Teilt Text an Satzgrenzen."""
    parts = SENTENCE_SPLIT.split(text)
    return [p.strip() for p in parts if p.strip()]


# === VOICE PIPELINE ENDPOINT ===

async def handle_voice(request):
    """POST /api/voice - Komplette Voice-Pipeline als SSE Stream.

    Empfaengt Audio-Blob, gibt SSE-Events zurueck:
    - transcript: Erkannter Text vom User
    - text: Satz-Chunk der KI-Antwort
    - audio: Base64-MP3 des gesprochenen Satzes
    - done: Pipeline fertig
    - error: Fehler aufgetreten
    """
    try:
        reader = await request.multipart()
    except Exception as e:
        return web.json_response({"error": f"Multipart-Fehler: {e}"}, status=400)

    # Felder lesen (Audio + optional Chat-History)
    audio_bytes = None
    content_type = "audio/mp4"
    chat_history_json = ""
    while True:
        field = await reader.next()
        if field is None:
            break
        if field.name == "audio":
            audio_bytes = await field.read()
            content_type = field.headers.get("Content-Type", "audio/mp4")
            if hasattr(field, 'content_type') and field.content_type:
                content_type = field.content_type
        elif field.name == "chat_history":
            chat_history_json = (await field.read()).decode("utf-8", errors="replace")

    if not audio_bytes or len(audio_bytes) < 500:
        return web.json_response({"error": "Kein Audio empfangen"}, status=400)

    agent = request.query.get("agent", "kai")
    model_req = request.query.get("model", "auto")
    session_id = request.query.get("session", "default")
    voice_override = request.query.get("voice", "")  # Optionale Stimmen-Wahl
    demo_mode = request.query.get("demo", "") == "1"

    log.info(f"Voice [{agent.upper()}]: {len(audio_bytes)} bytes Audio empfangen")

    # SSE Response starten
    response = web.StreamResponse(
        status=200,
        headers={
            "Content-Type": "text/event-stream",
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
            "Access-Control-Allow-Origin": "*",
        }
    )
    await response.prepare(request)

    async def send_sse(event, data):
        payload = f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"
        await response.write(payload.encode("utf-8"))

    try:
        # === SCHRITT 1: Audio transkribieren (Groq Whisper) ===
        log.info("Voice: Starte Transkription...")
        transcript = await transcribe_audio(audio_bytes, content_type)

        if not transcript:
            await send_sse("error", {"message": "Kein Text erkannt. Bitte sprich deutlicher."})
            return response

        log.info(f"Voice: Transkript = '{transcript[:80]}'")
        await send_sse("transcript", {"text": transcript})
        # KIM lernt auch per Voice: Persoenliche Infos speichern
        await extract_and_save_user_info(transcript)

        # === SCHRITT 2: Modell waehlen (Voice = Groq bevorzugt fuer Speed) ===
        if model_req == "auto":
            if demo_mode:
                # Demo: Premium-Modell fuer beste Qualitaet
                model = "or-claude-sonnet"
                auto_reason = "Demo -> Claude Sonnet (Premium)"
            else:
                # Voice braucht SPEED - Groq hat die beste First-Token-Latency
                model = "groq-llama"
                auto_reason = "Voice -> Groq (schnellste Antwort)"
            log.info(f"Voice Auto-Route: {auto_reason}")
        else:
            model = model_req

        # Session History + Chat-Kontext aus Messenger
        if session_id not in sessions:
            sessions[session_id] = []
        history = sessions[session_id]
        # Chat-History vom Frontend einfuegen (damit Voice den Text-Chat kennt)
        if chat_history_json and not history:
            try:
                chat_msgs = json.loads(chat_history_json)
                for cm in chat_msgs[-8:]:  # Letzte 8 Nachrichten als Kontext
                    role = cm.get("role", "user")
                    if role not in ("user", "assistant"):
                        role = "assistant"
                    history.append({"role": role, "content": cm.get("content", "")})
                log.info(f"Voice: {len(history)} Chat-Nachrichten als Kontext geladen")
            except Exception as e:
                log.warning(f"Voice: Chat-History parse error: {e}")
        history.append({"role": "user", "content": transcript})

        # System Prompt fuer Voice (gleiche Persoenlichkeit wie Chat!)
        base_prompt = SYSTEM_PROMPTS.get(agent, SYSTEM_PROMPTS["kai"])
        voice_instruction = (
            "\n\nDu bist jetzt am TELEFON. Wichtige Regeln:"
            "\n- Sprich natuerlich und warmherzig, wie in einem echten Gespraech"
            "\n- Halte Antworten kurz (1-3 Saetze), aber freundlich"
            "\n- Kein Markdown, keine Sonderzeichen, keine Listen"
            "\n- Sei genauso persoenlich und vertraut wie im Chat"
            "\n- Antworte so, wie du einem guten Freund am Telefon antworten wuerdest"
        )
        # Datum/Uhrzeit + Wetter immer mitgeben
        datetime_info = get_datetime_info()
        weather_info = await get_weather()
        live_info = f"\n\n{datetime_info}"
        if weather_info:
            live_info += f"\n{weather_info}"
        system_prompt = base_prompt + voice_instruction + live_info
        # Voice: User-Profil laden (wichtig fuer persoenliche Antworten)
        user_content = read_file(os.path.join(WORKSPACE, "USER.md"))
        if user_content.strip():
            system_prompt += "\n\n" + user_content[:800]
        # Memory-Kurzkontext
        mem_content = read_file(os.path.join(WORKSPACE, "MEMORY.md"))
        if mem_content.strip():
            system_prompt += "\n\nKontext:\n" + mem_content[:500]

        messages = [{"role": "system", "content": system_prompt}] + history[-10:]

        # === SCHRITT 3: LLM streamen + Satzweise TTS ===
        # Stimme: Explizite Wahl > OpenAI Default > Edge Fallback
        if voice_override and (voice_override in AVAILABLE_VOICES or voice_override in OPENAI_VOICE_CATALOG):
            voice = voice_override
            if voice_override in OPENAI_VOICE_CATALOG:
                OPENAI_VOICES[agent] = voice_override
        elif TTS_ENGINE == "openai":
            # OpenAI-Stimmen klingen viel natuerlicher - immer bevorzugen
            voice = OPENAI_VOICES.get(agent, OPENAI_VOICE_DEFAULT)
        else:
            voice = TTS_VOICES.get(agent, TTS_DEFAULT_VOICE)
        model_name = MODEL_CATALOG.get(model, {}).get("name", model)
        log.info(f"Voice: Starte LLM-Stream ({model_name})...")

        full_text = ""
        sentence_buffer = ""
        chunk_index = 0

        async for token in call_llm_stream(model, messages, MAX_TOKENS):
            full_text += token
            sentence_buffer += token

            # Pruefen ob vollstaendige Saetze im Buffer sind
            sentences = split_into_sentences(sentence_buffer)
            if len(sentences) > 1:
                # Alle ausser dem letzten sind fertige Saetze
                for s in sentences[:-1]:
                    if len(s) < 3:
                        continue
                    await send_sse("text", {"text": s, "full": full_text})

                    # TTS fuer diesen Satz generieren
                    audio = await tts_chunk(s, voice, agent, demo_mode)
                    if audio:
                        b64 = base64.b64encode(audio).decode("ascii")
                        await send_sse("audio", {"audio": b64, "index": chunk_index})
                        chunk_index += 1
                        log.info(f"Voice: Chunk {chunk_index} gesendet ({len(audio)} bytes)")

                sentence_buffer = sentences[-1]

        # Restlichen Buffer aussprechen
        remaining = sentence_buffer.strip()
        if remaining and len(remaining) >= 3:
            await send_sse("text", {"text": remaining, "full": full_text})
            audio = await tts_chunk(remaining, voice, agent, demo_mode)
            if audio:
                b64 = base64.b64encode(audio).decode("ascii")
                await send_sse("audio", {"audio": b64, "index": chunk_index})
                chunk_index += 1

        # History updaten
        history.append({"role": "assistant", "content": full_text})
        if len(history) > 40:
            sessions[session_id] = history[-20:]

        # Chat speichern
        save_chat(agent, transcript, full_text, model)

        await send_sse("done", {
            "full_text": full_text,
            "model": model,
            "model_name": model_name,
            "chunks": chunk_index
        })

        log.info(f"Voice: Fertig - {len(full_text)} Zeichen, {chunk_index} Audio-Chunks via {model_name}")

    except Exception as e:
        log.error(f"Voice Pipeline Fehler: {e}", exc_info=True)
        try:
            await send_sse("error", {"message": str(e)})
        except:
            pass

    return response


# === BESTEHENDE ENDPOINTS ===

async def handle_chat(request):
    """POST /api/chat - Hauptchat-Endpoint mit Auto-Routing."""
    try:
        data = await request.json()
    except:
        return web.json_response({"error": "Invalid JSON"}, status=400)

    message = data.get("message", "").strip()
    agent = data.get("agent", "kai")
    requested_model = data.get("model", "auto")
    session_id = data.get("session", "default")
    demo_mode = data.get("demo", False)

    if not message:
        return web.json_response({"error": "Keine Nachricht"}, status=400)

    auto_reason = None
    if requested_model == "auto":
        if demo_mode:
            model = "or-claude-sonnet"
            auto_reason = "Demo -> Claude Sonnet (Premium)"
        else:
            model, auto_reason = auto_select_model(message, agent)
        log.info(f"Auto-Route: {auto_reason}")
    else:
        model = requested_model

    model_name = MODEL_CATALOG.get(model, {}).get("name", model)
    log.info(f"Chat [{agent.upper()}] ({model_name}): {message[:80]}")

    if session_id not in sessions:
        sessions[session_id] = []
    history = sessions[session_id]
    history.append({"role": "user", "content": message})

    base_prompt = SYSTEM_PROMPTS.get(agent, SYSTEM_PROMPTS["kai"])
    # Datum/Uhrzeit + Wetter
    datetime_info = get_datetime_info()
    weather_info = await get_weather()
    live_info = f"\n\n{datetime_info}"
    if weather_info:
        live_info += f"\n{weather_info}"
    context = build_context()
    if context:
        system_prompt = base_prompt + live_info + "\n\nHier ist der aktuelle Kontext und das Gedaechtnis:\n\n" + context
    else:
        system_prompt = base_prompt + live_info

    messages = [{"role": "system", "content": system_prompt}] + history[-20:]

    try:
        answer, error = await call_llm(model, messages, MAX_TOKENS)

        if error and model != "deepseek":
            log.warning(f"{model_name} fehlgeschlagen ({error}), Fallback auf DeepSeek...")
            model = "deepseek"
            model_name = "DeepSeek V3 (Fallback)"
            answer, error = await call_llm(model, messages, MAX_TOKENS)

        if error:
            log.error(f"LLM Fehler: {error}")
            return web.json_response(
                {"output": f"KI-Server Fehler. Bitte versuche es nochmal.", "agent": agent, "model": model},
                status=502
            )

        history.append({"role": "assistant", "content": answer})
        if len(history) > 40:
            sessions[session_id] = history[-20:]

        save_chat(agent, message, answer, model)
        # KIM lernt: Persoenliche Infos aus der Nachricht extrahieren und speichern
        await extract_and_save_user_info(message)
        log.info(f"Antwort via {model_name}: {len(answer)} Zeichen")

        response_data = {
            "output": answer,
            "agent": agent,
            "model": model,
            "model_name": model_name,
        }
        if auto_reason:
            response_data["auto_reason"] = auto_reason

        return web.json_response(response_data)

    except asyncio.TimeoutError:
        log.error(f"Timeout bei {model_name}")
        return web.json_response(
            {"output": "Die Anfrage hat zu lange gedauert. Bitte versuche es nochmal."},
            status=504
        )
    except Exception as e:
        log.error(f"Verbindungsfehler: {e}")
        return web.json_response(
            {"output": f"Verbindungsfehler: {e}"},
            status=503
        )


async def handle_tts(request):
    """POST /api/tts - Text-to-Speech (OpenAI Premium oder Edge Fallback)."""
    try:
        data = await request.json()
    except:
        return web.json_response({"error": "Invalid JSON"}, status=400)

    text = data.get("text", "").strip()
    agent = data.get("agent", "kai")
    voice = data.get("voice", TTS_VOICES.get(agent, TTS_DEFAULT_VOICE))

    if not text:
        return web.json_response({"error": "Kein Text"}, status=400)

    clean = re.sub(r'[*_#`~\[\]()>|]', '', text)
    clean = re.sub(r'https?://\S+', 'Link', clean)
    clean = re.sub(r'\n{2,}', '. ', clean)
    clean = re.sub(r'\n', ' ', clean)
    clean = clean.strip()

    if not clean:
        return web.json_response({"error": "Kein sprechbarer Text"}, status=400)

    if len(clean) > 5000:
        clean = clean[:5000] + "... Der Text wurde gekuerzt."

    engine_used = TTS_ENGINE
    log.info(f"TTS [{agent}] (engine={engine_used}): {len(clean)} Zeichen")

    try:
        audio = await tts_chunk(clean, voice, agent)
        if audio:
            return web.Response(
                body=audio,
                content_type="audio/mpeg",
                headers={"Cache-Control": "no-cache"}
            )
        return web.json_response({"error": "TTS konnte kein Audio generieren"}, status=500)
    except Exception as e:
        log.error(f"TTS Fehler: {e}")
        return web.json_response({"error": f"TTS Fehler: {str(e)}"}, status=500)


async def handle_models(request):
    """GET /api/models - Liste verfuegbarer Modelle."""
    models = [{"id": k, **v} for k, v in MODEL_CATALOG.items()]
    return web.json_response({"models": models})


async def handle_voices(request):
    """GET /api/voices - Liste verfuegbarer TTS-Stimmen."""
    edge_voices = [{"id": k, "engine": "edge", **v} for k, v in AVAILABLE_VOICES.items()]
    openai_voices = [{"id": k, "engine": "openai", **v} for k, v in OPENAI_VOICE_CATALOG.items()]
    return web.json_response({
        "voices": openai_voices + edge_voices,
        "openai_voices": openai_voices,
        "edge_voices": edge_voices,
        "defaults": OPENAI_VOICES if TTS_ENGINE == "openai" else TTS_VOICES,
        "engine": TTS_ENGINE
    })


async def handle_health(request):
    """GET /api/health - Server Status."""
    return web.json_response({
        "status": "ok",
        "server": "KIMANUS OS Backend v2 (Voice Pipeline)",
        "timestamp": datetime.now().isoformat(),
        "litellm": LITELLM_URL,
        "models": list(MODEL_CATALOG.keys()),
        "features": ["chat", "voice", "tts", "auto-routing"]
    })


async def handle_index(request):
    """GET / - Serve index.html mit no-cache Headers."""
    resp = web.FileResponse(os.path.join(STATIC_DIR, "index.html"))
    resp.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    resp.headers["Pragma"] = "no-cache"
    resp.headers["Expires"] = "0"
    return resp


# =========================================
# VIDEO ANALYZER PROXY
# =========================================
VIDEO_ANALYZER_URL = "http://video-analyzer:3001"

async def handle_video_analyze(request):
    """POST /api/video-analyze - Proxy to Video Analyzer Agent."""
    try:
        body = await request.json()
    except Exception:
        return web.json_response({"error": "Ungueltiger JSON-Body"}, status=400)

    log.info(f"Video Analyze Proxy: {body.get('url', '?')}")
    async with ClientSession() as session:
        async with session.post(
            f"{VIDEO_ANALYZER_URL}/analyze",
            json={"url": body.get("url", ""), "frames": body.get("frames", False)},
            timeout=ClientTimeout(total=300)  # Gemini braucht bis 3min fuer Video-Analyse
        ) as resp:
            data = await resp.json()
            return web.json_response(data, status=resp.status)


async def handle_video_chat(request):
    """POST /api/video-chat - Proxy to Video Analyzer Chat."""
    try:
        body = await request.json()
    except Exception:
        return web.json_response({"error": "Ungueltiger JSON-Body"}, status=400)

    async with ClientSession() as session:
        async with session.post(
            f"{VIDEO_ANALYZER_URL}/chat",
            json={"url": body.get("url", ""), "question": body.get("question", "")},
            timeout=ClientTimeout(total=300)
        ) as resp:
            data = await resp.json()
            return web.json_response(data, status=resp.status)


SEARXNG_URL = "http://searxng:8080"

async def handle_video_search(request):
    """GET /api/video-search?q=... - YouTube-Suche via SearXNG."""
    query = request.query.get("q", "").strip()
    if not query:
        return web.json_response({"error": "Kein Suchbegriff"}, status=400)

    log.info(f"Video Search: {query}")
    try:
        import urllib.parse
        search_url = f"{SEARXNG_URL}/search?q={urllib.parse.quote(query)}&format=json&engines=youtube&categories=videos"
        import urllib.request
        req = urllib.request.Request(search_url, headers={"Accept": "application/json"})
        def _fetch():
            resp = urllib.request.urlopen(req, timeout=15)
            return json.loads(resp.read())
        import asyncio
        data = await asyncio.to_thread(_fetch)
        results = []
        for r in data.get("results", [])[:8]:
            results.append({
                "title": r.get("title", ""),
                "url": r.get("url", ""),
                "thumbnail": r.get("thumbnail", ""),
                "length": r.get("length", ""),
                "channel": r.get("author", ""),
                "iframe_src": r.get("iframe_src", ""),
            })
        return web.json_response({"query": query, "results": results})
    except Exception as e:
        log.error(f"Video search error: {e}")
        return web.json_response({"error": str(e)}, status=500)


# =========================================
# OPENAI REALTIME API (WebRTC Voice)
# =========================================

async def handle_profile(request):
    """POST /api/profile - Speichert User-Profil als USER.md im Workspace."""
    try:
        data = await request.json()
    except:
        return web.json_response({"error": "Invalid JSON"}, status=400)

    name = data.get("name", "").strip()
    job = data.get("job", "").strip()
    interests = data.get("interests", [])
    tone = data.get("tone", "locker")

    # USER.md generieren
    lines = ["# User-Profil", ""]
    if name:
        lines.append(f"- Name: {name}")
    if job:
        lines.append(f"- Beruf: {job}")
    if interests:
        lines.append(f"- Interessen: {', '.join(interests)}")
    lines.append(f"- Anrede: {'Du (locker)' if tone == 'locker' else 'Sie (formell)'}")
    lines.append("")
    lines.append("## Kommunikations-Regeln")
    if name:
        lines.append(f"- Nutzer heisst {name}")
        lines.append(f"- NIEMALS mit '{name}' ansprechen! Einfach direkt antworten.")
    else:
        lines.append("- Nutzer direkt ansprechen, ohne Namen")
    if tone == "locker":
        lines.append("- Locker und freundlich, per Du")
        lines.append("- Wie ein guter Freund reden")
    else:
        lines.append("- Formell und hoeflich, per Sie")
        lines.append("- Professionell aber warmherzig")
    if interests:
        lines.append(f"\n## Interessen\n{', '.join(interests)}")

    user_md = "\n".join(lines) + "\n"

    # Auf Disk speichern + in alle Workspaces kopieren
    user_path = os.path.join(WORKSPACE, "USER.md")
    try:
        with open(user_path, "w", encoding="utf-8") as f:
            f.write(user_md)
        # In Sub-Agent-Workspaces kopieren (via Docker API)
        await _sync_profile_to_agents(user_md)
        log.info(f"User-Profil gespeichert: {name or 'Anonym'}, {job or '-'}, {len(interests)} Interessen")
        return web.json_response({"ok": True, "message": "Profil gespeichert"})
    except Exception as e:
        log.error(f"Profil speichern fehlgeschlagen: {e}")
        return web.json_response({"error": str(e)}, status=500)


async def handle_profile_get(request):
    """GET /api/profile - Gibt das aktuelle User-Profil zurueck (fuer Handy-Backup)."""
    user_path = os.path.join(WORKSPACE, "USER.md")
    content = read_file(user_path)
    import hashlib
    content_hash = hashlib.md5(content.encode()).hexdigest() if content else ""
    return web.json_response({
        "profile": content,
        "hash": content_hash,
        "timestamp": os.path.getmtime(user_path) if os.path.exists(user_path) else 0
    })


async def handle_profile_sync(request):
    """POST /api/profile/sync - Handy schickt sein lokales Backup zurueck zum Server.

    Wird genutzt wenn: Server-Profil leer/kuerzer als Handy-Profil.
    """
    try:
        data = await request.json()
    except:
        return web.json_response({"error": "Invalid JSON"}, status=400)

    phone_profile = data.get("profile", "").strip()
    phone_hash = data.get("hash", "")

    if not phone_profile:
        return web.json_response({"ok": False, "message": "Kein Profil zum Sync"})

    # Server-Profil laden und vergleichen
    user_path = os.path.join(WORKSPACE, "USER.md")
    server_profile = read_file(user_path)

    # Nur ueberschreiben wenn Handy-Profil mehr Infos hat
    if len(phone_profile) > len(server_profile):
        with open(user_path, "w", encoding="utf-8") as f:
            f.write(phone_profile)
        # In Sub-Agent-Workspaces kopieren (via Docker API)
        await _sync_profile_to_agents(phone_profile)
        log.info(f"Profil vom Handy synchronisiert ({len(phone_profile)} chars)")
        return web.json_response({"ok": True, "message": "Profil vom Handy wiederhergestellt", "action": "restored"})
    else:
        return web.json_response({"ok": True, "message": "Server-Profil ist aktuell", "action": "unchanged"})


async def handle_manus_chat(request):
    """POST /api/manus - Sendet eine Nachricht an einen OpenClaw Agent via Docker API.
    Unterstuetzte Agents: main (Manus), kim, kai
    """
    try:
        data = await request.json()
    except:
        return web.json_response({"error": "Invalid JSON"}, status=400)

    message = data.get("message", "").strip()
    session_id = data.get("session_id", "")
    agent_id = data.get("agent", "main")  # Default: Manus (main)
    # Nur erlaubte Agents
    if agent_id not in ("main", "kim", "kai"):
        agent_id = "main"
    if not message:
        return web.json_response({"error": "Keine Nachricht"}, status=400)

    try:
        log.info(f"Agent [{agent_id}] Anfrage: {message[:80]}...")

        # Docker API via Unix Socket: exec create + start
        import aiohttp
        cmd_parts = ["openclaw", "agent", "--agent", agent_id,
                     "--message", message, "--json", "--timeout", "120"]
        if session_id:
            cmd_parts.extend(["--session-id", session_id])

        connector = UnixConnector(path="/var/run/docker.sock")
        async with ClientSession(connector=connector) as docker:
            # Exec erstellen
            exec_create = await docker.post(
                "http://localhost/containers/manus-admin/exec",
                json={"Cmd": cmd_parts, "AttachStdout": True, "AttachStderr": True}
            )
            if exec_create.status != 201:
                err = await exec_create.text()
                log.error(f"Docker exec create failed: {err}")
                return web.json_response({"error": "Docker exec fehlgeschlagen"}, status=502)

            exec_id = (await exec_create.json())["Id"]

            # Exec starten und Output lesen
            exec_start = await docker.post(
                f"http://localhost/exec/{exec_id}/start",
                json={"Detach": False, "Tty": False},
                timeout=ClientTimeout(total=135)
            )
            raw_output = await exec_start.read()

            # Docker stream protocol: 8-byte header pro Frame entfernen
            stdout_data = b""
            stderr_data = b""
            pos = 0
            while pos + 8 <= len(raw_output):
                stream_type = raw_output[pos]
                frame_size = int.from_bytes(raw_output[pos+4:pos+8], 'big')
                if pos + 8 + frame_size > len(raw_output):
                    break
                frame = raw_output[pos+8:pos+8+frame_size]
                if stream_type == 1:
                    stdout_data += frame
                elif stream_type == 2:
                    stderr_data += frame
                pos += 8 + frame_size

            # Exec-Status pruefen
            exec_inspect = await docker.get(f"http://localhost/exec/{exec_id}/json")
            exec_info = await exec_inspect.json()
            exit_code = exec_info.get("ExitCode", -1)

        output = stdout_data.decode("utf-8", errors="replace").strip()

        if exit_code != 0:
            err = stderr_data.decode("utf-8", errors="replace").strip()
            log.error(f"Manus exit {exit_code}: {err}")
            return web.json_response({"error": "Manus nicht erreichbar", "details": err}, status=502)

        result = json.loads(output)
        payloads = result.get("result", {}).get("payloads", [])
        reply_text = "\n\n".join(p.get("text", "") for p in payloads if p.get("text"))
        sid = result.get("result", {}).get("meta", {}).get("agentMeta", {}).get("sessionId", "")

        log.info(f"Manus-Antwort: {reply_text[:80]}...")
        return web.json_response({
            "reply": reply_text or "Manus hat nicht geantwortet.",
            "session_id": sid,
            "model": result.get("result", {}).get("meta", {}).get("agentMeta", {}).get("model", ""),
        })

    except asyncio.TimeoutError:
        log.error("Manus-Timeout nach 135s")
        return web.json_response({"error": "Manus-Timeout - Anfrage dauert zu lange"}, status=504)
    except Exception as e:
        log.error(f"Manus-Fehler: {e}")
        return web.json_response({"error": str(e)}, status=500)


async def handle_video_save(request):
    """POST /api/video-save - Speichert eine Video-Analyse als Markdown im Workspace."""
    try:
        data = await request.json()
    except:
        return web.json_response({"error": "Invalid JSON"}, status=400)

    title = data.get("title", "Unbekannt").strip()
    channel = data.get("channel", "").strip()
    duration = data.get("duration", "").strip()
    url = data.get("url", "").strip()
    analysis = data.get("analysis", "").strip()
    date_str = data.get("date", datetime.now(timezone.utc).isoformat())

    if not analysis:
        return web.json_response({"error": "Keine Analyse vorhanden"}, status=400)

    # Verzeichnis erstellen
    save_dir = os.path.join(WORKSPACE, "video-analysen")
    os.makedirs(save_dir, exist_ok=True)

    # Dateiname aus Titel + Datum
    safe_title = re.sub(r'[^\w\s-]', '', title)[:60].strip().replace(' ', '_')
    date_short = datetime.fromisoformat(date_str.replace('Z', '+00:00')).strftime('%Y-%m-%d_%H%M')
    filename = f"{date_short}_{safe_title}.md"
    filepath = os.path.join(save_dir, filename)

    # Markdown erstellen
    md = f"# {title}\n\n"
    md += f"- **Kanal:** {channel}\n" if channel else ""
    md += f"- **Dauer:** {duration}\n" if duration else ""
    md += f"- **URL:** {url}\n" if url else ""
    md += f"- **Analysiert:** {date_short.replace('_', ' ')}\n"
    md += f"\n---\n\n## Analyse\n\n{analysis}\n"

    try:
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(md)
        log.info(f"Video-Analyse gespeichert: {filename}")
        return web.json_response({"ok": True, "filename": filename})
    except Exception as e:
        log.error(f"Video-Analyse speichern fehlgeschlagen: {e}")
        return web.json_response({"error": str(e)}, status=500)


async def handle_realtime_session(request):
    """POST /api/realtime/session - Erstellt einen ephemeral Token fuer WebRTC.

    Der Client nutzt diesen Token um eine direkte WebRTC-Verbindung
    zu OpenAI aufzubauen. Audio streamt dann direkt Client <-> OpenAI.
    """
    if not OPENAI_API_KEY:
        return web.json_response({"error": "OpenAI API Key nicht konfiguriert"}, status=500)

    try:
        data = await request.json()
    except:
        data = {}

    agent = data.get("agent", "kai")
    demo = data.get("demo", False)
    chat_context = data.get("chat_context", "")  # Letzter Chat-Verlauf

    # User-Profil laden
    user_content = read_file(os.path.join(WORKSPACE, "USER.md"))
    user_context = user_content[:600] if user_content.strip() else ""

    # Memory laden
    mem_content = read_file(os.path.join(WORKSPACE, "MEMORY.md"))
    mem_context = mem_content[:400] if mem_content.strip() else ""

    # Datum/Uhrzeit
    datetime_info = get_datetime_info()

    # Wetter async holen
    weather_info = await get_weather()
    live_info = datetime_info
    if weather_info:
        live_info += f"\n{weather_info}"

    # Chat-Kontext aufbereiten (letzte Nachrichten aus dem Messenger)
    chat_ctx_str = ""
    if chat_context:
        chat_ctx_str = f"\n\nVorheriges Gespraech (der Nutzer wechselt jetzt zum Telefonieren):\n{chat_context[:800]}"
        log.info(f"Realtime: Chat-Kontext geladen ({len(chat_context)} chars)")

    # System-Prompt fuer Realtime zusammenbauen
    base = SYSTEM_PROMPTS.get(agent, SYSTEM_PROMPTS["kai"])
    instructions = (
        f"{base}\n\n"
        f"Aktuelle Infos:\n{live_info}\n\n"
        f"{user_context}\n\n"
        f"Kontext:\n{mem_context}"
        f"{chat_ctx_str}"
    )

    # Stimme waehlen (Realtime API hat eigene Stimmen-Liste)
    REALTIME_VOICES = {"kai": "ash", "kim": "coral"}  # ash=warm maennlich, coral=warm weiblich
    voice = REALTIME_VOICES.get(agent, "ash")

    # Ephemeral Session bei OpenAI erstellen
    async with ClientSession() as session:
        async with session.post(
            "https://api.openai.com/v1/realtime/sessions",
            headers={
                "Authorization": f"Bearer {OPENAI_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": "gpt-4o-realtime-preview",
                "voice": voice,
                "instructions": instructions,
                "input_audio_transcription": {
                    "model": "whisper-1"
                },
                "turn_detection": {
                    "type": "server_vad",
                    "threshold": 0.5,
                    "prefix_padding_ms": 300,
                    "silence_duration_ms": 500
                }
            },
            timeout=ClientTimeout(total=10)
        ) as resp:
            if resp.status != 200:
                error = await resp.text()
                log.error(f"Realtime Session Fehler: {resp.status} - {error[:300]}")
                return web.json_response({"error": f"OpenAI Realtime: {error[:200]}"}, status=resp.status)

            result = await resp.json()
            log.info(f"Realtime Session erstellt fuer {agent.upper()}, Voice: {voice}")
            return web.json_response({
                "token": result.get("client_secret", {}).get("value", ""),
                "voice": voice,
                "agent": agent,
                "model": "gpt-4o-realtime-preview",
                "expires_at": result.get("client_secret", {}).get("expires_at", 0)
            })


def create_app():
    app = web.Application(client_max_size=10 * 1024 * 1024)  # 10MB fuer Audio-Uploads
    app.router.add_post("/api/chat", handle_chat)
    app.router.add_post("/api/voice", handle_voice)
    app.router.add_post("/api/tts", handle_tts)
    app.router.add_get("/api/health", handle_health)
    app.router.add_get("/api/models", handle_models)
    app.router.add_get("/api/voices", handle_voices)
    app.router.add_post("/api/profile", handle_profile)
    app.router.add_get("/api/profile", handle_profile_get)
    app.router.add_post("/api/profile/sync", handle_profile_sync)
    app.router.add_post("/api/manus", handle_manus_chat)
    app.router.add_post("/api/video-save", handle_video_save)
    app.router.add_post("/api/realtime/session", handle_realtime_session)
    app.router.add_post("/api/video-analyze", handle_video_analyze)
    app.router.add_post("/api/video-chat", handle_video_chat)
    app.router.add_get("/api/video-search", handle_video_search)
    app.router.add_get("/", handle_index)
    app.router.add_static("/", STATIC_DIR)
    return app


if __name__ == "__main__":
    log.info("=== KIMANUS OS Backend v2 startet ===")
    log.info(f"LiteLLM: {LITELLM_URL}")
    log.info(f"Static: {STATIC_DIR}")
    log.info(f"Workspace: {WORKSPACE}")
    log.info(f"Modelle: {list(MODEL_CATALOG.keys())}")
    log.info(f"Groq Whisper: {GROQ_WHISPER_MODEL}")
    log.info(f"TTS Engine: {TTS_ENGINE} ({'OpenAI ' + OPENAI_TTS_MODEL if TTS_ENGINE == 'openai' else 'Edge TTS (gratis)'})")
    log.info(f"Features: Chat, Voice Pipeline, TTS, Auto-Routing")
    app = create_app()
    web.run_app(app, host="0.0.0.0", port=3000)
