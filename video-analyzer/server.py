"""
KIMANUS OS - Video Analyzer Agent
Laeuft unter KAI (A4BIS) - Container #11
Analysiert YouTube-Videos: Transkript + Keyframes + KI-Analyse
"""

import asyncio
import base64
import json
import logging
import os
import re
import subprocess
import tempfile
import time
import urllib.request
import uuid
from pathlib import Path

from aiohttp import web, ClientSession

# ============================================================
# Konfiguration
# ============================================================

PORT = 3001
TEMP_DIR = Path("/tmp/video-analyzer")
TEMP_DIR.mkdir(parents=True, exist_ok=True)

# LiteLLM Gateway (intern im Docker-Netzwerk)
LITELLM_URL = os.getenv("LITELLM_URL", "http://litellm:4000")
LITELLM_KEY = os.getenv("LITELLM_KEY", "sk-manus-geheimschluessel-1234")

# Gemini direkt (fuer Bild-Analyse, da LiteLLM kein Bild-Upload kann)
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

# Groq Whisper (fuer Transkription wenn kein Untertitel vorhanden)
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_WHISPER_URL = "https://api.groq.com/openai/v1/audio/transcriptions"

# Maximale Keyframes
MAX_FRAMES = 20
FRAME_INTERVAL_SECS = 30  # Alle 30 Sekunden ein Frame

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("video-analyzer")

# Gespeicherte Analysen (In-Memory Cache)
analyses_cache = {}


# ============================================================
# YouTube Hilfsfunktionen
# ============================================================

def extract_video_id(url: str) -> str | None:
    """Extrahiert die Video-ID aus verschiedenen YouTube-URL-Formaten."""
    patterns = [
        r'(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/embed/|youtube\.com/v/)([a-zA-Z0-9_-]{11})',
        r'(?:youtube\.com/shorts/)([a-zA-Z0-9_-]{11})',
    ]
    for p in patterns:
        m = re.search(p, url)
        if m:
            return m.group(1)
    return None


async def get_video_info_oembed(video_id: str) -> dict:
    """Holt Video-Metadaten via YouTube oEmbed API (zuverlaessig, kein Bot-Block)."""
    oembed_url = f"https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v={video_id}&format=json"
    try:
        def _fetch():
            req = urllib.request.Request(oembed_url, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
            })
            resp = urllib.request.urlopen(req, timeout=10)
            return json.loads(resp.read())

        data = await asyncio.to_thread(_fetch)
        if data.get("title"):
            return {
                "title": data.get("title", ""),
                "channel": data.get("author_name", ""),
                "duration_string": "",  # oEmbed liefert keine Dauer
                "description": "",  # oEmbed liefert keine Beschreibung
                "thumbnail": f"https://img.youtube.com/vi/{video_id}/maxresdefault.jpg",
                "view_count": "0",
            }
    except Exception as e:
        log.error(f"oEmbed error: {e}")
    return {}


async def get_video_info_innertube(video_id: str) -> dict:
    """Versucht Video-Info via YouTube Innertube API."""
    innertube_url = "https://www.youtube.com/youtubei/v1/player"
    payload = {
        "videoId": video_id,
        "context": {
            "client": {
                "clientName": "WEB",
                "clientVersion": "2.20240101.00.00",
                "hl": "de",
                "gl": "DE",
            }
        }
    }
    try:
        payload_bytes = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            innertube_url,
            data=payload_bytes,
            headers={"Content-Type": "application/json"},
        )
        def _do_request():
            resp = urllib.request.urlopen(req, timeout=15)
            return json.loads(resp.read())

        data = await asyncio.to_thread(_do_request)
        details = data.get("videoDetails", {})
        if details.get("title"):
            return {
                "title": details.get("title", ""),
                "channel": details.get("author", ""),
                "duration_string": _format_duration(int(details.get("lengthSeconds", 0))),
                "description": details.get("shortDescription", ""),
                "thumbnail": f"https://img.youtube.com/vi/{video_id}/maxresdefault.jpg",
                "view_count": details.get("viewCount", "0"),
                "_captions": data.get("captions", {}),
            }
    except Exception as e:
        log.warning(f"Innertube error: {e}")
    return {}


