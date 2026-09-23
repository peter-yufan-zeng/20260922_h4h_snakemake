#!/bin/bash
#SBATCH --job-name=mouse_rnaseq_controller
#SBATCH --partition=all
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=4G
#SBATCH --time=4-00:00:00
#SBATCH --output=rnaseq-controller-%j.out
set -euo pipefail
# Submit with an absolute --chdir pointing to this checkout on /cluster/projects.
: "${SLURM_JOB_ID:?Run with sbatch or from a compute-node allocation}"
if [[ ! -f run_rnaseq_mouse.snk ]]; then
    echo 'Use sbatch --chdir=/cluster/projects/GROUP/PROJECT scripts/run_h4h.sh' >&2
    exit 1
fi
# Load the site-provided workflow runner and Python.
if ! type module >/dev/null 2>&1; then
    source "${H4H_MODULES_INIT:-/etc/profile.d/modules.sh}"
fi
module load "${H4H_PYTHON_MODULE:-python3/3.10.9}"
module load "${H4H_SNAKEMAKE_MODULE:-snakemake/7.3.8}"
if [[ "$(snakemake --version)" != 7.3.8 ]]; then
    echo 'This profile requires Snakemake 7.3.8; check module load snakemake/7.3.8.' >&2
    exit 1
fi
# Keep Snakemake's own temporary files on shared project storage too.
mkdir -p work/tmp work/cache
export XDG_CACHE_HOME="$PWD/work/cache"
export TMPDIR
TMPDIR=$(mktemp -d "$PWD/work/tmp/controller.XXXXXXXX")
export TMP="$TMPDIR" TEMP="$TMPDIR"
trap 'rm -rf -- "$TMPDIR"' EXIT
CONFIG="${H4H_CONFIG:-config/h4h.yaml}"
python scripts/preflight.py --config "$CONFIG"
snakemake --snakefile run_rnaseq_mouse.snk --profile profiles/h4h --configfile "$CONFIG" "$@"
