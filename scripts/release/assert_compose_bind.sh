#!/usr/bin/env bash
# Canonical Compose bind assertions. Uses ONLY docker-compose.yml (no local override).
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT_DIR"

COMPOSE_BIN=(docker compose -f docker-compose.yml)

if ! command -v docker >/dev/null 2>&1; then
  echo "ERROR: docker not available"
  exit 1
fi

_extract_published_ports() {
  # Prints host:container port mappings for transcriptx-web from `compose config` JSON.
  local json="$1"
  python3 - "$json" <<'PY'
import json, sys
data = json.loads(sys.argv[1])
svc = data.get("services", {}).get("transcriptx-web", {})
ports = svc.get("ports") or []
out = []
for p in ports:
    if isinstance(p, dict):
        published = p.get("published")
        target = p.get("target")
        host_ip = p.get("host_ip") or ""
        if published is None or target is None:
            continue
        out.append(f"{host_ip}:{published}:{target}" if host_ip else f"{published}:{target}")
    else:
        out.append(str(p))
for line in sorted(out):
    print(line)
PY
}

_assert_ports() {
  local label="$1"
  shift
  local expected=("$@")
  local json
  json="$("${COMPOSE_BIN[@]}" config --format json)"
  local actual
  actual="$(_extract_published_ports "$json")"
  local -a actual_arr=()
  while IFS= read -r line; do
    [[ -n "$line" ]] && actual_arr+=("$line")
  done <<< "$actual"

  if [[ ${#actual_arr[@]} -ne ${#expected[@]} ]]; then
    echo "ERROR [$label]: expected ${#expected[@]} published port(s), got ${#actual_arr[@]}"
    echo "  expected: ${expected[*]}"
    echo "  actual:   ${actual_arr[*]:-<none>}"
    exit 1
  fi
  local i
  for i in "${!expected[@]}"; do
    if [[ "${actual_arr[$i]}" != "${expected[$i]}" ]]; then
      echo "ERROR [$label]: port mismatch at index $i"
      echo "  expected: ${expected[$i]}"
      echo "  actual:   ${actual_arr[$i]}"
      echo "  all actual: ${actual_arr[*]}"
      exit 1
    fi
  done
  echo "OK [$label]: ${actual_arr[*]}"
}

# Default bind host → loopback only
unset TRANSCRIPTX_BIND_HOST || true
_assert_ports "default loopback" "127.0.0.1:8501:8501"

# Explicit LAN bind
export TRANSCRIPTX_BIND_HOST=0.0.0.0
_assert_ports "lan opt-in" "0.0.0.0:8501:8501"
unset TRANSCRIPTX_BIND_HOST || true

echo "OK: canonical compose bind assertions passed"