async def get_video_info_ytdlp(video_id: str) -> dict:
    """Holt Video-Metadaten via yt-dlp (letzter Fallback)."""
    cmd = [
        "yt-dlp", "--dump-json", "--no-download",
        "--no-playlist", "--no-warnings",
        "--extractor-args", "youtube:player_client=web",
        f"https://www.youtube.com/watch?v={video_id}"
    ]
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=30)
        if proc.returncode == 0:
            return json.loads(stdout.decode())
        log.warning(f"yt-dlp info error: {stderr.decode()[:200]}")
    except Exception as e:
        log.error(f"Video info error: {e}")
    return {}


def _format_duration(secs: int) -> str:
    mins, s = divmod(secs, 60)
    hrs, m = divmod(mins, 60)
    if hrs > 0:
        return f"{hrs}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


async def get_transcript_ytapi(video_id: str) -> str | None:
    """Holt Transkript via youtube-transcript-api (zuverlaessigste Methode)."""
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
        def _fetch():
            try:
                transcript_list = YouTubeTranscriptApi.get_transcript(video_id, languages=["de", "en"])
            except Exception:
                # Versuch ohne Sprachpraeferenz
                transcript_list = YouTubeTranscriptApi.get_transcript(video_id)
            return " ".join([t["text"] for t in transcript_list])

        transcript = await asyncio.to_thread(_fetch)
        if transcript and len(transcript.strip()) > 50:
            log.info(f"Transkript via youtube-transcript-api: {len(transcript)} Zeichen")
            return transcript
    except ImportError:
        log.warning("youtube-transcript-api nicht installiert")
    except Exception as e:
        log.warning(f"youtube-transcript-api error: {e}")
    return None


async def get_transcript_innertube(video_id: str, captions_data: dict) -> str | None:
    """Holt Transkript direkt via YouTube Innertube Captions API."""
    try:
        renderer = captions_data.get("playerCaptionsTracklistRenderer", {})
        tracks = renderer.get("captionTracks", [])

        if not tracks:
            return None

        # Bevorzuge Deutsch, dann Englisch
        chosen = None
        for lang_pref in ["de", "en"]:
            for track in tracks:
                if track.get("languageCode", "").startswith(lang_pref):
                    chosen = track
                    break
            if chosen:
                break

        if not chosen:
            chosen = tracks[0]

        caption_url = chosen.get("baseUrl", "")
        if not caption_url:
            return None

        if "fmt=" not in caption_url:
            caption_url += "&fmt=json3"
        else:
            caption_url = re.sub(r"fmt=\w+", "fmt=json3", caption_url)

        def _fetch_captions():
            resp = urllib.request.urlopen(caption_url, timeout=15)
            return json.loads(resp.read())

        data = await asyncio.to_thread(_fetch_captions)
        events = data.get("events", [])
        texts = []
        for event in events:
            segs = event.get("segs", [])
            for seg in segs:
                t = seg.get("utf8", "").strip()
                if t and t != "\n":
                    texts.append(t)
        transcript = " ".join(texts)
        if len(transcript) > 50:
            log.info(f"Transkript via Innertube Captions: {len(transcript)} Zeichen")
            return transcript
    except Exception as e:
        log.error(f"Innertube captions error: {e}")
    return None


