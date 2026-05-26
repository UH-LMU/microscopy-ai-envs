#!/usr/bin/env python3
"""Report which pixi environments are affected by changes to pixi.lock.

Usage:
    scripts/pixi-lock-affects.py            # working tree vs HEAD
    scripts/pixi-lock-affects.py <rev>      # working tree vs <rev>
    scripts/pixi-lock-affects.py <a>..<b>   # <a> vs <b>

Lines under the top-level `packages:` section (shared package pool) don't map
to a specific env and are reported as "outside env blocks".
"""
import re
import subprocess
import sys
from collections import defaultdict


def line_to_env_map(text):
    """Map 1-based line number -> env name, for lines inside `environments:` blocks."""
    out = {}
    in_environments = False
    current_env = None
    for i, line in enumerate(text.splitlines(), start=1):
        if re.match(r"^environments:\s*$", line):
            in_environments = True
            current_env = None
            continue
        if in_environments and re.match(r"^[A-Za-z_]", line):
            # a new top-level key (e.g. `packages:`) ends the environments block
            in_environments = False
            current_env = None
            continue
        if in_environments:
            m = re.match(r"^  ([A-Za-z0-9_.-]+):\s*$", line)
            if m:
                current_env = m.group(1)
                continue
            if current_env is not None:
                out[i] = current_env
    return out


def git_show(rev_path):
    return subprocess.check_output(["git", "show", rev_path], text=True)


def resolve_sources(arg):
    """Return (before_text, after_text, diff_args) for the given CLI arg."""
    if arg is None:
        before = git_show("HEAD:pixi.lock")
        with open("pixi.lock") as f:
            after = f.read()
        diff_args = ["HEAD", "--", "pixi.lock"]
    elif ".." in arg:
        a, b = arg.split("..", 1)
        # tolerate three-dot form by stripping a leading dot
        b = b.lstrip(".")
        before = git_show(f"{a}:pixi.lock")
        after = git_show(f"{b}:pixi.lock")
        diff_args = [arg, "--", "pixi.lock"]
    else:
        before = git_show(f"{arg}:pixi.lock")
        with open("pixi.lock") as f:
            after = f.read()
        diff_args = [arg, "--", "pixi.lock"]
    return before, after, diff_args


HUNK_RE = re.compile(r"^@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@")


def walk_diff(diff_text, before_map, after_map):
    affected = defaultdict(lambda: {"added": 0, "removed": 0})
    outside = {"added": 0, "removed": 0}
    old_ln = new_ln = 0
    in_hunk = False
    for line in diff_text.splitlines():
        m = HUNK_RE.match(line)
        if m:
            old_ln = int(m.group(1))
            new_ln = int(m.group(2))
            in_hunk = True
            continue
        if not in_hunk:
            continue
        if not line:
            old_ln += 1
            new_ln += 1
            continue
        tag = line[0]
        if tag == "+":
            env = after_map.get(new_ln)
            (affected[env] if env else outside)["added"] += 1
            new_ln += 1
        elif tag == "-":
            env = before_map.get(old_ln)
            (affected[env] if env else outside)["removed"] += 1
            old_ln += 1
        elif tag == " ":
            old_ln += 1
            new_ln += 1
        elif tag == "\\":
            # "\ No newline at end of file" — no line consumed
            pass
    return affected, outside


def main():
    arg = sys.argv[1] if len(sys.argv) > 1 else None
    try:
        before, after, diff_args = resolve_sources(arg)
    except subprocess.CalledProcessError as e:
        sys.exit(f"git show failed: {e}")

    diff_text = subprocess.check_output(["git", "diff", *diff_args], text=True)
    if not diff_text.strip():
        print("No changes in pixi.lock.")
        return

    affected, outside = walk_diff(diff_text, line_to_env_map(before), line_to_env_map(after))

    if not affected and not (outside["added"] or outside["removed"]):
        print("pixi.lock changed but no diff lines mapped — check the script.")
        return

    name_w = max((len(e) for e in affected), default=10)
    print("Environments affected by pixi.lock changes:")
    for env in sorted(affected):
        s = affected[env]
        print(f"  {env:<{name_w}}  +{s['added']:<4}  -{s['removed']:<4}")
    if outside["added"] or outside["removed"]:
        print(f"  {'(outside env blocks)':<{name_w}}  +{outside['added']:<4}  -{outside['removed']:<4}")


if __name__ == "__main__":
    main()
