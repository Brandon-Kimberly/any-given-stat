#!/bin/bash
# Install pipeline + web dependencies and build the datasets so tests, linters
# and the dev server work in Claude Code on the web sessions.
set -euo pipefail

if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

cd "$CLAUDE_PROJECT_DIR"

if ! command -v uv >/dev/null 2>&1; then
  pip install --quiet uv
fi

(cd pipeline && uv sync --quiet)
(cd web && npm install --no-audit --no-fund --silent)

# Datasets are gitignored; rebuild them (downloads are cached in data/raw).
# Non-fatal: a network hiccup shouldn't block the session.
(cd pipeline && uv run --quiet ags build 2>&1 | tail -n 3) \
  || echo "warning: dataset build failed; run 'cd pipeline && uv run ags build' manually" >&2
