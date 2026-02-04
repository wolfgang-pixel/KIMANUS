# Kim TV

KI-gestützter personalisierter Video-Kanal, der relevante YouTube-Inhalte zu einem Thema kuratiert und wie ein TV-Sender abspielt.

## Features

- **KI-Themeneingabe**: Zwei-Fragen-Flow ("Welches Thema?" + "Spezielle Fragen?")
- **YouTube-Suche**: Mit Qualitätsbewertung (Aufrufe/Alter/Kanal)
- **Deutsche Priorisierung**: DACH-Region Kanäle werden bevorzugt
- **Spracherkennung**: Englische Titel werden erkannt und niedriger gerankt
- **LLM Timestamps**: KI berechnet relevante Video-Abschnitte (30-300 Sekunden)
- **Preview-Ansicht**: Zeigt alle Videos vor dem Abspielen
- **Filter-Buttons**: Alle/Deutsch/Englisch
- **YouTube Player**: Mit Timestamp-Sprung (seekTo)
- **Loop-Modus & Auto-Advance**: Nahtloses Abspielen

## Tech Stack

- **Frontend**: React 19 + TypeScript + Tailwind CSS + shadcn/ui
- **Backend**: Express 4 + tRPC 11 + Node.js
- **Datenbank**: MySQL/TiDB mit Drizzle ORM
- **APIs**: YouTube Data API, OpenAI LLM

## Installation

```bash
# Dependencies installieren
npm install

# Umgebungsvariablen konfigurieren
cp .env.example .env
# Dann .env bearbeiten mit deinen API-Keys

# Datenbank-Migrationen ausführen
npm run db:push

# Entwicklungsserver starten
npm run dev
```

## Umgebungsvariablen

```env
PORT=3000
DATABASE_URL=mysql://user:password@localhost:3306/kimtv
YOUTUBE_API_KEY=your_youtube_api_key
OPENAI_API_KEY=your_openai_api_key
```

## Projektstruktur

```
├── client/src/
│   ├── pages/
│   │   ├── Home.tsx        # Landing Page
│   │   └── Watch.tsx       # Kim TV Player
│   ├── components/ui/      # shadcn/ui Komponenten
│   └── lib/
│       ├── trpc.ts         # tRPC Client
│       └── utils.ts        # Hilfsfunktionen
├── server/
│   ├── index.ts            # Express Server
│   ├── routers.ts          # tRPC Router
│   └── _core/
│       ├── llm.ts          # LLM Integration
│       └── dataApi.ts      # YouTube API
└── drizzle/
    └── schema.ts           # DB Schema
```

## Geplante Features

1. **Phase 2**: Deutsche Untertitel für englische Videos
2. **Phase 3**: TTS für Untertitel
3. **Phase 4**: Avatar-Moderator

## Rechtliches

Kim TV nutzt ausschließlich YouTube-Embedding (kein Download), was rechtlich unbedenklich ist - wie mit der Fernbedienung zwischen Kanälen zu zappen.

## Version

v1.6.0
