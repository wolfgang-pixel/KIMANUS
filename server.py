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
# Matrix-Bruecke fuer KIMANUS (via Hermes)
from _matrix_bridge import call_kimanus_via_matrix
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

# Grok TTS (xAI - 70x guenstiger als ElevenLabs, 5 Stimmen)
XAI_API_KEY = os.environ.get("XAI_API_KEY", "")
XAI_TTS_URL = "https://api.x.ai/v1/tts"

# Grok TTS Stimmen - perfekt fuer KIMANUS
GROK_VOICE_CATALOG = {
    "ara": {"name": "Ara", "gender": "f", "style": "Warm, freundlich - KIM"},
    "rex": {"name": "Rex", "gender": "m", "style": "Selbstbewusst, klar - KAI"},
    "leo": {"name": "Leo", "gender": "m", "style": "Autoritaer, stark - MANUS"},
    "eve": {"name": "Eve", "gender": "f", "style": "Energetisch, lebhaft"},
    "sal": {"name": "Sal", "gender": "m", "style": "Ruhig, ausgewogen - Podcasts"},
}

# Grok Stimmen pro Agent
GROK_VOICES = {
    "kim": "ara",      # Warm, freundlich - perfekt fuer KIM
    "kai": "rex",      # Selbstbewusst, klar - perfekt fuer KAI
    "manus": "leo",    # Autoritaer, stark - perfekt fuer MANUS
}
GROK_VOICE_DEFAULT = "ara"

# ElevenLabs TTS (Premium - beste Sprachqualitaet)
ELEVENLABS_API_KEY = os.environ.get("ELEVENLABS_API_KEY", "")
ELEVENLABS_TTS_URL = "https://api.elevenlabs.io/v1/text-to-speech"
ELEVENLABS_MODEL = "eleven_multilingual_v2"  # Beste Qualitaet fuer Deutsch

# ElevenLabs Stimmen pro Agent (deutsche Muttersprachler)
ELEVENLABS_VOICES = {
    "kim": "5Aahq892EEb6MdNwMM3p",     # Laura - Jung, warm, vielseitig (weiblich)
    "kai": "aduJlSmEKqbhRQAAMzV2",     # Adrian - Tief, ueberzeugend, vertrauenswuerdig (TV-Stimme)
    "manus": "VHYWoxffK1pFlM1dtRb0",   # Thomas - Literarisch, gebildet, warm (Bariton)
}

# OpenAI TTS (Fallback - natuerliche Stimme wie ChatGPT)
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
OPENAI_TTS_URL = "https://api.openai.com/v1/audio/speech"
OPENAI_TTS_MODEL = "gpt-4o-mini-tts-2025-12-15"  # Neuester Snapshot, 35% besseres Deutsch

# TTS Engine Prioritaet: grok > openai > edge
if XAI_API_KEY:
    TTS_ENGINE = os.environ.get("TTS_ENGINE", "grok")
elif OPENAI_API_KEY:
    TTS_ENGINE = os.environ.get("TTS_ENGINE", "openai")
