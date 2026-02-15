# FHIR Generation

Converts surgical compliance reports into HL7 FHIR R4 Bundles for EHR integration. Turns AI-generated analysis into healthcare-standard interoperable data.

## Setup

```bash
cd FHIR_Generation
pip install -r requirements.txt
```

Requires ScitePipeline's `.env` for Supabase access when using the `/fhir/from-pipeline` endpoint.

## Usage

### Start the FastAPI server

```bash
uvicorn main:app --port 8001
```

### Convert a local JSON report to FHIR

```bash
python main.py --convert ../ScitePipeline/test_report_output.json
```

## Endpoints

| Endpoint | Description |
|---|---|
| `POST /fhir/generate` | Convert a compliance report payload to FHIR Bundle |
| `POST /fhir/from-pipeline/{run_id}` | Fetch stored report from Supabase → FHIR |
| `POST /fhir/from-video` | End-to-end: video → analysis → FHIR Bundle |

## Output

Generates a FHIR R4 Bundle containing:

- **Procedure** resource — the surgical procedure performed
- **DiagnosticReport** — compliance score and deviation summary
- **Observation** resources — one per detected surgical step with timestamps and confidence
- **DetectedIssue** resources — one per deviation with evidence and citations
- **Patient** and **Practitioner** references

## Key Files

| File | Purpose |
|---|---|
| `main.py` | FastAPI server + CLI |
| `fhir_mapper.py` | Builds FHIR R4 Bundle from compliance data |

