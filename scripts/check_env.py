#!/usr/bin/env python
"""Smoke-test the pixi env this script runs in.

Run inside an env, e.g.:

    pixi run -e stardist check-env
    pixi run -e cellpose4-full python scripts/check_env.py

The tool under test is derived from PIXI_ENVIRONMENT_NAME (set by pixi), or
from the first CLI argument. For `<tool>-full` envs the jupyter extras are
checked too.

GPU handling is controlled by CHECK_GPU:
    auto    (default) require working CUDA if `nvidia-smi` finds a GPU, else skip
    require fail if CUDA does not work
    skip    do not test CUDA at all

Exit code 0 = all checks passed (or skipped), 1 = at least one failure.
"""

import os
import shutil
import subprocess
import sys
import traceback

RESULTS = []  # (status, name, detail)


def check(name):
    def deco(fn):
        try:
            detail = fn()
            RESULTS.append(("SKIP" if detail == "SKIP" else "PASS", name, "" if detail in (None, "SKIP") else detail))
        except Exception as e:
            RESULTS.append(("FAIL", name, f"{type(e).__name__}: {e}"))
            traceback.print_exc()
        return fn
    return deco


def gpu_present():
    smi = shutil.which("nvidia-smi")
    if not smi:
        return False
    try:
        out = subprocess.run([smi, "-L"], capture_output=True, text=True, timeout=30)
    except Exception:
        return False
    return out.returncode == 0 and "GPU" in out.stdout


def want_gpu():
    mode = os.environ.get("CHECK_GPU", "auto").lower()
    if mode == "skip":
        return False
    if mode == "require":
        return True
    return gpu_present()


# ---- per-tool checks -------------------------------------------------------

def check_torch_cuda():
    @check("torch import")
    def _():
        import torch
        return f"torch {torch.__version__}, built for CUDA {torch.version.cuda}"

    if not want_gpu():
        RESULTS.append(("SKIP", "torch CUDA", "no GPU detected (set CHECK_GPU=require to force)"))
        return

    @check("torch CUDA")
    def _():
        import torch
        if not torch.cuda.is_available():
            raise RuntimeError("torch.cuda.is_available() is False")
        dev = torch.device("cuda:0")
        a = torch.randn(512, 512, device=dev)
        b = (a @ a.T).sum().item()  # forces a kernel launch + sync
        if b != b:  # NaN
            raise RuntimeError("matmul returned NaN")
        conv = torch.nn.Conv2d(1, 4, 3).to(dev)  # exercises cuDNN
        conv(torch.randn(1, 1, 64, 64, device=dev)).sum().item()
        return f"{torch.cuda.get_device_name(0)}, cuDNN {torch.backends.cudnn.version()}"


def check_cellpose(major):
    @check("cellpose import")
    def _():
        import cellpose
        from cellpose import models  # noqa: F401
        try:
            from importlib.metadata import version
            v = version("cellpose")
        except Exception:
            v = getattr(cellpose, "__version__", "?")
        if int(v.split(".")[0]) != major:
            raise RuntimeError(f"expected cellpose {major}.x, got {v}")
        return f"cellpose {v}"

    check_torch_cuda()

    if want_gpu():
        @check("cellpose sees GPU")
        def _():
            from cellpose import core
            if not core.use_gpu():
                raise RuntimeError("cellpose.core.use_gpu() is False")


def check_micro_sam():
    @check("micro_sam import")
    def _():
        import micro_sam
        import micro_sam.util  # noqa: F401
        import segment_anything  # noqa: F401
        return f"micro_sam {micro_sam.__version__}"

    @check("napari plugin manifest")
    def _():
        # Catches the npe2/pydantic breakage noted in pixi.toml.
        from npe2 import PluginManager
        pm = PluginManager.instance()
        pm.discover()
        if "micro_sam" not in {m.name for m in pm.iter_manifests()}:
            raise RuntimeError("micro-sam napari plugin not discovered")

    check_torch_cuda()


def check_stardist():
    @check("numpy/scipy pins")
    def _():
        import numpy
        import scipy
        if int(numpy.__version__.split(".")[0]) >= 2:
            raise RuntimeError(f"numpy {numpy.__version__} (need <2 for TF 2.10)")
        # "Frankenstein numpy" detector: 2.x files left behind in a 1.x install.
        from scipy.interpolate import splrep
        splrep(list(range(10)), [x * x for x in range(10)])
        return f"numpy {numpy.__version__}, scipy {scipy.__version__}"

    @check("tensorflow import")
    def _():
        import tensorflow as tf
        return f"tensorflow {tf.__version__}"

    @check("stardist import")
    def _():
        import stardist
        from stardist.models import StarDist2D  # noqa: F401
        return f"stardist {stardist.__version__}"

    if not want_gpu():
        RESULTS.append(("SKIP", "tensorflow GPU", "no GPU detected (set CHECK_GPU=require to force)"))
        return

    @check("tensorflow GPU")
    def _():
        import tensorflow as tf
        gpus = tf.config.list_physical_devices("GPU")
        if not gpus:
            raise RuntimeError("no GPU visible to TensorFlow (LD_LIBRARY_PATH / CUDA 11 libs?)")
        with tf.device("/GPU:0"):
            a = tf.random.normal((512, 512))
            float(tf.reduce_sum(tf.matmul(a, a, transpose_b=True)))
            # exercises cuDNN
            x = tf.random.normal((1, 64, 64, 1))
            float(tf.reduce_sum(tf.keras.layers.Conv2D(4, 3)(x)))
        info = tf.sysconfig.get_build_info()
        return f"{len(gpus)} GPU(s), CUDA {info.get('cuda_version')}, cuDNN {info.get('cudnn_version')}"


def check_jupyter():
    @check("jupyter extras")
    def _():
        import importlib
        mods = ["ipykernel", "jupyterlab", "ipywidgets", "matplotlib", "pandas", "skimage", "sklearn"]
        for m in mods:
            importlib.import_module(m)
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        plt.plot([0, 1])
        plt.close("all")
        return ", ".join(mods)


TOOLS = {
    "cellpose3": lambda: check_cellpose(3),
    "cellpose4": lambda: check_cellpose(4),
    "micro-sam": check_micro_sam,
    "stardist": check_stardist,
}


def main():
    env = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("PIXI_ENVIRONMENT_NAME", "")
    full = env.endswith("-full")
    tool = env[: -len("-full")] if full else env
    if tool not in TOOLS:
        print(f"check_env: no checks defined for env {env!r} (known: {', '.join(TOOLS)})")
        return 1

    print(f"== {env}: python {sys.version.split()[0]} at {sys.executable}")
    TOOLS[tool]()
    if full:
        check_jupyter()

    print()
    for status, name, detail in RESULTS:
        print(f"  [{status}] {name}" + (f" -- {detail}" if detail else ""))
    return 1 if any(s == "FAIL" for s, _, _ in RESULTS) else 0


if __name__ == "__main__":
    sys.exit(main())
