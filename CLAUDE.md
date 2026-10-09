# microscopy-ai-envs

Pixi-managed conda + pypi environments for the microscopy-AI tools used at
UH-LMU (cellpose 3/4, micro-sam, stardist). The repo also publishes per-env
`conda-lock.yml` files that downstream Docker / Apptainer builds and
non-pixi consumers depend on.

## Environment layout

Every tool ships **two** environments:

| name             | use                                            | extras                                                      |
| ---------------- | ---------------------------------------------- | ----------------------------------------------------------- |
| `<tool>`         | minimal — built into docker/apptainer images   | tool + CUDA only                                            |
| `<tool>-full`    | workstation, interactive use (Jupyter, VSCode) | adds `[feature.jupyter]`: ipykernel, jupyterlab, ipywidgets, matplotlib-base, pandas, scikit-image, scikit-learn |

Each `<tool>` and `<tool>-full` pair **shares a `solve-group`** so they get
identical pins for everything they have in common. This is deliberate: a bug
found in the workstation env must also reproduce in the corresponding
container env. The cost is that the minimal env's lock churns whenever its
`-full` sibling's solve set changes — that's the explicit price of the
consistency guarantee.

When adding a new tool, follow the same pattern. Put interactive-only
packages in `[feature.jupyter]`, not in the tool's own feature, or the
minimal env will silently grow.

## Stardist is pinned to old TensorFlow on purpose

The `stardist` env is fixed at TensorFlow < 2.11, CUDA 11.2, cuDNN 8.1,
Python 3.10, numpy < 2, scipy < 1.14. TensorFlow 2.10 is the **last release
with native Windows GPU support** (2.11+ requires WSL on Windows), and the
stardist users at LMU run on Win 11 native. Do not "modernize" these pins
without first confirming that Win-native GPU is being dropped. Other classic-
TF tools added later (csbdeep, n2v, ...) likely need the same matrix.

This is why stardist uses its own `cuda11` and `tensorflow` features instead
of the shared `cuda` (CUDA 12) feature.

## Pixi + TensorFlow gotchas

Three failure modes recur when working with TF-based envs in this repo:

1. **Pin both `numpy` AND `scipy` on the conda side** — not just numpy. If
   TF < 2.11 is in `pypi-dependencies`, the pip resolver otherwise pulls
   scipy wheels built against NumPy 2.x ABI, surfacing as `_ARRAY_API not
   found` or "All ufuncs must have type numpy.ufunc" at TF import time. The
   working pattern:
   ```toml
   [feature.tensorflow.dependencies]
   numpy = "<2"
   scipy = "<1.14"
   ```

2. **Pixi does not set `LD_LIBRARY_PATH` automatically**, so TF can't find
   env-bundled CUDA libraries (`libcudart.so.11.0` etc.). Set it via an
   activation hook on the CUDA feature:
   ```toml
   [feature.cuda11.activation.env]
   LD_LIBRARY_PATH = "$CONDA_PREFIX/lib:$LD_LIBRARY_PATH"
   XLA_FLAGS = "--xla_gpu_cuda_data_dir=$CONDA_PREFIX"
   ```

3. **A corrupted "Frankenstein" `numpy/` can persist even with correct
   pins.** Symptom: bare `TypeError` (no message) deep in scipy, e.g.
   `scipy/interpolate/_fitpack_impl.py:103` in `array([], dfitpack_int)`.
   `conda list` shows numpy 1.26.4 and pins are correct — but
   `site-packages/numpy/_core/_type_aliases.py` contains the **NumPy 2.x**
   version, which calls `getattr(numpy._core.multiarray, 'signedinteger')`
   (only exists in 2.x). The dist-info's own `RECORD` will list 2.x-only
   paths. **Fix:** `rm -rf .pixi/envs/<env> && pixi install -e <env>`.
   Surgical pip downgrades won't clean up the stray 2.x files.

## Conda-lock CI pipeline

`.github/workflows/update-conda-locks.yml` regenerates per-env
`conda-locks/<env>.conda-lock.yml` files whenever `pixi.lock` changes. The
workflow runs `pixi-to-conda-lock --output conda-locks pixi.lock` (omitting
`--environment` converts all envs in one call), then
`scripts/normalize-conda-locks.py`, and auto-commits the result via
`stefanzweifel/git-auto-commit-action@v5`.

The normalize step is needed because `pixi-to-conda-lock` (<= 0.4.5) copies
pixi.lock v7 platform names (`linux-64-cuda12`, `win-64-cuda12`, formerly
`p1`/`p2`, for the CUDA-12 envs) into the
output instead of `linux-64`/`win-64`, and writes packages in no fixed order.
Without it, conda-lock consumers find no packages for the CUDA envs, and every
run churns thousands of lines.

**Required:** any env with `pypi-dependencies` MUST also list `pip` in its
conda dependencies, or `pixi-to-conda-lock` errors with "PyPI packages are
present but no pip package found". For TF envs this is wired into
`[feature.tensorflow.dependencies]`.

## Local utilities

`scripts/pixi-lock-affects.py` attributes lines in a `pixi.lock` diff to
specific environments — useful when a lock diff looks huge but is actually
scoped to one env.

```bash
scripts/pixi-lock-affects.py                # working tree vs HEAD
scripts/pixi-lock-affects.py <rev>~..<rev>  # what did this commit do
scripts/pixi-lock-affects.py <a>..<b>       # changes between two refs
```

Single-arg form (`<rev>`) means "working tree vs `<rev>`", **not** "what
did this commit do" — use the `..` range for the latter.

`scripts/run_in_env.{sh,ps1}` are thin wrappers that `cd` into a project
repo and run a command under a chosen pixi env from this repo.

## Common operations

```bash
pixi shell -e <env>           # interactive shell
pixi install -e <env>         # solve + install one env
pixi install --all            # solve + install all envs
pixi run -e <env> <cmd>       # one-shot command
```

After adding or modifying an env, prefer `pixi install --all` so the lock
is consistent across all sibling envs in the same solve-group.
