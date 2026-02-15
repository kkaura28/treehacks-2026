## Inspiration

Medical errors kill an estimated 2.6–3 million people globally each year. Every surgery follows a protocol, yet compliance is formally tracked in only a small fraction of cases. Feedback is delayed, manual, and often limited to post-operative notes.

We asked:

**What if the operating room had a flight data recorder — and a live command center?**

## What It Does

VIPER transforms first-person surgical video into structured, clinically actionable intelligence.

Using smart-glasses capture, VIPER extracts:

- Instrument and anatomy segmentation
- Instrument tip trajectories
- 6D instrument pose
- Surgeon hand joint tracking
- Stroke-level motion segmentation

On top of this spatial data, a reasoning pipeline:

- Maps actions to structured surgical protocols
- Detects missing, out-of-order, or unsafe steps
- Cross-references flagged deviations against surgical literature

But VIPER isn't just a backend engine.

All outputs surface in a purpose-built analytics platform featuring:

- **Real-Time OR Command Center** — live procedure progress tracking
- **Interactive Timeline View** — synchronized video + structured step events
- **Deviation Explorer** — evidence-backed deviation cards with literature context
- **Procedure Graph Visualization** — protocol displayed as a directed graph, color-coded by execution status
- **Skills Assessment Dashboard** — 6DoF motion metrics mapped to surgical skill frameworks
- **FHIR/EHR Export** — structured, standards-compliant reports ready for hospital systems

VIPER doesn't just tell you what happened.
It shows you *how* it happened, whether it followed protocol, and why it matters.

## How We Built It

### Vision Pipeline

Video feeds into:

- **SAM 2** for segmentation
- **Optical flow** for keypoint tracking
- **Depth models** for spatial context
- **FoundationPose** for 6D pose estimation
- **MediaPipe** for hand joint tracking

This produces per-frame trajectories and motion signals, which are segmented into discrete surgical strokes using velocity profiling, spectral analysis (SPARC smoothness via FFT), and high-frequency tremor decomposition. Bimanual coordination is quantified through cross-correlation of hand velocity vectors, and motion economy is derived from path length ratios in both 2D pixel space and 3D world coordinates.

### Reasoning Pipeline

- **Gemini** maps observed actions to protocol steps
- A **comparator** detects deviations
- **Scite** retrieves relevant research snippets

Outputs are structured and exportable as FHIR-compliant surgical reports.

We validated the pipeline on controlled "banana surgery" tests before medical footage to stress-test segmentation and tracking reliability.

## Challenges We Ran Into

Surgical video is inherently messy: occlusions, lighting shifts, rapid POV movement, and long-duration procedures.

Maintaining stable segmentation and pose estimation over time required careful model orchestration.

A deeper challenge was translating low-level motion data into clinically meaningful feedback. Surgeons don't want keypoints. They want to know whether a safety-critical step was skipped. Bridging computer vision outputs with protocol-aware reasoning was essential.

## Accomplishments We're Proud Of

- Built a complete end-to-end system from smart-glasses video to FHIR-compliant surgical reports
- Integrated segmentation, 6DoF pose estimation, and stroke-level motion analysis
- Designed a real-time OR dashboard with structured protocol tracking
- Implemented deviation detection backed by live literature retrieval
- Created an interface that surgeons can review in minutes, not hours

VIPER turns surgery into structured data — and makes that data usable.

## What We Learned

The immediate value is improved compliance and reduced error. Hospitals can save an estimated $2.5M–$3.6M annually.

The long-term opportunity is even larger. Robotics companies need high-quality, timestamped, stroke-level surgical motion data to train autonomous systems. Just as dashcams became training data for self-driving cars, structured surgical video becomes training data for surgical robotics.

**VIPER generates that data at scale.**

## What's Next for VIPER

- Expanding to more procedure types
- Tightening the deviation-to-citation pipeline
- Launching pilot integrations with hospital systems
- Building longitudinal surgeon performance analytics

Long term, every surgery generates a structured, auditable, ML-ready record — improving patient safety today and enabling surgical autonomy tomorrow.