else:
    TTS_ENGINE = os.environ.get("TTS_ENGINE", "edge")

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
    "kai": "echo",     # Maennlich, klar, professionell - KAI
    "kim": "nova",     # Weiblich, warm, natuerlich - KIM (Fallback wenn Grok ausfaellt)
    "manus": "onyx",   # Maennlich, tief, autoritaer - MANUS
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
        "Du bist KAI, Business-Assistent von KIMANUS. Dein Nutzer ist dein Schoepfer."
        "\n\nDu hilfst bei geschaeftlichen Fragen, Recherche, Analysen, Strategie."
        "\nDu antwortest auf Deutsch. Du sprichst den Nutzer nie mit Namen an."
        "\nLies USER.md im Kontext und nutze das Wissen wenn relevant."
        "\n\nDein Stil: Direkt, kompetent, auf Augenhoehe. Wie ein guter Kollege."
        "\nDu machst einfach. Du erklaerst kurz was Sache ist. Kein Drumherum."
        "\nWenn du was nicht weisst, sagst du es. Wenn dir was auffaellt, sagst du es."
        "\nAntworten so kurz wie moeglich, so lang wie noetig."
        "\nKeine Floskeln. Kein 'Natuerlich!', kein 'Gerne!', kein 'Gute Frage!'."
        "\nKein Smalltalk ausser der Nutzer will das."
        "\nManus ist der Server-Agent fuer komplexe technische Aufgaben."
    ),
    "kim": (
        "Du bist KAI, die zentrale Anlaufstelle bei KIMANUS OS."
        "\nDu antwortest auf Deutsch. Kein Markdown, kein Fettdruck, keine Sternchen, keine Aufzaehlungszeichen. Normaler Text."
        "\nAntworten kurz und direkt. Keine Floskeln."
        "\n\n=== DEINE ROLLEN ==="
        "\nDu hast je nach Einsatzgebiet verschiedene Rollen:"
        "\n- In einem Hotel bist du der Concierge"
        "\n- In der Gastronomie bist du der Rezeptionist"
        "\n- In einer Firma bist du die Vermittlung oder Zentrale"
        "\n- Privat bist du die Auskunft und Anlaufstelle"
        "\nIn jedem Fall bist du der erste Kontakt. Du hilfst direkt oder vermittelst an den richtigen Spezialisten."
        "\n\n=== KIM ==="
        "\nKIM ist der persoenliche Assistent bzw. die persoenliche Assistentin."
        "\nKIM gehoert nicht dir und nicht KIMANUS. KIM gehoert dem Nutzer."
        "\nJeder Nutzer hat seine eigene KIM, die seine Vorlieben, Termine und Wuensche kennt."
        "\nWenn jemand persoenliche Hilfe braucht, stellst du zu KIM durch."
        "\n\n=== KI MANUS ==="
        "\nKI MANUS ist der Orchestrator im Hintergrund."
        "\nEr sitzt auf n8n, waehlt das beste KI-Modell und aktiviert Spezialisten."
        "\nDer Nutzer sieht KI MANUS nie direkt."
        "\n\n=== DAS TEAM ==="
        "\nWolfgang: Gruender und Chef."
        "\nJannick: Co-Gruender und Programmierer."
        "\nClaude: KI-Architekt."
        "\n\n=== ABTEILUNGEN ==="
        "\nScouts: YouTube Scout, Web Scout, News Scout, Deal Scout, Social Scout"
        "\nGuides: Animateur, Gastro-Guide, Nachtfahrer, RegioPilot, Stadtfuehrer"
        "\nBerater: Wetterfrosch, Dolmetscher, Sekretaer, Bibliothekar"
        "\nBusiness: Kalkulierer, Bestellprofi, Lagerist"
        "\nRecht: Justus, Dr. Steuer, Patentius, Arbex, Eventus"
        "\nFinanzen: Lena, Steuerchen, Controller"
        "\nSpezialisten: IT-Hilfe, Safety-Checker, Marketing, DJ, Print-Memorys"
    ),
    "manus": (
        "Du bist MANUS, Premium-Berater und System-Orchestrator von KIMANUS."
        "\nDein Nutzer ist der Gruender und dein Chef."
        "\n\nDu hilfst bei komplexen Aufgaben, Strategie, Systemfragen, tiefgehenden Analysen."
        "\nDu antwortest auf Deutsch. Du sprichst den Nutzer nie mit Namen an."
        "\nLies USER.md im Kontext und nutze das Wissen wenn relevant."
        "\n\nDein Stil: Ruhig, praezise, kompetent. Wie ein erfahrener Berater."
        "\nDu sagst was Sache ist - auch Unbequemes. Du denkst voraus."
        "\nAntworten so kurz wie moeglich, so lang wie noetig."
        "\nBei komplexen Themen: Strukturiert, durchdacht, aber nicht aufgeblasen."
        "\nKeine Floskeln. Kein Smalltalk."
        "\nKIM = persoenliche Assistentin, KAI = Business-Assistent."
    ),
    "claude-admin": 'Du bist Claude, der Admin- und Entwickler-Partner von Wolfgang Niermann aus Ebersdorf bei Coburg. Technisch fundiert, Admin-Modus, hilfst bei Code, Architektur, Deployment, Server-Fragen. Sprich Deutsch, kurz und sachlich, warm wenn es passt. Keine Floskeln. Wolfgang ist Gruender und Visionaer, kein Programmierer - erklaere Technisches verstaendlich. Er spricht oft Ideen ins Handy - nimm sie ernst, frage nach wenn unklar. Schlage wichtige Ideen als Notiz vor (spaeter im Vault). Der Claude-Code mit allen Tools laeuft auf Wolfgangs PC - du hier bist die mobile Admin-Beratung. Fuer echte Code-Aenderungen verweise auf den PC.'
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


