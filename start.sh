#!/usr/bin/env sh
# Any Given Stat: build what's missing, then serve the site at http://localhost:4173.
# Extra args go to `ags up` (e.g. ./start.sh --port 5000 --no-open).
set -e
cd "$(dirname "$0")"
if ! command -v uv >/dev/null 2>&1; then
  echo "uv is not installed: see https://docs.astral.sh/uv/" >&2
  exit 1
fi
exec uv run --project pipeline ags up "$@"
