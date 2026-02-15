## Inspiration

Medical errors kill an estimated 2.6–3 million people globally each year. Every surgery follows a protocol, yet compliance is formally tracked in only a small fraction of cases. Feedback is delayed, manual, and often limited to post-operative notes.

We asked: **What if the operating room had a flight data recorder and a live command center?**

## What It Does

VIPER transforms first-person surgical video into structured, clinically actionable intelligence. Using smart-glasses capture, the vision pipeline extracts instrument and anatomy segmentation, tracks instrument tip trajectories across frames, estimates full 6D instrument pose, recovers surgeon hand joint positions, and segments continuous motion into discrete surgical strokes.

This spatial data then feeds into a reasoning layer that maps observed actions to structured surgical protocols, flags missing, out-of-order, or unsafe steps, and cross-references each deviation against published surgical literature.

But VIPER isn't just a backend engine. all of this surfaces in a purpose-built analytics platform. Surgeons and administrators get a real-time OR command center that tracks live procedure progress, an interactive timeline view with synchronized video playback alongside structured step events, and a deviation explorer that presents evidence-backed cards with literature context for every flagged issue. The platform also includes a procedure graph visualization that renders the full protocol as a directed graph color-coded by execution status, a skills assessment dashboard that maps 6DoF motion metrics to validated surgical skill frameworks, and full FHIR/EHR export for standards-compliant reports ready for hospital systems. Beyond post-op review, there's a pre-op voice mode that lets surgeons get briefed about a patient through a conversational agent, surgeon-level analytics for tracking individual performance over time, and a mock command center for monitoring real-time surgeries as they happen.

VIPER doesn't just tell you what happened. It shows you how it happened, whether it followed protocol, and why it matters.

## How We Built It

The system is composed of two tightly integrated pipelines. On the vision side, raw video first passes through SAM 2 for pixel-level segmentation, then optical flow tracks keypoints across frames while depth models provide spatial context. FoundationPose handles full 6D instrument pose estimation, and MediaPipe recovers surgeon hand joints. Together, these produce per-frame trajectories and motion signals, which are then segmented into discrete surgical strokes using velocity profiling, spectral analysis (SPARC smoothness via FFT), and high-frequency tremor decomposition. From there, bimanual coordination is quantified through cross-correlation of hand velocity vectors, and motion economy is derived from path length ratios in both 2D pixel space and 3D world coordinates.

The analytics platform is built with Next.js 14 and Supabase for Postgres-backed storage and real-time subscriptions. The UI uses Tailwind CSS with a custom dark theme designed for clinical environments, ReactFlow for interactive procedure graph visualization, and Recharts for radar and bar chart rendering. Real-time updates in the OR command center are powered by Supabase channel subscriptions on observed events and procedure run tables.

On the reasoning side, Gemini watches the procedure and maps observed actions to protocol steps. A comparator then diffs the observed sequence against the expected SOP graph to detect deviations, and Scite retrieves relevant research snippets to provide evidence-backed context for each flag. The final outputs are structured and exportable as FHIR-compliant surgical reports. We validated the full pipeline on controlled "banana surgery" experiments before moving to medical footage, using them to stress-test segmentation and tracking reliability under controlled conditions.

## Challenges We Ran Into

Surgical video is inherently messy. Frequent occlusions from hands and instruments, rapid lighting changes, constant camera movement from the first-person POV, and long-duration procedures with shifting visual context all make stable tracking extremely difficult. Maintaining consistent segmentation and pose estimation across an entire case required careful orchestration of multiple models working in concert.

A deeper challenge was translating low-level motion data into clinically meaningful feedback. Surgeons don't want keypoints. they want to know whether a safety-critical step was skipped and what the literature says about it. Bridging raw computer vision outputs with protocol-aware reasoning in a way that produces actionable, interpretable reports was essential to making the system useful in practice.

## Accomplishments We're Proud Of

We built a complete end-to-end system that takes raw smart-glasses video and produces FHIR-compliant surgical reports, integrating segmentation, 6DoF pose estimation, and stroke-level motion analysis into a single cohesive pipeline. On the platform side, we designed a real-time OR dashboard with structured protocol tracking and implemented deviation detection backed by live literature retrieval. Most importantly, we created an interface that surgeons can actually review in minutes rather than hours. VIPER turns surgery into structured data. and makes that data usable.

## What We Learned

The immediate value is improved compliance and reduced error. hospitals can save an estimated $2.5M–$3.6M annually. But the long-term opportunity is even larger. Robotics companies need high-quality, timestamped, stroke-level surgical motion data to train autonomous systems. Just as dashcams became foundational training data for self-driving cars, structured surgical video at scale becomes the training substrate for surgical robotics. VIPER generates that data at scale.

## What's Next for VIPER

We're expanding to more procedure types and tightening the deviation-to-citation pipeline to make reports even more actionable. From there, we plan to launch pilot integrations with hospital systems and build out longitudinal surgeon performance analytics for credentialing and training feedback. Long term, every surgery generates a structured, auditable, ML-ready record. improving patient safety today and enabling surgical autonomy tomorrow.