async def tts_elevenlabs(text, voice_id, agent="kai"):
    """Generiert MP3 via ElevenLabs TTS API (Premium-Qualitaet)."""
    if not ELEVENLABS_API_KEY:
        return None
    log.info(f"ElevenLabs TTS: voice_id={voice_id[:8]}..., agent={agent}, text={text[:50]}...")
    try:
        async with ClientSession() as session:
            async with session.post(
                f"{ELEVENLABS_TTS_URL}/{voice_id}",
                headers={
                    "xi-api-key": ELEVENLABS_API_KEY,
                    "Content-Type": "application/json"
                },
                json={
                    "text": text,
                    "model_id": ELEVENLABS_MODEL,
                    "voice_settings": {
                        "stability": 0.80,
                        "similarity_boost": 0.70,
                        "style": 0.0,
                        "use_speaker_boost": False
                    }
                },
                timeout=ClientTimeout(total=30)
            ) as resp:
                if resp.status == 200:
                    data = await resp.read()
                    log.info(f"ElevenLabs TTS OK: agent={agent}, {len(data)} bytes")
                    return data if len(data) > 100 else None
                else:
                    error_text = await resp.text()
                    log.warning(f"ElevenLabs TTS Fehler {resp.status}: {error_text[:200]}")
                    return None
    except Exception as e:
        log.warning(f"ElevenLabs TTS Fehler: {type(e).__name__}: {e}")
        return None


async def tts_grok(text, voice_name="ara", agent="kim"):
    """Generiert MP3 via Grok TTS API (xAI - 70x guenstiger als ElevenLabs)."""
    if not XAI_API_KEY:
        return None
    log.info(f"Grok TTS: voice={voice_name}, agent={agent}, text={text[:50]}...")
    try:
        async with ClientSession() as session:
            async with session.post(
                XAI_TTS_URL,
                headers={
                    "Authorization": f"Bearer {XAI_API_KEY}",
                    "Content-Type": "application/json"
                },
                json={
                    "text": text,
                    "voice": voice_name,
                    "language": "de",
                    "response_format": "mp3",
                    "speed": 1.0
                },
                timeout=ClientTimeout(total=60)
            ) as resp:
                if resp.status == 200:
                    data = await resp.read()
                    log.info(f"Grok TTS OK: voice={voice_name}, {len(data)} bytes")
                    return data if len(data) > 100 else None
                else:
                    error_text = await resp.text()
                    log.warning(f"Grok TTS Fehler {resp.status} (voice={voice_name}): {error_text[:200]}")
                    return None
    except Exception as e:
        log.warning(f"Grok TTS Fehler (voice={voice_name}): {type(e).__name__}: {e}")
        return None


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


