#!/usr/bin/env bash
#SBATCH --job-name=cp2c-mvp-smoke
#SBATCH --account=gov115094
#SBATCH --partition=dev
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --mem=64G
#SBATCH --gres=gpu:H200:1
#SBATCH --time=00:30:00
#SBATCH --output=/work/austinhpc25/nano4_cp2_mvp_candidate_v1/runtime_smoke/slurm-%j.out

set -euo pipefail
repo=/work/austinhpc25/MeiChuHackathon26
root=/work/austinhpc25/nano4_cp2_mvp_candidate_v1
expected=3d161dd86c941e4a72ac4053ac795b0c3f7e5cb0
test "$(git -C "$repo" rev-parse HEAD)" = "$expected"
test -z "$(git -C "$repo" status --porcelain=v1 --untracked-files=all)"
export PATH=/work/austinhpc25/nano4_cp2_readiness_3d161dd/py312/bin:$PATH
export PYTHONPATH="$repo"
export CUBLAS_WORKSPACE_CONFIG=:4096:8
export OMP_NUM_THREADS="$SLURM_CPUS_PER_TASK"
python -u "$root/runtime_smoke/build_smoke_fixture.py" --output-dir "$root/runtime_smoke"
python -u "$root/runtime_smoke/smoke_validation.py" --root "$root"
