# ScitePipeline

Core analysis pipeline. Takes surgical video → Gemini video interpretation → SOP graph comparison → scite.ai evidence adjudication → compliance report.

## Setup

```bash
cd ScitePipeline
pip install -r requirements.txt
```

Create `.env`:

```
SUPABASE_URL=<your-supabase-url>
SUPABASE_KEY=<your-supabase-service-key>
GEMINI_API_KEY=<your-gemini-api-key>
SCITE_API_KEY=<your-scite-api-key>
```

## Usage

### Analyze a video end-to-end

```bash
python test_full_pipeline.py --video surgery_video_3.mp4 --procedure incision_drainage_abscess --model gemini-3-pro-preview
```

### Run with mock events (no video needed)

```bash
python test_full_pipeline.py --mock --procedure laparoscopic_cholecystectomy
```

### Start the FastAPI server

```bash
python main.py
```

Runs at `http://localhost:8000`. Endpoints:

| Endpoint | Description |
|---|---|
| `POST /mock` | Generate mock procedure run with deliberate deviations |
| `POST /analyze/{run_id}` | Run full pipeline on a procedure run |
| `GET /report/{run_id}` | Retrieve stored compliance report |
| `GET /report/{run_id}/text` | Get human-readable report text |

## Pipeline Steps

1. **Video Interpretation** (`video_interpreter.py`) — Gemini watches the surgery video and maps observed actions to SOP node IDs with timestamps and confidence scores
2. **Graph Comparison** (`comparator.py`) — Compares observed events against the gold-standard SOP graph. Detects missing steps, out-of-order steps, and skipped safety-critical steps
3. **Evidence Adjudication** (`adjudicator.py`) — Queries scite.ai for relevant citations, then runs DeBERTa NLI to score whether each deviation is clinically significant
4. **Report Generation** (`report.py`) — Produces a structured compliance report with scores, confirmed/mitigated/review deviations, and evidence summaries

## Key Files

| File | Purpose |
|---|---|
| `video_interpreter.py` | Gemini video → structured events |
| `comparator.py` | SOP graph comparison |
| `adjudicator.py` | scite.ai + NLI evidence scoring |
| `report.py` | Compliance report generation |
| `models.py` | Pydantic data models |
| `config.py` | Settings + Supabase client |