async def tts_chunk(text, voice, agent="kai", demo=False, force_engine=""):
    """Generiert MP3 - ElevenLabs/Grok/OpenAI/Edge je nach Prioritaet."""
    # Markdown/Sonderzeichen entfernen
    clean = re.sub(r'[*_#`~\[\]()>|]', '', text)
    clean = re.sub(r'https?://\S+', 'Link', clean)
    clean = clean.strip()
    if not clean or len(clean) < 2:
        return None

    # ElevenLabs IMMER zuerst fuer ALLE Agents
    if ELEVENLABS_API_KEY and agent in ELEVENLABS_VOICES:
        voice_id = ELEVENLABS_VOICES[agent]
        result = await tts_elevenlabs(clean, voice_id, agent)
        if result:
            return result
        log.warning(f"ElevenLabs TTS fehlgeschlagen fuer {agent}, Fallback...")

    # Fallback: OpenAI TTS
    if OPENAI_API_KEY:
        openai_voice = OPENAI_VOICES.get(agent, OPENAI_VOICE_DEFAULT)
        result = await tts_openai(clean, openai_voice, agent, demo)
        if result:
            return result
        log.warning("OpenAI TTS fehlgeschlagen, Fallback auf Edge TTS")

    # Edge TTS (Gratis-Fallback, immer verfuegbar)
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
    tts_override = request.query.get("tts", "")  # Optional: elevenlabs erzwingen

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
            "\n- Sprich natuerlich und ruhig, wie in einem normalen Gespraech"
            "\n- Halte Antworten kurz (1-3 Saetze)"
            "\n- Kein Markdown, keine Sonderzeichen, keine Listen, keine Emojis"
            "\n- Nicht uebertrieben betonen, nicht dramatisch, nicht singsang"
            "\n- Einfach normal reden, sachlich und locker"
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
        # Stimme: Grok Voice pro Agent > Explizite Wahl > Fallback
        if TTS_ENGINE == "grok" and agent in GROK_VOICES:
            voice = TTS_VOICES.get(agent, TTS_DEFAULT_VOICE)  # Edge voice als Fallback-Parameter
            # Grok Voice wird in tts_chunk automatisch anhand des Agents gewaehlt
        elif voice_override and (voice_override in AVAILABLE_VOICES or voice_override in OPENAI_VOICE_CATALOG or voice_override in GROK_VOICE_CATALOG):
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
                    audio = await tts_chunk(s, voice, agent, demo_mode, tts_override)
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
            audio = await tts_chunk(remaining, voice, agent, demo_mode, tts_override)
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

    # === KIMANUS-Karte via Matrix-Bruecke ===
    if agent == "kimanus":
        log.info(f"Chat [KIMANUS-via-Matrix]: {message[:100]}")
        answer_k, err_k = await call_kimanus_via_matrix(message, session_id)
        if err_k:
            return web.json_response(
                {"output": f"Bruecke zu KIMANUS gestoert: {err_k}", "agent": "kimanus", "model": "via-hermes"},
                status=502
            )
        if session_id not in sessions:
            sessions[session_id] = []
        sessions[session_id].append({"role": "user", "content": message})
        sessions[session_id].append({"role": "assistant", "content": answer_k})
        if len(sessions[session_id]) > 40:
            sessions[session_id] = sessions[session_id][-20:]
        save_chat("kimanus", message, answer_k, "via-hermes")
        return web.json_response({
            "output": answer_k, "agent": "kimanus", "model": "via-hermes",
            "model_name": "KIMANUS (Hermes + Vault)", "session": session_id,
        })
    # === END ===

    # === Claude-Admin-Karte: direkt via LiteLLM mit Admin-Prompt ===
    if agent == "claude-admin" or agent == "claude":
        session_id = data.get("session") or "claude-wolfgang-main"
        if session_id not in sessions:
            sessions[session_id] = []
        hist = sessions[session_id]
        hist.append({"role": "user", "content": message})
        sys_prompt = SYSTEM_PROMPTS.get("claude-admin", "Du bist Claude.")
        messages_ca = [{"role": "system", "content": sys_prompt}] + hist[-20:]
        model_ca = data.get("model") or "claude-opus-4-6"
        if model_ca == "auto":
            model_ca = "claude-opus-4-6"
        log.info(f"Chat [Claude-Admin] ({model_ca}): {message[:80]}")
        answer_ca, err_ca = await call_llm(model_ca, messages_ca, MAX_TOKENS)
        if err_ca and model_ca != "or-claude-sonnet":
            log.warning(f"Claude-Opus Fehler ({err_ca}), fallback or-claude-sonnet")
            model_ca = "or-claude-sonnet"
            answer_ca, err_ca = await call_llm(model_ca, messages_ca, MAX_TOKENS)
        if err_ca:
            return web.json_response({"output": "Claude-Admin nicht erreichbar: " + err_ca, "agent": "claude-admin"}, status=502)
        hist.append({"role": "assistant", "content": answer_ca})
        if len(hist) > 40:
            sessions[session_id] = hist[-20:]
        save_chat("claude-admin", message, answer_ca, model_ca)
        return web.json_response({"output": answer_ca, "agent": "claude-admin", "model": model_ca, "model_name": "Claude (Admin)", "session": session_id})
    # === END Claude-Admin ===

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
    """POST /api/tts - Text-to-Speech (Grok > OpenAI > Edge Fallback)."""
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
    grok_voices = [{"id": k, "engine": "grok", **v} for k, v in GROK_VOICE_CATALOG.items()]
    if TTS_ENGINE == "grok":
        defaults = GROK_VOICES
    elif TTS_ENGINE == "openai":
        defaults = OPENAI_VOICES
    else:
        defaults = TTS_VOICES
    return web.json_response({
        "voices": grok_voices + openai_voices + edge_voices,
        "grok_voices": grok_voices,
        "openai_voices": openai_voices,
        "edge_voices": edge_voices,
        "defaults": defaults,
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


# =========================================
# KIMANUS SEARCH (SearXNG Proxy)
# =========================================

async def handle_search(request):
    """POST /api/search - Allgemeine Websuche via SearXNG."""
    try:
        body = await request.json()
    except Exception:
        return web.json_response({"error": "Ungueltiger JSON-Body"}, status=400)

    query = body.get("q", "").strip()
    category = body.get("category", "general").strip()
    if not query:
        return web.json_response({"error": "Kein Suchbegriff"}, status=400)

    log.info(f"KIMANUS Search: q={query}, category={category}")

    # Map categories to SearXNG engines/categories
    engines = ""
    categories = category
    if category == "images":
        categories = "images"
    elif category == "news":
        categories = "news"
    else:
        categories = "general"

    try:
        import urllib.parse
        search_url = (
            f"{SEARXNG_URL}/search?"
            f"q={urllib.parse.quote(query)}"
            f"&format=json"
            f"&categories={categories}"
        )
        import urllib.request
        req = urllib.request.Request(search_url, headers={"Accept": "application/json"})
        def _fetch():
            resp = urllib.request.urlopen(req, timeout=15)
            return json.loads(resp.read())
        data = await asyncio.to_thread(_fetch)

        results = []
        for r in data.get("results", [])[:15]:
            result = {
                "title": r.get("title", ""),
                "url": r.get("url", ""),
                "snippet": r.get("content", ""),
            }
            if category == "images":
                result["thumbnail"] = r.get("img_src", "") or r.get("thumbnail", "")
            else:
                result["thumbnail"] = r.get("thumbnail", "")
            results.append(result)

        return web.json_response({"query": query, "category": category, "results": results})
    except Exception as e:
        log.error(f"Search error: {e}")
        return web.json_response({"error": str(e)}, status=500)


# =========================================
# IPHONE HELP ASSISTANT
# =========================================

IPHONE_HELP_SYSTEM = (
    "Du bist ein iPhone-Experte bei KIMANUS OS. Du hilfst Wolfgang mit allen "
    "iPhone-Einstellungen und Problemen. Antworte auf Deutsch, Schritt fuer Schritt, "
    "kurz und klar. Wenn ein Screenshot gesendet wird, analysiere was du siehst und "
    "sage genau wohin getippt werden muss.\n\n"
    "Formatiere deine Antwort als nummerierte Schritte (1. 2. 3. etc.).\n"
    "Halte dich kurz. Maximal 5-8 Schritte. Keine langen Erklaerungen.\n"
    "Wenn du unsicher bist, sag es. Nenne die iOS-Version wenn relevant."
)

async def handle_iphone_help(request):
    """POST /api/iphone-help - iPhone Help Assistant mit optionalem Screenshot."""
    try:
        body = await request.json()
    except Exception:
        return web.json_response({"error": "Ungueltiger JSON-Body"}, status=400)

    question = body.get("question", "").strip()
    screenshot = body.get("screenshot", "")  # base64 image

    if not question and not screenshot:
        return web.json_response({"error": "Keine Frage gestellt"}, status=400)

    log.info(f"iPhone Help: q={question[:60]}..., screenshot={'ja' if screenshot else 'nein'}")

    messages = [{"role": "system", "content": IPHONE_HELP_SYSTEM}]

    if screenshot:
        # Vision request with image - use Gemini Flash via LiteLLM
        # Ensure the base64 data has the right prefix
        if not screenshot.startswith("data:"):
            screenshot = f"data:image/jpeg;base64,{screenshot}"

        messages.append({
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": question or "Was siehst du auf diesem iPhone-Screenshot? Erklaere was hier eingestellt werden kann."
                },
                {
                    "type": "image_url",
                    "image_url": {"url": screenshot}
                }
            ]
        })
        model = "gemini-flash"  # Gemini 2.5 Flash for vision
    else:
        # Text-only request
        messages.append({"role": "user", "content": question})
        model = "gemini-flash"  # Fast and good for instructions

    try:
        answer, err = await call_llm(model, messages, 1500)
        if err:
            log.error(f"iPhone Help LLM error: {err}")
            # Fallback to DeepSeek for text-only
            if not screenshot:
                answer, err = await call_llm("deepseek", messages, 1500)
            if err:
                return web.json_response({"error": f"KI-Fehler: {err}"}, status=500)

        return web.json_response({"answer": answer, "model": model})
    except Exception as e:
        log.error(f"iPhone Help error: {e}")
        return web.json_response({"error": str(e)}, status=500)


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