async def get_transcript(video_id: str, info: dict) -> str | None:
    """
    Versucht Transkript zu holen (Prioritaet):
    1. youtube-transcript-api (zuverlaessigste)
    2. Innertube Captions API
    3. yt-dlp Untertitel
    4. Groq Whisper (Audio-Transkription)
    """
    # Methode 1: youtube-transcript-api (beste Methode)
    transcript = await get_transcript_ytapi(video_id)
    if transcript:
        return transcript

    # Methode 2: Innertube Captions (wenn verfuegbar)
    captions = info.get("_captions", {})
    if captions:
        transcript = await get_transcript_innertube(video_id, captions)
        if transcript:
            return transcript

    work_dir = TEMP_DIR / str(uuid.uuid4())
    work_dir.mkdir(parents=True, exist_ok=True)

    try:
        # Methode 3: yt-dlp Untertitel
        transcript = await _get_subtitles(video_id, work_dir)
        if transcript and len(transcript.strip()) > 50:
            log.info(f"Transkript via Untertitel: {len(transcript)} Zeichen")
            return transcript

        # Methode 4: Groq Whisper
        if GROQ_API_KEY:
            transcript = await _whisper_transcribe(video_id, work_dir)
            if transcript and len(transcript.strip()) > 50:
                log.info(f"Transkript via Whisper: {len(transcript)} Zeichen")
                return transcript

        log.warning("Kein Transkript verfuegbar")
        return None
    finally:
        _cleanup_dir(work_dir)


async def _get_subtitles(video_id: str, work_dir: Path) -> str | None:
    """Holt Untertitel via yt-dlp."""
    url = f"https://www.youtube.com/watch?v={video_id}"
    sub_file = work_dir / "subs"

    for lang_args in [
        ["--write-sub", "--sub-lang", "de,en,de-orig"],
        ["--write-auto-sub", "--sub-lang", "de,en"],
    ]:
        cmd = [
            "yt-dlp", "--skip-download", "--no-playlist", "--no-warnings",
            "--extractor-args", "youtube:player_client=web",
            *lang_args, "--sub-format", "vtt",
            "-o", str(sub_file), url
        ]
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )
            await asyncio.wait_for(proc.communicate(), timeout=30)

            for vtt_file in work_dir.glob("*.vtt"):
                text = _parse_vtt(vtt_file.read_text(encoding="utf-8", errors="ignore"))
                if text and len(text.strip()) > 50:
                    return text
        except Exception as e:
            log.warning(f"Subtitle download error: {e}")

    return None


def _parse_vtt(vtt_content: str) -> str:
    """Parst VTT-Untertitel und entfernt Duplikate und Timestamps."""
    lines = []
    seen = set()
    for line in vtt_content.split("\n"):
        line = line.strip()
        if not line or line.startswith("WEBVTT") or line.startswith("Kind:") or \
           line.startswith("Language:") or "-->" in line or line.isdigit():
            continue
        clean = re.sub(r"<[^>]+>", "", line).strip()
        if clean and clean not in seen:
            seen.add(clean)
            lines.append(clean)
    return " ".join(lines)


async def _whisper_transcribe(video_id: str, work_dir: Path) -> str | None:
    """Laed Audio herunter und transkribiert via Groq Whisper."""
    url = f"https://www.youtube.com/watch?v={video_id}"
    audio_file = work_dir / "audio.mp3"

    cmd = [
        "yt-dlp", "--no-playlist", "--no-warnings",
        "--extractor-args", "youtube:player_client=web",
        "-x", "--audio-format", "mp3", "--audio-quality", "5",
        "--max-filesize", "25M",
        "-o", str(audio_file), url
    ]
    try:
        log.info("Lade Audio fuer Whisper...")
        proc = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        await asyncio.wait_for(proc.communicate(), timeout=120)

        actual_file = None
        for f in work_dir.glob("audio*"):
            actual_file = f
            break

        if not actual_file or not actual_file.exists():
            log.warning("Audio-Download fehlgeschlagen")
            return None

        file_size = actual_file.stat().st_size
        log.info(f"Audio heruntergeladen: {file_size / 1024 / 1024:.1f} MB")

        if file_size > 25 * 1024 * 1024:
            log.warning("Audio zu gross fuer Whisper (>25MB)")
            return None

        import aiohttp
        data = aiohttp.FormData()
        data.add_field("file", open(actual_file, "rb"), filename="audio.mp3", content_type="audio/mpeg")
        data.add_field("model", "whisper-large-v3")
        data.add_field("language", "de")
        data.add_field("response_format", "text")

        async with ClientSession() as session:
            async with session.post(
                GROQ_WHISPER_URL,
                headers={"Authorization": f"Bearer {GROQ_API_KEY}"},
                data=data,
                timeout=aiohttp.ClientTimeout(total=120)
            ) as resp:
                if resp.status == 200:
                    return await resp.text()
                else:
                    error = await resp.text()
                    log.error(f"Whisper error {resp.status}: {error[:200]}")
                    return None
    except Exception as e:
        log.error(f"Whisper transcription error: {e}")
        return None


