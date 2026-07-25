#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
repository="$(cd -- "${script_dir}/.." && pwd)"

exec uv run --project "${repository}/agent" kintsugi-agent-rehearse \
  --repository "${repository}" "$@"
