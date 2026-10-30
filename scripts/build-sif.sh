#!/usr/bin/env bash
# Build an Apptainer .sif from one of the docker/Dockerfile.* pixi images:
# docker build -> docker save -> apptainer build (docker/pixi-env.def).
#
#   scripts/build-sif.sh <env> [version]
#   pixi run sif:build <env> [version]
#
# <env> is cellpose3, cellpose4 or micro-sam. [version] defaults to
# `git describe --tags --always --dirty`; tag the repo first for a clean name.
# Output: $SIF_DIR/uh-lmu_<env>_<version>.sif (SIF_DIR defaults to ./sif).
# The docker tar goes to $TMPDIR and apptainer's scratch to $APPTAINER_TMPDIR
# (or $TMPDIR); both need several GB, so point them at a big disk if /tmp is
# small. DOCKER overrides the docker command (default: "sudo docker").
# An existing image with the same tag is reused unless the version is -dirty
# or REBUILD=1.
set -euo pipefail

usage() { echo "usage: $0 <cellpose3|cellpose4|micro-sam> [version]" >&2; exit 2; }
[[ $# -ge 1 && $# -le 2 ]] || usage
env=$1
case $env in
  cellpose3) dockerfile=docker/Dockerfile.cellpose3 ;;
  cellpose4) dockerfile=docker/Dockerfile.cellpose4 ;;
  micro-sam) dockerfile=docker/Dockerfile.microsam ;;
  *) usage ;;
esac

cd "$(dirname "$0")/.."
version=${2:-$(git describe --tags --always --dirty)}
commit=$(git rev-parse --short HEAD)
sif_dir=${SIF_DIR:-sif}
sif=$sif_dir/uh-lmu_${env}_${version}.sif
image=uh-lmu/$env:$version
read -r -a docker <<< "${DOCKER:-sudo docker}"

# The sudo timestamp can expire during a long build; say why we're prompting.
sudo_reason() {
  if [[ ${docker[0]} == sudo ]] && ! sudo -n true 2>/dev/null; then
    echo ">>> sudo needed for: $*" >&2
  fi
}

# Reuse an existing image unless the version is -dirty (its tag doesn't pin
# the content) or REBUILD=1.
sudo_reason "docker image inspect $image"
if [[ $version != *-dirty && ${REBUILD:-0} != 1 ]] &&
   "${docker[@]}" image inspect "$image" > /dev/null 2>&1; then
  echo "image $image exists, skipping docker build (REBUILD=1 to force)"
else
  sudo_reason "docker build $image"
  "${docker[@]}" build -f "$dockerfile" -t "$image" .
fi

tar=$(mktemp --tmpdir "uh-lmu_${env}_XXXXXX.tar")
trap 'rm -f "$tar"' EXIT
# Redirect (not -o) so the tar is owned by us, not root.
sudo_reason "docker save $image > $tar"
"${docker[@]}" save "$image" > "$tar"

scratch=${APPTAINER_TMPDIR:-${TMPDIR:-/tmp}}
echo "tar $(du -h "$tar" | cut -f1) in $(dirname "$tar"); apptainer scratch" \
  "$scratch has $(df -h --output=avail "$scratch" | tail -1 | tr -d ' ') free" \
  "(needs ~2x the tar)"

mkdir -p "$sif_dir"
# --notest + separate `apptainer test`: an unprivileged build runs %test under
# fakeroot, which fails where user namespaces are restricted (Ubuntu AppArmor).
apptainer build --force --notest \
  --build-arg ARCHIVE="$tar" \
  --build-arg ENV="$env" \
  --build-arg VERSION="$version" \
  --build-arg COMMIT="$commit" \
  "$sif" docker/pixi-env.def
apptainer test "$sif"

echo "built $sif"