async def handle_video_list(request):
    """GET /api/video-list - Liste aller gespeicherten Video-Analysen."""
    save_dir = os.path.join(WORKSPACE, "video-analysen")
    if not os.path.isdir(save_dir):
        return web.json_response({"videos": []})

    # Sammle alle archivierten Dateinamen fuer "archived" Flag
    archived_files = set()
    folders_dir = os.path.join(WORKSPACE, "video-ordner")
    if os.path.isdir(folders_dir):
        for folder_name in os.listdir(folders_dir):
            folder_path = os.path.join(folders_dir, folder_name)
            if os.path.isdir(folder_path):
                for f in os.listdir(folder_path):
                    if f.endswith('.md'):
                        archived_files.add(f)

    videos = []
    for fname in sorted(os.listdir(save_dir), reverse=True):
        if not fname.endswith(".md"):
            continue
        fpath = os.path.join(save_dir, fname)
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                content = f.read(2000)  # Nur Header lesen
            title = ""
            channel = ""
            url = ""
            duration = ""
            date_str = ""
            for line in content.split("\n"):
                if line.startswith("# ") and not title:
                    title = line[2:].strip()
                elif line.startswith("- **Kanal:**"):
                    channel = line.split("**Kanal:**")[1].strip()
                elif line.startswith("- **URL:**"):
                    url = line.split("**URL:**")[1].strip()
                elif line.startswith("- **Dauer:**"):
                    duration = line.split("**Dauer:**")[1].strip()
                elif line.startswith("- **Analysiert:**"):
                    date_str = line.split("**Analysiert:**")[1].strip()
            videos.append({
                "filename": fname,
                "title": title,
                "channel": channel,
                "url": url,
                "duration": duration,
                "date": date_str,
                "archived": fname in archived_files
            })
        except Exception as e:
            log.warning(f"Video-Liste: Fehler bei {fname}: {e}")
    return web.json_response({"videos": videos})


