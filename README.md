
# Microscopy AI Environments (Pixi)

This repo hosts **reusable, pre-solved environments** for heavy tools:
- **cellpose3** (Cellpose < 4.0; Python 3.12)
- **cellpose4** (Cellpose ≥ 4.0 with SAM; Python 3.12)
- **micro-sam** (micro-SAM + napari; Python 3.12)
- **stardist** (StarDist + TensorFlow 2.10; Python 3.10)

Each also comes as `<tool>-full` with Jupyter and analysis extras. All but
stardist include [bioio](https://github.com/bioio-devs/bioio) readers for CZI,
LIF, OME-TIFF, OME-Zarr and plain TIFF, e.g.
`BioImage("img.czi").get_image_dask_data("ZYX")`.

## Usage (local workstation)

```bash
# clone once to a fixed path (example on Windows)
# C:\hyapp\pixi\microscopy-ai-envs

pixi install -e cellpose3    # solve once
pixi install -e cellpose4
pixi install -e micro-sam

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

## Building Apptainer .sif images
The images produced by the Dockerfiles are too large to build on GitHub Actions,
so .sif files are built locally:

```bash
pixi run sif:build cellpose4          # or sif:build:cp3 / sif:build:cp4 / sif:build:microsam
# -> sif/uh-lmu_cellpose4_<YYYYMMDD>_<commit>.sif (-dirty if uncommitted changes)
```

`scripts/build-sif.sh` does `sudo docker build` -> `docker save` -> `apptainer
build` with `docker/pixi-env.def` (labels, help, and a `%test` that runs
`scripts/check_env.py`). The docker tar and apptainer scratch need several GB:
set `TMPDIR` / `APPTAINER_TMPDIR` to a big disk if needed, `SIF_DIR` to change
the output dir. Test on a GPU host with
`CHECK_GPU=require apptainer test --nv sif/<name>.sif`.

## Helper scripts
- `scripts/run_in_env.ps1` / `scripts/run_in_env.sh` run a command in a selected env for a **project path**.
- `scripts/fix-env-permissions.ps1` (`pixi run fix-perms [env ...]`, Windows): after installing, makes every file in the envs inherit the env folder's permissions, so users other than the installer can run them. Same as Explorer's "Replace all child object permission entries…". Re-run after each install/update.
