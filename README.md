# treehacks-2026

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