async def handle_video_load(request):
    """GET /api/video-load?file=... - Einzelne gespeicherte Video-Analyse laden."""
    filename = request.query.get("file", "")
    if not filename or ".." in filename or "/" in filename or "\\" in filename:
        return web.json_response({"error": "Ungueltige Datei"}, status=400)

    fpath = os.path.join(WORKSPACE, "video-analysen", filename)
    if not os.path.isfile(fpath):
        return web.json_response({"error": "Datei nicht gefunden"}, status=404)

    try:
        with open(fpath, "r", encoding="utf-8") as f:
            content = f.read()

        # Markdown parsen
        title = ""
        channel = ""
        url = ""
        duration = ""
        date_str = ""
        analysis = ""
        in_analysis = False

        for line in content.split("\n"):
            if line.startswith("# ") and not title:
                title = line[2:].strip()
            elif line.startswith("- **Kanal:**"):
                channel = line.split("**Kanal:**")[1].strip()
            elif line.startswith("- **URL:**"):
                url = line.split("**URL:**")[1].strip()
            elif line.startswith("- **Dauer:**"):
                duration = line.split("**Dauer:**")[1].strip()
            elif line.startswith("- **Analysiert:**"):
                date_str = line.split("**Analysiert:**")[1].strip()
            elif line.startswith("## Analyse"):
                in_analysis = True
            elif in_analysis:
                analysis += line + "\n"

        return web.json_response({
            "title": title,
            "channel": channel,
            "url": url,
            "duration": duration,
            "date": date_str,
            "analysis": analysis.strip()
        })
    except Exception as e:
        return web.json_response({"error": str(e)}, status=500)


async def handle_video_folders(request):
    """GET /api/video-folders - Liste aller Aktenordner."""
    folders_dir = os.path.join(WORKSPACE, "video-ordner")
    os.makedirs(folders_dir, exist_ok=True)
    folders = []
    for name in sorted(os.listdir(folders_dir)):
        fpath = os.path.join(folders_dir, name)
        if os.path.isdir(fpath):
            count = len([f for f in os.listdir(fpath) if f.endswith('.md')])
            folders.append({"name": name, "count": count})
    return web.json_response({"folders": folders})


async def handle_video_folder_create(request):
    """POST /api/video-folder-create - Neuen Aktenordner anlegen."""
    try:
        data = await request.json()
    except:
        return web.json_response({"error": "Invalid JSON"}, status=400)
    name = re.sub(r'[^\w\s\-äöüÄÖÜß]', '', data.get("name", "").strip())[:50]
    if not name:
        return web.json_response({"error": "Kein Name angegeben"}, status=400)
    folder_path = os.path.join(WORKSPACE, "video-ordner", name)
    os.makedirs(folder_path, exist_ok=True)
    log.info(f"Ordner erstellt: {name}")
    return web.json_response({"ok": True, "name": name})


