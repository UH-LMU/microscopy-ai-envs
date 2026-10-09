#!/usr/bin/env python
"""Run scripts/check_env.py in every env defined in pixi.toml.

    pixi run test                    # all envs (installs them if needed)
    pixi run test stardist micro-sam # only these envs
    python scripts/test_envs.py --frozen

Pass-through env var CHECK_GPU=auto|require|skip controls CUDA checks (see
check_env.py). Uses only the stdlib, so any Python 3.8+ works.
"""

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
CHECK = Path("scripts") / "check_env.py"


def pixi_envs():
    out = subprocess.run(
        ["pixi", "info", "--json"], cwd=REPO, capture_output=True, text=True, check=True
    ).stdout
    return [e["name"] for e in json.loads(out)["environments_info"] if e["name"] != "default"]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("envs", nargs="*", help="envs to test (default: all)")
    ap.add_argument("--frozen", action="store_true", help="pass --frozen to pixi run (don't re-solve)")
    args = ap.parse_args()

    available = pixi_envs()
    envs = args.envs or available
    unknown = [e for e in envs if e not in available]
    if unknown:
        sys.exit(f"unknown env(s): {', '.join(unknown)} (available: {', '.join(available)})")

    # Don't leak the outer pixi activation into the per-env runs.
    child_env = {k: v for k, v in os.environ.items() if not k.startswith(("PIXI_", "CONDA_"))}

    results = []
    for env in envs:
        print(f"\n{'=' * 70}\n>>> {env}\n{'=' * 70}", flush=True)
        cmd = ["pixi", "run", "-e", env]
        if args.frozen:
            cmd.append("--frozen")
        cmd += ["python", str(CHECK), env]
        t0 = time.time()
        rc = subprocess.run(cmd, cwd=REPO, env=child_env).returncode
        results.append((env, rc, time.time() - t0))

    print(f"\n{'=' * 70}\nSummary\n{'=' * 70}")
    for env, rc, dt in results:
        print(f"  {'PASS' if rc == 0 else 'FAIL'}  {env:<20} ({dt:.0f}s)")
    failed = [env for env, rc, _ in results if rc != 0]
    if failed:
        print(f"\n{len(failed)} env(s) failed: {', '.join(failed)}")
        return 1
    print(f"\nall {len(results)} env(s) passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
