#!/usr/bin/env python3
"""Replace pixi platform aliases in conda-lock files with real platform names.

Usage:
    scripts/fix-conda-lock-platforms.py <pixi.lock> <conda-lock.yml>...

pixi.lock format v7 gives platforms with extra virtual packages (e.g. envs with
`[feature.cuda.system-requirements] cuda = "12"`) alias names like `p1`, with
the real platform in `subdir`. pixi-to-conda-lock (<= 0.4.5) copies the alias
into its output, so conda-lock consumers asking for `linux-64` find nothing.
This rewrites `p1` -> `linux-64` etc. in place; files without aliases are left
untouched.
"""
import re
import sys

import yaml


def alias_map(pixi_lock_path):
    """Map platform alias -> subdir, from the top-level `platforms:` list of a v7 pixi.lock."""
    with open(pixi_lock_path) as f:
        data = yaml.safe_load(f)
    platforms = data.get("platforms")
    if not isinstance(platforms, list):
        return {}  # pre-v7 lock: no aliases
    return {p["name"]: p["subdir"] for p in platforms if "subdir" in p and p["subdir"] != p["name"]}


def fix_file(path, aliases):
    with open(path) as f:
        text = f.read()
    names = "|".join(re.escape(a) for a in aliases)
    # The three places a platform name appears in conda-lock output:
    #   metadata.content_hash keys ("    p1: ..."), metadata.platforms items ("  - p1"),
    #   and each package's "  platform: p1".
    pattern = re.compile(rf"^(\s*platform: |\s*- |\s*)({names})(:\s|\s*$)", re.MULTILINE)
    new_text, n = pattern.subn(lambda m: m.group(1) + aliases[m.group(2)] + m.group(3), text)
    if n:
        with open(path, "w") as f:
            f.write(new_text)
    return n


def main():
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    aliases = alias_map(sys.argv[1])
    if not aliases:
        print("no platform aliases in pixi.lock, nothing to do")
        return
    print("aliases:", ", ".join(f"{a} -> {s}" for a, s in sorted(aliases.items())))
    for path in sys.argv[2:]:
        print(f"{path}: {fix_file(path, aliases)} replacements")


if __name__ == "__main__":
    main()
