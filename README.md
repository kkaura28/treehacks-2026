# treehacks-2026

VIPER is an AI platform that watches first-person surgical video (via smart glasses) and extracts detailed spatial data like instrument tracking, pose estimation, hand positions, and surgical stroke segmentation, then reasons over it to map actions to protocols and flag deviations backed by literature. Everything surfaces through an analytics platform with live OR tracking, interactive timelines, deviation cards, protocol graphs, skills dashboards, EHR export, and a pre-op voice briefing mode, so it's essentially an AI system that watches surgery happen and tells you, in real time and after the fact, what went right, what didn't, and why.

## Setup (including FoundationPose)

This repo uses [FoundationPose](https://github.com/NVlabs/FoundationPose) (NVlabs 6D pose estimation) as a **Git submodule**.

**First-time clone (get everything in one step):**
```bash
git clone --recurse-submodules https://github.com/YOUR_USERNAME/treehacks-2026.git
```

**If you already cloned without submodules:**
```bash
git submodule update --init --recursive
```

Then follow FoundationPose’s own setup (Docker or conda, weights, etc.) inside `FoundationPose/` — see `FoundationPose/readme.md`.

**RTX 5090 / Blackwell (sm_120):** Use the `fp5090` conda env (Python 3.11 + PyTorch nightly cu128). From repo root: `conda activate fp5090`, then `cd FoundationPose && python run_demo.py`. The demo uses a Python fallback for rotation clustering by default to avoid a C++ extension crash on this setup.
