# KIMANUS Agenten-Architektur (Stand: 24.03.2026)

## Grundprinzip: Concierge + Spezialisten

KIM und KAI sind **Concierges** - sie sind die erste Anlaufstelle fuer den Nutzer.
Sie kennen dich, haben eine Seele, ein Gedaechtnis und eine Persoenlichkeit.
Fuer Spezialaufgaben delegieren sie an **Scouts und Agenten**.

## KIM/KAI Kern-Faehigkeiten (wie OpenClaw, aber besser)

### Seele & Persoenlichkeit
- 8 Ewige Grundsaetze von KIMANUS
- Goldene Regel + Demut
- KIM: warmherzig, einfuehlsam, wie eine gute Freundin
- KAI: professionell, praezise, wie ein erstklassiger Berater

### Gedaechtnis (Memory-System)
- Fakten ueber den Nutzer (Name, Wohnort, Familie)
- Vorlieben und Einstellungen
- Wichtige Termine und Daten
- Letzte Gespraechsthemen
- Sync zwischen App und Server (n8n staticData)
- Bearbeitbar vom Nutzer (Memory View)

### Kontext & Intelligenz
- Chat-Historie (letzte 20 Nachrichten)
- Wechselbare LLMs (Groq, DeepSeek, Gemini, Claude, GPT-4o, Qwen lokal)
- Memory hat IMMER Vorrang ueber Chat-Verlauf
- Kompakte Antworten (2-4 Saetze), nicht schwafeln

### Stimme & Kommunikation
- ElevenLabs Custom Voices (wechselbar)
- Grok TTS + OpenAI TTS als Fallback
- Vorlesen jeder Nachricht (Hoeren-Button)
- Spracheingabe (Web Speech API)
- Spaeter: Telefon, WhatsApp, E-Mail

## Concierge-Delegation

KIM/KAI erkennen wann ein Spezialist gebraucht wird:

### Was KIM/KAI SELBST machen:
- Gespraech, Smalltalk, Zuhören
- Einfache Fragen (Allgemeinwissen des LLM)
- Rat geben, Meinung, Humor
- Texte formulieren, Ideen brainstormen
- Memory verwalten (sich Dinge merken)

### Was an SCOUTS delegiert wird:
- Web-Recherche → Web-Scout (SearXNG)
- YouTube-Suche → YT Scout (YouTube API + Kapitel)
- iPhone-Hilfe → iPhone Scout (Gemini Vision)
- Dokumente → Dokument-Agent
- E-Mails senden → E-Mail-Agent (SMTP)
- WhatsApp → WhatsApp-Agent (Matrix Bridge)
- Kalkulationen → Kalkulations-Agent
- Terminplanung → Kalender-Agent

### Delegation klingt menschlich:
"Gute Frage! Dafuer hab ich meinen YouTube-Scout - der sucht das gerade..."
"Moment, ich frage kurz meinen Web-Recherche-Spezialisten..."
"Dafuer schicke ich dir gleich was per WhatsApp rueber."

## Technische Umsetzung (n8n)

1. KIM/KAI Haupt-Workflows empfangen die Nachricht
2. Setup-Node baut System-Prompt mit Memory + Persoenlichkeit
3. LLM entscheidet ob Delegation noetig (Tool-Calling oder Keywords)
4. Sub-Workflow wird aufgerufen (n8n Execute Workflow Node)
5. Ergebnis kommt zurueck → KIM/KAI formulieren Antwort
6. Memory-Update extrahieren und speichern

## Naechste Schritte
1. Web-Recherche Scout bauen (SearXNG + n8n)
2. YT Scout ankoppeln (existiert schon in der App)
3. Tool-Calling im LLM aktivieren (Funktionsaufrufe)
4. WhatsApp-Kanal einrichten
5. E-Mail-Agent bauen
