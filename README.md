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
