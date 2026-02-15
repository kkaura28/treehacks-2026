# Analytics UI

Next.js dashboard for surgical compliance analysis. Displays procedure sessions, deviation reports, procedure graphs, skills assessments, and pre-op voice briefings.

## Setup

```bash
cd Analytics_UI
npm install
```

Create `.env`:

```
NEXT_PUBLIC_SUPABASE_URL=<your-supabase-url>
NEXT_PUBLIC_SUPABASE_ANON_KEY=<your-supabase-anon-key>
GEMINI_API_KEY=<your-gemini-api-key>
```

Run:

```bash
npx next dev
```

Opens at `http://localhost:3000`.

## Pages

| Route | Description |
|---|---|
| `/` | Procedure overview with compliance stats |
| `/procedures/[id]` | Session list for a procedure type |
| `/sessions/[id]` | Full session detail — overview, video timeline, procedure graph, deviation analysis, skills, data export |
| `/briefings` | Pre-op patient briefing list |
| `/briefings/[id]` | Voice-powered AI briefing for a patient |
| `/api/chat` | Server-side Gemini API route for voice briefing |

## Tech

- **Next.js 16** + React 19
- **Supabase** for data
- **Gemini 2.5 Flash** for pre-op briefing chat
- **Web Speech API** for voice input/output
- **React Flow** for procedure graph visualization
- **Recharts** for skills radar charts
- **Tailwind CSS 4** for styling

