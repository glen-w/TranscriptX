#!/usr/bin/env bash
# pip-audit the production image freeze (SR-08).
# Freeze is taken from the image; audit runs on the host so the image
# does not need pip-audit installed.
# Waived no-fix CVEs named in docs/dev/dependency_audit.md do not fail.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT_DIR"

IMAGE="${TRANSCRIPTX_IMAGE:-transcriptx:latest}"
OUT_DIR="${TRANSCRIPTX_AUDIT_OUT:-$ROOT_DIR/artifacts/pre-release}"
mkdir -p "$OUT_DIR"

if ! command -v docker >/dev/null 2>&1; then
  echo "SKIP: docker not available"
  exit 0
fi

if ! docker image inspect "$IMAGE" >/dev/null 2>&1; then
  echo "ERROR: image $IMAGE not found; build first"
  exit 1
fi

if ! command -v pip-audit >/dev/null 2>&1 && ! python3 -m pip_audit --help >/dev/null 2>&1; then
  echo "ERROR: pip-audit not available on host"
  exit 1
fi

docker run --rm --entrypoint python "$IMAGE" -m pip freeze \
  | tee "$OUT_DIR/pip-freeze-image.txt"

AUDIT_CMD=(pip-audit)
if ! command -v pip-audit >/dev/null 2>&1; then
  AUDIT_CMD=(python3 -m pip_audit)
fi

set +e
"${AUDIT_CMD[@]}" -r "$OUT_DIR/pip-freeze-image.txt" --format json \
  -o "$OUT_DIR/pip-audit-image.json"
AUDIT_RC=$?
"${AUDIT_CMD[@]}" -r "$OUT_DIR/pip-freeze-image.txt" --format columns \
  | tee "$OUT_DIR/pip-audit-image.txt"
set -e

WAIVER_DOC="$ROOT_DIR/docs/dev/dependency_audit.md"
if [[ "$AUDIT_RC" -ne 0 ]]; then
  python3 - "$OUT_DIR/pip-audit-image.json" "$WAIVER_DOC" <<'PY'
import json
import sys
from pathlib import Path

report = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
waiver = Path(sys.argv[2]).read_text(encoding="utf-8")
deps = report.get("dependencies", report if isinstance(report, list) else [])
blocking = []
waived = []
for dep in deps:
    for vuln in dep.get("vulns") or []:
        ids = [vuln.get("id") or ""]
        ids.extend(vuln.get("aliases") or [])
        ids = [i for i in ids if i]
        fixable = bool(vuln.get("fix_versions"))
        named = any(i in waiver for i in ids)
        label = f"{dep.get('name')} {dep.get('version')} ({', '.join(ids)})"
        if named and not fixable:
            waived.append(label)
        else:
            blocking.append(label)
if waived:
    print("Waived no-fix findings:")
    for row in waived:
        print(f"  {row}")
if blocking:
    print("Blocking findings:")
    for row in blocking:
        print(f"  {row}")
    sys.exit(1)
print("OK: image pip-audit has no unwaived findings")
PY
fi

echo "OK: image pip-audit completed"
