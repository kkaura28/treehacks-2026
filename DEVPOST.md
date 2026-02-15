# VIPER — Video Intelligence for Procedural Evaluation & Review

## Inspiration

Medical errors kill 2.6 to 3 million people a year. Every surgery has a protocol, but compliance is only tracked on 1% of cases. The feedback loop is stuck on a clipboard. We asked: what if the operating room had an eye-level POV flight data recorder that integrated directly into the hospital's records?

## What It Does

VIPER captures surgical video (prototyped with Meta Ray-Ban smart glasses), runs it through comprehensive ML pipelines, and outputs structured, actionable data — all surfaced through a purpose-built analytics platform.

### ML Pipeline

- **SAM 2** for instrument and anatomy segmentation
- **Optical flow** for keypoint tracking across frames — producing per-frame instrument tip trajectories (x, y coordinates at every frame for each tracked tool)
- **Depth models** for spatial context and 3D scene understanding
- **FoundationPose** for 6DoF instrument pose estimation
- **MediaPipe** for surgeon hand joint tracking
- **Gemini 2.5 Pro** for high-level video understanding — mapping raw footage to structured SOP step events with timestamps and confidence scores
- **Stroke-level segmentation** from CV tracking data — velocity profiles, acceleration peaks, and directional changes in the instrument tip trajectories are used to segment each SOP step into individual instrument strokes (each cut, spread, grasp, retract) with sub-second precision

### Reasoning & Evidence Pipeline

- **Scite.ai** citation search surfaces real snippets from surgical literature for each detected deviation
- **DeBERTa NLI** (zero-shot natural language inference) scores every snippet against risk vs. safety hypotheses
- Verdicts (confirmed / mitigated / context-dependent) are evidence-weighted from aggregated NLI scores + citation type counts — not heuristics

### Analytics Platform (Next.js)

The full-stack web application is where all ML outputs converge into a clinical-grade interface:

- **Real-Time OR Command Center** — A live operations dashboard showing every active surgery in the hospital. Each procedure card displays real-time step-by-step progress (dot indicators for each mandatory SOP step), current phase, elapsed time, surgeon identity, and completion percentage. Powered by Supabase Realtime subscriptions on Postgres changes — new events appear instantly without polling.

- **Session Detail View** — Deep-dive into any completed or in-progress procedure across six tabs:

  - **Overview** — Compliance score (radial gauge), steps expected vs. observed, source SOP documents, and top confirmed deviations at a glance.

  - **Timeline** — Synchronized dual-video playback (surgery feed + instrument tip tracking) alongside a phase-grouped event timeline. Click any event to seek both videos to that exact timestamp. Events expand to reveal individual stroke sub-items — each showing precise time ranges, instrument type, stroke classification (cut/spread/grasp/retract/cauterize/suture/irrigate/dissect), and a description. Missing mandatory steps are flagged at the bottom.

  - **Deviations** — Every deviation is displayed as an expandable card with a risk-vs-safety NLI confidence bar. Expanding a deviation shows the full evidence breakdown: citation landscape percentages (supporting vs. contrasting), number of snippets analyzed, and the actual literature quotes with NLI confidence scores and clickable DOI links. Grouped by verdict severity (confirmed → needs review → mitigated).

  - **Procedure Graph** — Interactive ReactFlow visualization of the full SOP as a directed graph. Nodes are color-coded by status (observed = teal, missing/skipped = red, out of order = orange, unobserved = gray). Clicking a node reveals its phase, safety-critical flag, required tools, actors, and preconditions. Conditional vs. sequential edges are visually distinguished.

  - **Skills Assessment** — Maps FoundationPose 6DoF tracking data to the GOALS/OSATS surgical skills framework (the clinical gold standard). Displays a radar chart across five domains (Depth Perception, Bimanual Dexterity, Efficiency, Tissue Handling, Autonomy) plus six kinematic metrics (Path Length, Motion Economy, Smoothness, Idle Time, Movement Count, Tremor Index) — each benchmarked with pass/marginal/fail thresholds.

  - **Report & Export** — Full system data view with patient information, surgery details, pre-operative and post-operative fields. Export options include FHIR R4 transaction bundles (Patient, Encounter, Procedure, Observations, DetectedIssues, Composition), instrument trajectory CSVs, hand kinematics CSVs, and spatial interaction data.

- **Surgeon Profiles** — Per-surgeon pages for longitudinal tracking across multiple cases.

- **Pre-Op Briefings** — Auto-generated briefing pages from the procedure's SOP graph and patient context.

### EHR Integration

- **FHIR R4 Bundle Generation** — Complete HL7 FHIR R4 transaction bundles with SNOMED-coded procedures, LOINC-coded observations, DetectedIssue resources for deviations (with severity mapped from NLI verdicts), Media resources for video references, and a Composition resource serving as the machine-readable operative note. Ready for direct EHR submission.

### Multi-Procedure SOP Library

Structured, validated SOPs for four procedure types — each with nodes, edges, phases, mandatory/optional flags, safety-critical markers, required tools, actors, and preconditions:
- Incision & Drainage of Abscess
- Laparoscopic Cholecystectomy
- Laparoscopic Appendectomy
- Cesarean Section

## How We Built It

**Vision Pipeline:** Video feeds into SAM 2 for segmentation, optical flow for keypoint tracking, depth models for spatial context, FoundationPose for 6DoF instrument pose, and MediaPipe for hand joints.