# ============================================================
# Keyframe-Extraktion
# ============================================================

async def extract_keyframes(video_id: str, max_frames: int = MAX_FRAMES) -> list[dict]:
    """
    Laed Video herunter und extrahiert Keyframes mit ffmpeg.
    Gibt Liste von {timestamp, base64_image} zurueck.
    """
    work_dir = TEMP_DIR / str(uuid.uuid4())
    work_dir.mkdir(parents=True, exist_ok=True)

    try:
        url = f"https://www.youtube.com/watch?v={video_id}"
        video_file = work_dir / "video.mp4"

        cmd = [
            "yt-dlp", "--no-playlist", "--no-warnings",
            "--extractor-args", "youtube:player_client=web",
            "-f", "worst[ext=mp4]/worst",
            "--max-filesize", "100M",
            "-o", str(video_file), url
        ]
        log.info("Lade Video fuer Keyframes...")
        proc = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        await asyncio.wait_for(proc.communicate(), timeout=180)

        actual_file = None
        for f in work_dir.glob("video*"):
            if f.suffix in ('.mp4', '.mkv', '.webm'):
                actual_file = f
                break

        if not actual_file or not actual_file.exists():
            log.warning("Video-Download fehlgeschlagen")
            return []

        duration_cmd = [
            "ffprobe", "-v", "error", "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1", str(actual_file)
        ]
        proc = await asyncio.create_subprocess_exec(
            *duration_cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        stdout, _ = await proc.communicate()
        duration = float(stdout.decode().strip()) if stdout else 300

        interval = max(duration / max_frames, 10)

        frames_dir = work_dir / "frames"
        frames_dir.mkdir()

        ffmpeg_cmd = [
            "ffmpeg", "-i", str(actual_file),
            "-vf", f"fps=1/{int(interval)},scale=640:-1",
            "-q:v", "3", "-frames:v", str(max_frames),
            str(frames_dir / "frame_%04d.jpg")
        ]
        proc = await asyncio.create_subprocess_exec(
            *ffmpeg_cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        await asyncio.wait_for(proc.communicate(), timeout=120)

        frames = []
        for frame_file in sorted(frames_dir.glob("*.jpg")):
            idx = int(frame_file.stem.split("_")[1]) - 1
            timestamp_secs = int(idx * interval)
            mins, secs = divmod(timestamp_secs, 60)

            with open(frame_file, "rb") as f:
                img_data = base64.b64encode(f.read()).decode()

            frames.append({
                "timestamp": f"{mins:02d}:{secs:02d}",
                "timestamp_secs": timestamp_secs,
                "base64": img_data,
                "size_kb": len(img_data) * 3 // 4 // 1024,
            })

        log.info(f"{len(frames)} Keyframes extrahiert")
        return frames

    except Exception as e:
        log.error(f"Keyframe extraction error: {e}")
        return []
    finally:
        _cleanup_dir(work_dir)


# ============================================================
# KI-Analyse (Gemini Flash - YouTube-URL direkt oder Text+Bilder)
# ============================================================

async def analyze_with_gemini_url(video_id: str, video_info: dict, question: str | None = None) -> str | None:
    """
    Analysiert YouTube-Video direkt via Gemini (URL-basiert).
    Gemini kann YouTube-Videos nativ verstehen (Audio + Video + Transkript).
    Gibt None zurueck wenn es nicht klappt.
    """
    if not GEMINI_API_KEY:
        return None

    try:
        from google import genai
        from google.genai import types
        client = genai.Client(api_key=GEMINI_API_KEY)
    except ImportError:
        log.warning("google-genai nicht installiert, URL-Analyse nicht moeglich")
        return None

    title = video_info.get("title", "Unbekannt")
    channel = video_info.get("channel", "Unbekannt")
    video_url = f"https://www.youtube.com/watch?v={video_id}"

    if question:
        prompt = f"""Du bist der Video Analyzer Agent von KIMANUS OS, Teil von KAI (A4BIS).
Du analysierst YouTube-Videos fuer Wolfgang.

Beantworte folgende Frage zum Video auf Deutsch, praezise und hilfreich:
{question}"""
    else:
        prompt = f"""Du bist der Video Analyzer Agent von KIMANUS OS, Teil von KAI (A4BIS).
Analysiere dieses YouTube-Video umfassend fuer Wolfgang.

Erstelle eine strukturierte Analyse auf Deutsch:

1. **Zusammenfassung** (3-5 Saetze)
2. **Hauptthemen** (die wichtigsten Themen als Liste)
3. **Key Points** (die wichtigsten Erkenntnisse/Aussagen)
4. **Visueller Inhalt** (beschreibe wichtige visuelle Elemente)
5. **Bewertung** (Qualitaet, Zielgruppe, Nuetzlichkeit)
6. **Keywords** (fuer spaetere Suche)

Sei praezise, informativ und auf Deutsch. Basiere die Analyse auf dem gesamten Video-Inhalt (Audio, Bild, Untertitel)."""

    try:
        contents = [
            types.Content(
                role="user",
                parts=[
                    types.Part.from_uri(file_uri=video_url, mime_type="video/*"),
                    types.Part.from_text(text=prompt),
                ]
            )
        ]
        response = await asyncio.to_thread(
            lambda: client.models.generate_content(
                model="gemini-2.5-flash",
                contents=contents,
            )
        )
        if response.text and len(response.text) > 100:
            log.info(f"Gemini URL-Analyse erfolgreich: {len(response.text)} Zeichen")
            return response.text
    except Exception as e:
        log.warning(f"Gemini URL-Analyse error: {e}")
    return None


async def analyze_with_gemini(
    video_info: dict,
    transcript: str | None,
    frames: list[dict],
    question: str | None = None,
) -> str:
    """
    Analysiert Video mit Gemini Flash (Text + optional Bilder).
    Fallback auf LiteLLM wenn Gemini nicht verfuegbar.
    """
    if not GEMINI_API_KEY:
        return await _analyze_with_litellm(video_info, transcript, question)

    try:
        from google import genai
        client = genai.Client(api_key=GEMINI_API_KEY)
        use_new = True
    except ImportError:
        try:
            import google.generativeai as genai_old
            genai_old.configure(api_key=GEMINI_API_KEY)
            model = genai_old.GenerativeModel("gemini-2.5-flash")
            use_new = False
        except ImportError:
            return await _analyze_with_litellm(video_info, transcript, question)

    title = video_info.get("title", "Unbekannt")
    channel = video_info.get("channel", "Unbekannt")
    duration = video_info.get("duration_string", "?")
    description = (video_info.get("description", "") or "")[:500]

    if question:
        prompt = f"""Du bist der Video Analyzer Agent von KIMANUS OS, Teil von KAI (A4BIS).
Du analysierst YouTube-Videos fuer Wolfgang.

Video: "{title}" von {channel} ({duration})
Beschreibung: {description}

{"Transkript:" if transcript else "Kein Transkript verfuegbar."}
{transcript[:8000] if transcript else ""}

Beantworte folgende Frage zum Video auf Deutsch, praezise und hilfreich:
{question}"""
    else:
        prompt = f"""Du bist der Video Analyzer Agent von KIMANUS OS, Teil von KAI (A4BIS).
Analysiere dieses YouTube-Video umfassend fuer Wolfgang.

Video: "{title}" von {channel} ({duration})
Beschreibung: {description}

{"Transkript:" if transcript else "Kein Transkript verfuegbar - analysiere anhand der Keyframes und Metadaten."}
{transcript[:12000] if transcript else ""}

Erstelle eine strukturierte Analyse auf Deutsch:

1. **Zusammenfassung** (3-5 Saetze)
2. **Hauptthemen** (die wichtigsten Themen als Liste)
3. **Key Points** (die wichtigsten Erkenntnisse/Aussagen)
4. **Visueller Inhalt** (was in den Keyframes zu sehen ist, falls vorhanden)
5. **Bewertung** (Qualitaet, Zielgruppe, Nuetzlichkeit)
6. **Keywords** (fuer spaetere Suche)

Sei praezise, informativ und auf Deutsch."""

    parts = [prompt]

    # Bilder hinzufuegen (max 10)
    for frame in (frames[:10] if frames else []):
        try:
            img_bytes = base64.b64decode(frame["base64"])
            parts.append({"mime_type": "image/jpeg", "data": img_bytes})
            parts.append(f"[Keyframe bei {frame['timestamp']}]")
        except Exception:
            pass

    try:
        if use_new:
            response_obj = await asyncio.to_thread(
                lambda: client.models.generate_content(
                    model="gemini-2.5-flash",
                    contents=parts,
                )
            )
            return response_obj.text
        else:
            response = await asyncio.to_thread(
                lambda: model.generate_content(parts).text
            )
            return response
    except Exception as e:
        log.error(f"Gemini error: {e}")
        return await _analyze_with_litellm(video_info, transcript, question)


async def _analyze_with_litellm(video_info: dict, transcript: str | None, question: str | None = None) -> str:
    """Fallback-Analyse ueber LiteLLM (nur Text, keine Bilder)."""
    title = video_info.get("title", "Unbekannt")
    channel = video_info.get("channel", "Unbekannt")
    duration = video_info.get("duration_string", "?")

    if question:
        user_msg = f"Video: \"{title}\" von {channel}.\n\nTranskript:\n{transcript[:6000] if transcript else 'Nicht verfuegbar'}\n\nFrage: {question}"
    else:
        user_msg = f"Analysiere dieses Video: \"{title}\" von {channel} ({duration}).\n\nTranskript:\n{transcript[:6000] if transcript else 'Nicht verfuegbar'}\n\nErstelle eine strukturierte Analyse auf Deutsch mit: Zusammenfassung, Hauptthemen, Key Points, Bewertung, Keywords."

    import aiohttp
    async with ClientSession() as session:
        async with session.post(
            f"{LITELLM_URL}/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {LITELLM_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": "deepseek",
                "messages": [
                    {"role": "system", "content": "Du bist der Video Analyzer Agent von KIMANUS OS. Analysiere Videos praezise auf Deutsch."},
                    {"role": "user", "content": user_msg}
                ],
                "max_tokens": 2000,
                "temperature": 0.3,
            },
            timeout=aiohttp.ClientTimeout(total=60)
        ) as resp:
            if resp.status == 200:
                data = await resp.json()
                return data["choices"][0]["message"]["content"]
            else:
                return f"Analyse-Fehler: {resp.status}"


# ============================================================
# API Endpoints
# ============================================================

import aiohttp

async def handle_health(request):
    """Health Check."""
    return web.json_response({
        "status": "ok",
        "agent": "Video Analyzer",
        "parent": "KAI (A4BIS)",
        "version": "1.1.0",
    })


async def handle_analyze(request):
    """
    POST /analyze
    Body: {"url": "https://youtube.com/watch?v=...", "frames": true/false}
    Komplette Video-Analyse: Transkript + optional Keyframes + KI-Analyse
    """
    try:
        body = await request.json()
    except Exception:
        return web.json_response({"error": "Ungueltiger JSON-Body"}, status=400)

    url = body.get("url", "").strip()
    include_frames = body.get("frames", False)  # Default false (schneller)

    video_id = extract_video_id(url)
    if not video_id:
        return web.json_response({"error": "Ungueltige YouTube-URL"}, status=400)

    log.info(f"=== Analyse Start: {video_id} ===")
    start_time = time.time()

    # 1. Video-Info holen (oEmbed zuerst, dann Innertube, dann yt-dlp)
    log.info("Hole Video-Metadaten via oEmbed...")
    info = await get_video_info_oembed(video_id)

    if not info or not info.get("title"):
        log.info("oEmbed fehlgeschlagen, versuche Innertube...")
        info = await get_video_info_innertube(video_id)

    if not info or not info.get("title"):
        log.info("Innertube fehlgeschlagen, versuche yt-dlp...")
        info = await get_video_info_ytdlp(video_id)

    if not info:
        info = {
            "title": f"YouTube Video {video_id}",
            "channel": "Unbekannt",
            "duration_string": "?",
            "thumbnail": f"https://img.youtube.com/vi/{video_id}/maxresdefault.jpg",
            "description": "",
        }

    title = info.get("title", "Unbekannt")
    log.info(f"Video: {title}")

    # 2. Versuche zuerst Gemini-URL-Analyse (sieht + hoert das Video direkt!)
    log.info("Versuche Gemini URL-Direktanalyse...")
    analysis = await analyze_with_gemini_url(video_id, info)
    transcript = None
    frames = []

    if analysis:
        log.info("Gemini URL-Analyse erfolgreich!")
    else:
        # Fallback: Transkript + Keyframes manuell holen
        log.info("Gemini URL-Analyse nicht moeglich, hole Transkript manuell...")
        tasks = [get_transcript(video_id, info)]
        if include_frames:
            tasks.append(extract_keyframes(video_id))

        results = await asyncio.gather(*tasks, return_exceptions=True)

        transcript = results[0] if not isinstance(results[0], Exception) else None
        frames = results[1] if len(results) > 1 and not isinstance(results[1], Exception) else []

        # KI-Analyse mit Transkript/Frames
        log.info("Starte KI-Analyse mit Transkript...")
        analysis = await analyze_with_gemini(info, transcript, frames)

    elapsed = time.time() - start_time
    log.info(f"=== Analyse fertig in {elapsed:.1f}s ===")

    # Ergebnis cachen
    result = {
        "video_id": video_id,
        "title": title,
        "channel": info.get("channel", ""),
        "duration": info.get("duration_string", ""),
        "thumbnail": info.get("thumbnail", ""),
        "transcript_length": len(transcript) if transcript else 0,
        "frames_count": len(frames),
        "analysis": analysis,
        "elapsed_seconds": round(elapsed, 1),
    }
    analyses_cache[video_id] = {
        "result": result,
        "transcript": transcript,
        "frames": frames,
        "info": info,
    }

    return web.json_response(result)


async def handle_transcript(request):
    """
    POST /transcript
    Body: {"url": "https://youtube.com/watch?v=..."}
    Nur Transkript holen.
    """
    try:
        body = await request.json()
    except Exception:
        return web.json_response({"error": "Ungueltiger JSON-Body"}, status=400)

    url = body.get("url", "").strip()
    video_id = extract_video_id(url)
    if not video_id:
        return web.json_response({"error": "Ungueltige YouTube-URL"}, status=400)

    info = await get_video_info_oembed(video_id)
    if not info:
        info = {}
    transcript = await get_transcript(video_id, info)

    return web.json_response({
        "video_id": video_id,
        "title": info.get("title", ""),
        "transcript": transcript,
        "length": len(transcript) if transcript else 0,
    })


async def handle_frames(request):
    """
    POST /frames
    Body: {"url": "https://youtube.com/watch?v=...", "count": 10}
    Keyframes extrahieren.
    """
    try:
        body = await request.json()
    except Exception:
        return web.json_response({"error": "Ungueltiger JSON-Body"}, status=400)

    url = body.get("url", "").strip()
    count = min(body.get("count", MAX_FRAMES), MAX_FRAMES)
    video_id = extract_video_id(url)
    if not video_id:
        return web.json_response({"error": "Ungueltige YouTube-URL"}, status=400)

    frames = await extract_keyframes(video_id, count)

    return web.json_response({
        "video_id": video_id,
        "frames_count": len(frames),
        "frames": [{"timestamp": f["timestamp"], "size_kb": f["size_kb"]} for f in frames],
    })


async def handle_chat(request):
    """
    POST /chat
    Body: {"url": "https://youtube.com/watch?v=...", "question": "Was sagt er ueber...?"}
    Follow-up Fragen zum Video.
    """
    try:
        body = await request.json()
    except Exception:
        return web.json_response({"error": "Ungueltiger JSON-Body"}, status=400)

    url = body.get("url", "").strip()
    question = body.get("question", "").strip()
    video_id = extract_video_id(url)

    if not video_id:
        return web.json_response({"error": "Ungueltige YouTube-URL"}, status=400)
    if not question:
        return web.json_response({"error": "Keine Frage gestellt"}, status=400)

    # Zuerst Gemini URL-Direktanalyse versuchen (kann Video sehen+hoeren)
    info = await get_video_info_oembed(video_id)
    if not info:
        info = {}

    answer = await analyze_with_gemini_url(video_id, info, question=question)

    if not answer:
        # Fallback: Aus Cache holen oder neu laden
        cached = analyses_cache.get(video_id)
        if cached:
            transcript = cached["transcript"]
            frames = cached["frames"]
            info = cached["info"]
        else:
            transcript = await get_transcript(video_id, info)
            frames = []

        answer = await analyze_with_gemini(info, transcript, frames, question=question)

    return web.json_response({
        "video_id": video_id,
        "question": question,
        "answer": answer,
    })


# ============================================================
# Hilfsfunktionen
# ============================================================

def _cleanup_dir(path: Path):
    """Loescht temporaeres Verzeichnis."""
    try:
        import shutil
        shutil.rmtree(path, ignore_errors=True)
    except Exception:
        pass


# ============================================================
# CORS Middleware
# ============================================================

@web.middleware
async def cors_middleware(request, handler):
    if request.method == "OPTIONS":
        resp = web.Response()
    else:
        try:
            resp = await handler(request)
        except web.HTTPException as e:
            resp = e

    resp.headers["Access-Control-Allow-Origin"] = "*"
    resp.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    resp.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
    return resp


# ============================================================
# App starten
# ============================================================

def main():
    app = web.Application(middlewares=[cors_middleware], client_max_size=10 * 1024 * 1024)

    app.router.add_get("/health", handle_health)
    app.router.add_post("/analyze", handle_analyze)
    app.router.add_post("/transcript", handle_transcript)
    app.router.add_post("/frames", handle_frames)
    app.router.add_post("/chat", handle_chat)

    log.info(f"Video Analyzer Agent startet auf Port {PORT}")
    log.info(f"LiteLLM: {LITELLM_URL}")
    log.info(f"Gemini: {'konfiguriert' if GEMINI_API_KEY else 'NICHT konfiguriert'}")
    log.info(f"Groq Whisper: {'konfiguriert' if GROQ_API_KEY else 'NICHT konfiguriert'}")

    web.run_app(app, host="0.0.0.0", port=PORT)


if __name__ == "__main__":
    main()
