# GPU image for aarch64 / NVIDIA GH200 (cellpose 4 + micro_sam)

Combined GPU container for CSC **Roihu**'s ARM (aarch64, Grace-Hopper) GPU nodes.
Two build recipes for the same image:

- **`gpu-arm64.def`** — Apptainer definition. Build directly on Roihu (no docker,
  no root). **This is the easy path.**
- **`Dockerfile.gpu-arm64`** — equivalent Dockerfile, for building via
  `docker buildx --platform linux/arm64` or a GitHub Actions arm64 runner and
  pushing to GHCR.

## Why a separate image (not the pixi ones)

The x86 pixi images (`Dockerfile.cellpose4`, `Dockerfile.microsam`) can't run on
Roihu's ARM GPU nodes, and conda-forge can't solve a GPU PyTorch on
linux-aarch64. So this image layers cellpose + micro_sam on NVIDIA's NGC PyTorch
base, which ships a native arm64/SBSA, GH200-tuned CUDA+cuDNN+PyTorch stack.

**Key lesson (validated on rg2102, 2026-07-01):** use a **numpy-2 NGC base**
(`25.10-py3`). On the numpy-1 base (`25.01`) torch's numpy bridge needs numpy<2,
but micro_sam's 2026 dependency closure (scikit-image 0.26, xarray 2026, pandas
3) needs numpy>=2 — irreconcilable, and pip backtracks forever. On a numpy-2 base
everything resolves with **no pins**. `phenix_zproj` stays x86 on the CPU nodes;
only this GPU image is arm64.

## Build on Roihu

A login node has `apptainer` and `--fakeroot` (you don't need to be in
`/etc/subuid` — it falls back to the `fakeroot` command; the
`User not listed in /etc/subuid` / `nodev on /tmp` messages are harmless):

```bash
apptainer build --fakeroot gpu-arm64.sif gpu-arm64.def
```

The build's `%test` prints the cellpose + micro_sam versions (imports only, so it
passes on a CPU-only login node).

## Validate on a GPU node

The real check needs a GH200 and `--nv` (from an interactive/`srun` GPU
allocation, e.g. `--partition=gpumedium --gres=gpu:gh200:1`):

```bash
apptainer exec --nv gpu-arm64.sif python -c "
import numpy as np, torch
from cellpose import models as cpm
from micro_sam.util import get_sam_model
m = cpm.CellposeModel(gpu=True)
masks = m.eval(np.random.randint(0, 255, (256, 256), dtype=np.uint8))[0]
p = get_sam_model(model_type='vit_b')
print('numpy', np.__version__, 'cuda', torch.cuda.is_available())
print('cellpose masks', masks.shape, '| micro_sam on', next(p.model.parameters()).device)
"
```

Expected: `numpy 2.x`, `cuda True`, `cellpose masks (256, 256)`, `micro_sam on
cuda:0`, and **no** "Failed to initialize NumPy" warning. (The `elf` backend and
`urllib3` version warnings are cosmetic.)

## Wiring into the connexin pipeline

Point both GPU-process container selectors at this one `.sif` in the Roihu
Nextflow profile (`withName: 'MICRO_SAM_.*'` and `withName: 'CELLPOSE4'`) — it
replaces the two x86 sifs (`uh-lmu_microsam_lmuv1.0.sif` +
`cellpose_4.0.7_cv1.sif`). That belongs with the Roihu executor/profile work.
