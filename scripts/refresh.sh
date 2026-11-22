#!/usr/bin/env bash
# Weekly refresh: pull the last couple of months from Arctic Shift (no key),
# re-rank, rebuild. Needs data/ to persist between runs (mini/box, or the
# Actions cache in .github/workflows/refresh.yml). Optional env:
#   YOUTUBE_API_KEY                 durations/dates for new videos (else oEmbed)
#   TCGTUBE_LLM_PROVIDER + key      LLM stance labels (else heuristic)
set -euo pipefail
cd "$(dirname "$0")/.."
PY=${PY:-.venv/bin/python}
[ -x "$PY" ] || { python3 -m venv .venv && .venv/bin/pip install -q -r requirements.txt; }
[ -f data/legacy.json ] || $PY pipeline/import_legacy.py || true
$PY pipeline/mine_arctic.py --refresh-recent 2
$PY pipeline/aggregate.py
$PY pipeline/build_site.py
echo "refresh done: $(date -u +%FT%TZ). Review corpus/ diff, then deploy is a human decision."