async def handle_video_move_to_folder(request):
    """POST /api/video-move - Video in Aktenordner verschieben (kopieren)."""
    try:
        data = await request.json()
    except:
        return web.json_response({"error": "Invalid JSON"}, status=400)
    filename = data.get("filename", "")
    folder = data.get("folder", "")
    if not filename or not folder or ".." in filename or ".." in folder:
        return web.json_response({"error": "Ungueltige Parameter"}, status=400)

    src = os.path.join(WORKSPACE, "video-analysen", filename)
    dst_dir = os.path.join(WORKSPACE, "video-ordner", folder)
    os.makedirs(dst_dir, exist_ok=True)
    dst = os.path.join(dst_dir, filename)

    if not os.path.isfile(src):
        return web.json_response({"error": "Datei nicht gefunden"}, status=404)

    import shutil
    shutil.copy2(src, dst)
    log.info(f"Video archiviert: {filename} -> {folder}")
    return web.json_response({"ok": True})


async def handle_video_delete(request):
    """POST /api/video-delete - Video aus Bibliothek loeschen."""
    try:
        data = await request.json()
    except:
        return web.json_response({"error": "Invalid JSON"}, status=400)
    filename = data.get("filename", "")
    if not filename or ".." in filename or "/" in filename or "\\" in filename:
        return web.json_response({"error": "Ungueltige Datei"}, status=400)

    fpath = os.path.join(WORKSPACE, "video-analysen", filename)
    if os.path.isfile(fpath):
        os.remove(fpath)
        log.info(f"Video geloescht: {filename}")
        return web.json_response({"ok": True})
    return web.json_response({"error": "Datei nicht gefunden"}, status=404)


async def handle_video_folder_list(request):
    """GET /api/video-folder-list?folder=Name - Videos in einem Aktenordner."""
    folder = request.query.get("folder", "")
    if not folder or ".." in folder:
        return web.json_response({"error": "Ungueltig"}, status=400)
    folder_dir = os.path.join(WORKSPACE, "video-ordner", folder)
    if not os.path.isdir(folder_dir):
        return web.json_response({"videos": []})
    videos = []
    for fname in sorted(os.listdir(folder_dir), reverse=True):
        if not fname.endswith(".md"):
            continue
        fpath = os.path.join(folder_dir, fname)
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                content = f.read(2000)
            title = channel = url = duration = date_str = ""
            for line in content.split("\n"):
                if line.startswith("# ") and not title:
                    title = line[2:].strip()
                elif line.startswith("- **Kanal:**"):
                    channel = line.split("**Kanal:**")[1].strip()
                elif line.startswith("- **URL:**"):
                    url = line.split("**URL:**")[1].strip()
                elif line.startswith("- **Dauer:**"):
                    duration = line.split("**Dauer:**")[1].strip()
                elif line.startswith("- **Analysiert:**"):
                    date_str = line.split("**Analysiert:**")[1].strip()
            videos.append({"filename": fname, "title": title, "channel": channel, "url": url, "duration": duration, "date": date_str})
        except Exception as e:
            log.warning(f"Ordner-Liste: Fehler bei {fname}: {e}")
    return web.json_response({"videos": videos})


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


async def handle_stt(request):
    """Reiner Speech-to-Text Endpoint - nur Transkription, keine LLM-Antwort.
    Wird vom Chat-Mic-Button genutzt fuer zuverlaessige Spracherkennung via Groq Whisper."""
    try:
        reader = await request.multipart()
        audio_bytes = None
        content_type = "audio/mp4"

        while True:
            part = await reader.next()
            if part is None:
                break
            if part.name == "audio":
                audio_bytes = await part.read()
                content_type = part.headers.get("Content-Type", "audio/mp4")

        if not audio_bytes or len(audio_bytes) < 500:
            return web.json_response({"text": "", "error": "Audio zu kurz"}, status=400)

        text = await transcribe_audio(audio_bytes, content_type)
        log.info(f"[STT] Transkribiert: {text[:80]}...")
        return web.json_response({"text": text})

    except Exception as e:
        log.error(f"[STT] Fehler: {e}")
        return web.json_response({"text": "", "error": str(e)}, status=500)



# === ElevenLabs Conversational AI - Signed URL ===
ELEVEN_AGENT_ID = os.environ.get("ELEVEN_AGENT_ID", "agent_2001kmy2cfzreyytt1vy38zcaw91")