**Video Understanding:** Gemini 3 Pro watches full procedure videos and maps observed actions to SOP node IDs with timestamps and confidence scores.

**Stroke Segmentation:** The CV pipeline outputs per-frame instrument tip coordinates (blade, forceps, etc.) as time-series data. We compute velocity magnitude, acceleration, and angular change at each frame, then apply peak detection and thresholding to segment continuous motion into discrete strokes — each classified by movement profile (cut = linear high-velocity, spread = diverging bilateral, grasp = converging, etc.) with sub-second timestamp boundaries.

**Reasoning Pipeline:** A comparator detects deviations (missing steps, out-of-order execution, skipped safety checks, unhandled complications) by diffing observed events against the SOP graph. Each deviation triggers claim-specific Scite searches. Every returned citation snippet is scored by DeBERTa zero-shot NLI against risk and safety hypotheses. Aggregated NLI scores + citation type counts produce evidence-weighted verdicts.

**Analytics Platform:** Next.js 14 with Supabase (Postgres + Realtime). ReactFlow for interactive procedure graphs. Recharts for radar/bar visualizations. Tailwind CSS with a custom dark theme designed for clinical environments (low-glare, high-contrast). Real-time OR command center uses Supabase channel subscriptions on `observed_events` and `procedure_runs` tables.

**EHR Integration:** Python FHIR mapper generates complete R4 transaction bundles with SNOMED/LOINC coding, mapping every observed event to an Observation, every deviation to a DetectedIssue, and the full report to a Composition.

**Validation:** We validated the full pipeline on banana surgery videos before medical footage.

## Challenges We Ran Into

- **Surgical video is messy:** Occlusions, lighting shifts, and constant camera movement from first-person smart glasses made consistent segmentation across long procedures extremely difficult.

- **Bridging vision → clinical meaning:** Mapping raw ML outputs to clinically meaningful deviation reports (not just "keypoint at frame 1204" but "you deviated at step 4 — here's the literature on why that matters") required chaining vision models with LLM-based reasoning.

- **NLI calibration for clinical verdicts:** Tuning the threshold where aggregated NLI snippet scores flip a verdict from "context-dependent" to "confirmed" — especially with different thresholds for safety-critical vs. non-critical steps.

- **Real-time state synchronization:** Getting the command center to reflect live procedure progress instantly (new events → updated step dots, phase changes, completion percentages) without polling required careful Supabase Realtime channel design.

- **Stroke-level precision:** Instrument tip trajectories are noisy — optical flow drift, occlusions, and rapid direction changes made it difficult to reliably segment discrete strokes from continuous motion. Tuning velocity thresholds and minimum stroke duration filters to avoid over- or under-segmentation required extensive iteration.

## Accomplishments That We're Proud Of

- **End-to-end pipeline:** From raw first-person video on smart glasses → ML segmentation → structured events → deviation detection → NLI-scored literature adjudication → FHIR R4 bundle — fully automated.

- **Real-time OR command center:** Live multi-OR dashboard with per-step progress tracking, powered by Supabase Realtime — procedures update as they happen.

- **Stroke-level granularity:** Signal processing on CV-derived instrument tip trajectories segments every individual cut, spread, grasp, and retract with sub-second timestamps — enabling biomechanics-grade analysis directly from tracking data.

- **Evidence-weighted adjudication:** Deviations aren't just flagged — each one is adjudicated against real surgical literature using a two-stage Scite → DeBERTa NLI pipeline, producing verdicts with cited evidence and confidence scores.

- **GOALS/OSATS skills mapping:** 6DoF tracking data mapped to the clinical gold standard for surgical skills assessment, giving trainees quantified feedback across five validated domains.

- **FHIR R4 compliance:** Complete, spec-compliant FHIR bundles with SNOMED/LOINC coding — ready for hospital EHR submission without manual transcription.

- **Four validated SOPs:** Structured procedure graphs for abscess I&D, lap chole, lap appendectomy, and c-section — each with safety-critical flags, preconditions, and phase annotations sourced from medical literature.

## What We Learned

The data is valuable far beyond auditing. Hospitals save an estimated $2.5M to $3.6M annually from reduced medical errors, but the bigger play is downstream: robotics companies (Intuitive Surgical, Medtronic, J&J) need this exact data — timestamped, segmented, stroke-level surgical video with structured annotations — to train autonomous systems. Just as dashcams became training data for self-driving cars, surgical video at scale becomes training data for surgical robotics.

Building a clinical-grade analytics platform taught us that the interface matters as much as the ML. Surgeons won't adopt a tool that shows them keypoints — they need verdicts, evidence, literature, and actionable reports in a low-friction UI they can review in 2 minutes between cases.

## What's Next for VIPER

- **More procedure types** — Expanding the SOP library beyond the initial four procedures
- **Tighter deviation-to-citation pipeline** — Making reports immediately actionable with inline literature references
- **Live kinematic exports** — Connecting FoundationPose tracking data to downloadable CSV exports for robotics training datasets
- **Hospital pilot conversations** — Starting integration pilots with hospital systems via FHIR R4 endpoints
- **Surgeon longitudinal analytics** — Compliance trends, recurring deviation patterns, and GOALS score progression across cases for credentialing and CME
- **Long term:** Every surgery generates a structured, auditable, ML-ready record — making surgery safer and feeding the next generation of surgical robotics