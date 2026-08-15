#!/usr/bin/env bash
# The four beats, run locally against a vac-gate checkout. Exit 0 only
# when every beat behaved: the pass-beats passed AND the failure-beats
# FAILED with their named reasons — a demo that goes green when the gate
# stopped firing would be exactly the theater the gate exists to prevent.
#
# usage: ./run_demo.sh [1|2|3|4]     (no argument = all four)
#   VAC_GATE=path  a local checkout of egnaro9/vac-gate (default ../vac-gate)
#   PYTHON=bin     an interpreter with vac-protocol installed
#                  (python3 -m pip install "git+https://github.com/egnaro9/vac-protocol")
set -u
cd "$(dirname "$0")"
GATE="${VAC_GATE:-../vac-gate}/gate.py"
PY="${PYTHON:-python3}"
[ -f "$GATE" ] || { echo "no gate.py at $GATE — set VAC_GATE to a vac-gate checkout"; exit 2; }
BUNDLE=certifications/claude-code-machine-2026-08-14
TAMPERED=certifications-tampered/claude-code-machine-2026-08-14
fail=0

run_gate() { out="$("$PY" "$GATE" "$@" 2>&1)"; rc=$?; printf '%s\n' "$out"; }
has() { printf '%s' "$out" | grep -qF "$1"; }
verdict() { # verdict <beat> <ok-condition-already-evaluated: $?>
  if [ "$1" -eq 0 ]; then echo "beat OK"; else echo "BEAT FAILED"; fail=1; fi
}

beat1() {
  echo; echo "=== beat 1 — the contract holds: valid bundle, matching bindings"
  run_gate --bundle-path "$BUNDLE" --bindings bindings.json \
           --require-agent claude-code-headless --require-family machine
  [ $rc -eq 0 ] && has "vac-gate: PASS" && has "6 matched exactly"
  verdict $?
}

beat2() {
  echo; echo "=== beat 2 — the inputs drifted: gate must FAIL, by name"
  run_gate --bundle-path "$BUNDLE" --bindings bindings-drift.json \
           --require-agent claude-code-headless --require-family machine
  [ $rc -ne 0 ] && has "FAIL binding-drift: harness_commit" \
                && has "FAIL binding-unrecorded: model"
  verdict $?
}

beat3() {
  echo; echo "=== beat 3 — re-pointed at the certified reality: gate passes again"
  # Mechanically beat 1 again, on purpose — see README: an honest
  # re-certification can only come from the issuer re-running one, and
  # this demo does not forge evidence.
  run_gate --bundle-path "$BUNDLE" --bindings bindings.json \
           --require-agent claude-code-headless --require-family machine
  [ $rc -eq 0 ] && has "vac-gate: PASS"
  verdict $?
}

beat4() {
  echo; echo "=== beat 4 — tampered contract copy (one flipped sha): gate must FAIL"
  run_gate --bundle-path "$TAMPERED" \
           --require-agent claude-code-headless --require-family machine
  [ $rc -ne 0 ] && has "sha256-mismatch" \
                && has "FAIL structural-verification-failed"
  verdict $?
}

case "${1:-all}" in
  1) beat1 ;;
  2) beat2 ;;
  3) beat3 ;;
  4) beat4 ;;
  all) beat1; beat2; beat3; beat4 ;;
  *) echo "usage: $0 [1|2|3|4]"; exit 2 ;;
esac
echo
[ $fail -eq 0 ] && echo "run_demo: every beat behaved" || echo "run_demo: FAILURE"
exit $fail