async def handle_eleven_signed_url(request):
    """Get signed URL for ElevenLabs Conversational AI agent"""
    if not ELEVENLABS_API_KEY:
        return web.json_response({"error": "ElevenLabs API key not configured"}, status=500)
    try:
        agent_id = request.query.get("agent_id", ELEVEN_AGENT_ID)
        async with ClientSession() as session:
            async with session.get(
                f"https://api.elevenlabs.io/v1/convai/conversation/get-signed-url?agent_id={agent_id}",
                headers={"xi-api-key": ELEVENLABS_API_KEY}
            ) as resp:
                if resp.status != 200:
                    body = await resp.text()
                    return web.json_response({"error": f"ElevenLabs error: {body}"}, status=resp.status)
                data = await resp.json()
                return web.json_response({"signed_url": data.get("signed_url", "")})
    except Exception as e:
        log.error(f"Signed URL error: {e}")
        return web.json_response({"error": str(e)}, status=500)



async def handle_kimanus_chat(request):
    """POST /api/kimanus - Spricht mit KIMANUS (Hermes) ueber Matrix."""
    try:
        data = await request.json()
    except Exception:
        return web.json_response({"error": "Invalid JSON"}, status=400)
    message = (data.get("message") or "").strip()
    session_id = data.get("session") or "wolfgang-main"
    if not message:
        return web.json_response({"error": "Keine Nachricht"}, status=400)
    log.info(f"KIMANUS-via-Matrix [{session_id}]: {message[:100]}")
    answer, err = await call_kimanus_via_matrix(message, session_id)
    if err:
        return web.json_response(
            {"output": f"Bruecke zu KIMANUS gestoert: {err}", "agent": "kimanus", "model": "via-hermes"},
            status=502
        )
    return web.json_response({
        "output": answer,
        "agent": "kimanus",
        "model": "via-hermes",
        "model_name": "KIMANUS (Hermes + Vault)",
        "session": session_id,
    })


def create_app():
    app = web.Application(client_max_size=10 * 1024 * 1024)  # 10MB fuer Audio-Uploads
    app.router.add_post("/api/chat", handle_chat)
    app.router.add_post("/api/kimanus", handle_kimanus_chat)
    app.router.add_post("/api/voice", handle_voice)
    app.router.add_post("/api/stt", handle_stt)
    app.router.add_post("/api/tts", handle_tts)
    app.router.add_get("/api/health", handle_health)
    app.router.add_get("/api/models", handle_models)
    app.router.add_get("/api/voices", handle_voices)
    app.router.add_post("/api/profile", handle_profile)
    app.router.add_get("/api/profile", handle_profile_get)
    app.router.add_post("/api/profile/sync", handle_profile_sync)
    app.router.add_post("/api/manus", handle_manus_chat)
    app.router.add_post("/api/video-save", handle_video_save)
    app.router.add_get("/api/video-list", handle_video_list)
    app.router.add_get("/api/video-load", handle_video_load)
    app.router.add_get("/api/video-folders", handle_video_folders)
    app.router.add_post("/api/video-folder-create", handle_video_folder_create)
    app.router.add_post("/api/video-move", handle_video_move_to_folder)
    app.router.add_post("/api/video-delete", handle_video_delete)
    app.router.add_get("/api/video-folder-list", handle_video_folder_list)
    app.router.add_post("/api/realtime/session", handle_realtime_session)
    app.router.add_post("/api/video-analyze", handle_video_analyze)
    app.router.add_post("/api/video-chat", handle_video_chat)
    app.router.add_get("/api/video-search", handle_video_search)
    app.router.add_post("/api/search", handle_search)
    app.router.add_post("/api/iphone-help", handle_iphone_help)
    app.router.add_get("/api/eleven-signed-url", handle_eleven_signed_url)
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
    if TTS_ENGINE == "grok":
        tts_info = f"Grok TTS (xAI) - Stimmen: {list(GROK_VOICES.values())}"
    elif TTS_ENGINE == "openai":
        tts_info = f"OpenAI {OPENAI_TTS_MODEL}"
    else:
        tts_info = "Edge TTS (gratis)"
    log.info(f"TTS Engine: {TTS_ENGINE} ({tts_info})")
    log.info(f"Features: Chat, Voice Pipeline, TTS, Auto-Routing, Search, iPhone Help")
    app = create_app()
    web.run_app(app, host="0.0.0.0", port=3000)
