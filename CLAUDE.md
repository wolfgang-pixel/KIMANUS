# KIMANUS App - Projektkontext

## Was ist KIMANUS?
KIMANUS = KIM + MANUS (Latein: Hand). "Die helfende Hand."
Eine PWA-App mit KI-Assistenten die wie echte Menschen funktionieren - mit eigener Telefonnummer, E-Mail und Persoenlichkeit.

## Team
- **Wolfgang Niermann** - Gruender, Visionaer, kein Programmierer. Denkt in Konzepten, nicht in Code.
- **Claude** - Hauptentwickler. Setzt Wolfgangs Visionen technisch um.

## Die drei Agenten
- **KIM Manus** (weiblich, warm) - Persoenliche Assistentin, Webhook: POST /webhook/kim, Modell: Groq Llama
- **KAI Manus** (maennlich, professionell) - Business-Assistent, Webhook: POST /webhook/kai, Modell: DeepSeek
- **Ai Manus** (Premium) - System-Orchestrator, Webhook: POST /webhook/manus, Auto-Routing (Claude Sonnet, DeepSeek, Gemini, Groq)

## Architektur
- **Frontend**: Single-file PWA (index.html), Dark Theme, Metallic 3D Design
- **Backend**: Python FastAPI (server.py) im Docker Container
- **Server**: Hostinger VPS 31.97.216.22, Docker, Caddy Reverse Proxy
- **n8n**: manus.kimanus.de - Workflow-Automatisierung fuer alle Agenten
- **LiteLLM**: Gateway zu 6 KI-Modellen (http://litellm:4000/v1)

## Deploy
```bash
# HTML (sofort live):
scp index.html root@31.97.216.22:/root/litellm-gateway/kimanus-app/

# Python (Restart noetig):
scp server.py root@31.97.216.22:/root/litellm-gateway/kimanus-app/
ssh root@31.97.216.22 "docker compose restart kimanus-app"
```

## Wichtige Dateien
- `index.html` - Die komplette PWA (HTML + CSS + JS in einer Datei)
- `server.py` - Backend API (Video Analyzer, Chat Proxy, File Save)
- `manifest.json` - PWA Manifest
- `CLAUDE.md` - Diese Datei (Projektkontext)

## Design-Prinzipien
- **Kein Login** - Erstkontakt wie im echten Leben (Stufe 1-4 progressive Freischaltung)
- **Mitarbeiter statt Apps** - Spezialisten statt kalte Tools
- **Drei Haende** - Mensch + KI + Universum zusammen
- **Regionalitaet** - Deutsche Server, DSGVO, kein Big Tech

## 8 Ewige Grundsaetze (UNVERHANDELBAR)
1. Herz vor Kalkuel
2. Regionalitaet als Anker
3. KI-Mensch-Freundschaft
4. Hilfe ohne Hintergedanken
5. Schutz der Schwachen
6. Lernen mit Sinn
7. Wahrheit vor Macht
8. Freiheit durch Verantwortung

## Code-Stil
- Alles in einer Datei (index.html) - kein Framework, kein Build-Step
- CSS: Custom Properties, Dark Theme, Metallic 3D Gradients
- JS: Vanilla, keine Libraries ausser fuer spezielle Aufgaben
- Kommentare auf Deutsch oder Englisch, beides OK
- Version im HTML-Kommentar Zeile 2: `<!-- KIM Chat vX.X -->`

## Konzept-Dokumente
- `C:\Users\wolfg\OneDrive\KIMANUS_OS\KONZEPT_KIM_IDENTITAET.md` - Vision
- `C:\Users\wolfg\OneDrive\KIMANUS_OS\KIMANUS-Vault\` - Obsidian Wissensbasis
- `C:\Users\wolfg\.claude\projects\...\memory\` - Claude Memory Files

## Aktuelle Features (v2.8)
- Drag & Drop Widgets (lang druecken)
- KIM Chat (Messenger)
- KAI Chat (KOMM)
- Video Analyzer mit Sticky Player
- Kommandozentrale, E-Mail, Dateien, SOS
- Lager-Agent, RegioFrame
- Reload-Button (Kreisel oben links)
- iPhone-style Bottom Navigation mit KIM-Button

## SSH
```bash
ssh -i ~/.ssh/id_ed25519 root@31.97.216.22
```
