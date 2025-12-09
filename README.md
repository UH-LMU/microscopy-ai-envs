
# Microscopy AI Environments (Pixi)

This repo hosts **reusable, pre-solved environments** for heavy tools:
- **cellpose3** (Cellpose < 4.0; Python 3.10)
- **cellpose4** (Cellpose ≥ 4.0 with SAM; Python 3.11)
- **microsam** (micro-SAM + napari; Python 3.11)

## Usage (local workstation)

```bash
# clone once to a fixed path (example on Windows)
# C:\hyapp\pixi\microscopy-ai-envs

pixi install -e cellpose3    # solve once
pixi install -e cellpose4
pixi install -e microsam

# optional: create/update a consolidated lock file after solving
# (pixi writes/updates pixi.lock automatically during install)
```

Point project repos at this location using tasks like:
```bash
# from a project repo
pixi run ext:train:cp4
```

## Containers (HPC)
Dockerfiles under `docker/` show how to build images that embed these envs. Publish tags like:
- `ghcr.io/uh-lmu/cellpose3:<date>`
- `ghcr.io/uh-lmu/cellpose4:<date>`
- `ghcr.io/uh-lmu/microsam:<date>`

## Helper scripts
- `scripts/run_in_env.ps1` / `scripts/run_in_env.sh` run a command in a selected env for a **project path**.
