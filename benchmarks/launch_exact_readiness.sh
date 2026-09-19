#!/usr/bin/env bash
# Run in a dedicated remote clone, with an already installed Python environment.
# Inventory only: no sbatch, training, dependency install or model download.
set -euo pipefail
if [[ $# -ne 5 ]]; then
  echo "usage: bash benchmarks/launch_exact_readiness.sh SHA ORIGIN_REF CONFIG CONFIG_SHA256 OUTPUT" >&2
  exit 2
fi
expected_sha="$1"
origin_ref="$2"
config="$3"
config_sha="$4"
output="$5"
[[ "$expected_sha" =~ ^[0-9a-f]{40}$ ]] || exit 2
[[ "$config_sha" =~ ^[0-9a-f]{64}$ ]] || exit 2
[[ "$origin_ref" != -* ]] || exit 2
[[ -z "$(git status --porcelain --untracked-files=all)" ]] || {
  echo "Refusing dirty source worktree" >&2; exit 2;
}
# Explicit ref only. Its fetched identity must equal the authorized immutable SHA.
git fetch --no-tags origin "$origin_ref"
[[ "$(git rev-parse FETCH_HEAD)" == "$expected_sha" ]] || {
  echo "Fetched ref differs from authorized SHA; do not run" >&2; exit 2;
}
# Never silently switch the source of a possibly running job.
[[ "$(git rev-parse HEAD)" == "$expected_sha" ]] || {
  echo "Check out the authorized SHA in a dedicated clone, then rerun" >&2; exit 2;
}
python -m benchmarks.readiness_environment \
  --expected-sha "$expected_sha" --config "$config" --config-sha256 "$config_sha" \
  --output "$output"
