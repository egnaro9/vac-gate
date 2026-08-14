"""vac-gate: require a verified capability contract before a workflow passes.

The gate over VAC bundles (vac-protocol SPEC v0.1): acquire a bundle —
a directory in the consumer's checkout, or an accepted entry fetched
sha256-checked from egnaro9/vac-protocol's registry — verify it
structurally with the real `python -m vac.verify`, hold it to the
consumer's requirements (exact subject.id, exact protocol.task), and
optionally re-earn every verdict with the issuer's own regrader at the
pinned commit. Every failure is one named reason; exit nonzero on any.

Honesty rules, stated because a gate that cannot say what it did not
check is worse than no gate:

- a structural PASS means the bundle is internally honest, not that the
  issuer's grader agrees — that is the regrade, and the final report
  names which of the two ran;
- regrade in v1 covers certlab-bundle-v1 only; requesting it on any
  other bundle FAILS (`regrade-unsupported`) rather than silently
  skipping;
- VAC bundles carry no dates BY DESIGN, so this gate proves
  pinned-and-honest, never recent — age-based freshness is not faked
  here (README, "Freshness: the honest gap").

Security posture: the manifest's replay.commands are NEVER executed —
regrade is structured from validated fields only (protocol.issuer must
be plain owner/name, issuer_commit a hex commit), every subprocess is
list-form, and no issuer code is installed or run unless structural
verification passed first.

Configuration: CLI flags, defaulting to the VAC_GATE_* environment the
composite action sets. Stdlib only.
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import re
import subprocess
import sys
import tempfile

REGISTRY_REPO = "egnaro9/vac-protocol"
DEFAULT_CLONE_BASE = "https://github.com"  # VAC_GATE_CLONE_BASE is the
# test seam: git clones from a local base directory exactly as from a host
SAFE_ISSUER = re.compile(r"[A-Za-z0-9._-]+/[A-Za-z0-9._-]+")
SAFE_COMMIT = re.compile(r"[0-9a-f]{4,40}")


def _run(argv: list[str], cwd=None) -> subprocess.CompletedProcess:
    return subprocess.run(argv, cwd=cwd, capture_output=True,
                          encoding="utf-8", errors="replace")


def _tail(p: subprocess.CompletedProcess) -> str:
    return " | ".join((p.stdout + p.stderr).strip().splitlines()[-3:])[-400:]


def fetch_registry_bundle(entry: str, tmp: pathlib.Path, clone_base: str,
                          failures: list[str]) -> pathlib.Path | None:
    """One accepted registry entry, every artifact sha256-checked against
    its registry pin by vac.registry itself. The registry repo is CLONED
    (depth 1) rather than pip-installed because registry.json lives in the
    repo, not the wheel — the module resolves it next to its own source,
    so it must run from a checkout."""
    reg = tmp / "vac-protocol"
    p = _run(["git", "clone", "--quiet", "--depth", "1",
              f"{clone_base}/{REGISTRY_REPO}", str(reg)])
    if p.returncode != 0:
        failures.append(f"registry-clone-failed: {clone_base}/"
                        f"{REGISTRY_REPO}: {_tail(p)}")
        return None
    dest = tmp / "bundle"
    dest.mkdir()
    p = _run([sys.executable, "-m", "vac.registry",
              "--fetch-bundle", entry, "--dest", str(dest)], cwd=reg)
    if p.stdout.strip():
        print(p.stdout.strip())
    if p.returncode != 0:
        failures.append(f"registry-fetch-failed: {entry!r} — the fetch "
                        "tool's own named reasons are above")
        return None
    return dest


def structural_verify(bundle: pathlib.Path, failures: list[str]) -> bool:
    """The real `python -m vac.verify`, output passed through — its named
    reasons ARE the gate's structural reasons."""
    p = _run([sys.executable, "-m", "vac.verify", str(bundle)])
    sys.stdout.write(p.stdout)
    if "No module named" in p.stderr:
        failures.append("vac-protocol-missing: python -m vac.verify is not "
                        "importable — pip install "
                        f"'git+{DEFAULT_CLONE_BASE}/{REGISTRY_REPO}'")
        return False
    if p.returncode != 0:
        failures.append("structural-verification-failed: python -m "
                        f"vac.verify exited {p.returncode}; its named "
                        "reasons are above")
        return False
    return True


def check_requirements(man: dict, require_agent: str, require_family: str,
                       failures: list[str], ran: list[str]) -> None:
    """Exact-match requirements: require_agent against subject.id,
    require_family against protocol.task. Exact, not substring — a gate
    that prefix-matched would pass 'claude-code' for any claude-code-*."""
    if require_agent:
        got = (man.get("subject") or {}).get("id")
        if got != require_agent:
            failures.append(f"agent-mismatch: required subject.id "
                            f"{require_agent!r}, bundle certifies {got!r}")
        ran.append(f"require_agent: subject.id == {require_agent!r}")
    if require_family:
        got = (man.get("protocol") or {}).get("task")
        if got != require_family:
            failures.append(f"family-mismatch: required protocol.task "
                            f"{require_family!r}, bundle covers {got!r}")
        ran.append(f"require_family: protocol.task == {require_family!r}")


def run_regrade(man: dict, bundle: pathlib.Path, tmp: pathlib.Path,
                clone_base: str, failures: list[str],
                ran: list[str]) -> None:
    """Clone the issuer at the pinned commit and re-earn every verdict
    with its own regrader; anything but 'consistent' fails — including the
    regrader's honest 'stale-code' refusal, which exits 0 but re-earns
    nothing (a gate must not read 'cannot regrade' as 'regraded')."""
    checks = (man.get("results") or {}).get("checks") or []
    profiles = sorted({str(c.get("profile")) for c in checks
                       if isinstance(c, dict)})
    if profiles != ["certlab-bundle-v1"]:
        failures.append("regrade-unsupported: v1 regrades certlab-bundle-v1 "
                        "bundles only, and never silently skips — this "
                        f"bundle's profile(s): {', '.join(profiles)}")
        return
    issuer = man["protocol"]["issuer"]
    commit = man["protocol"]["issuer_commit"]
    if not SAFE_ISSUER.fullmatch(issuer):
        failures.append(f"issuer-unsafe: protocol.issuer {issuer!r} is not "
                        "plain owner/name; refusing to build a clone URL")
        return
    if not SAFE_COMMIT.fullmatch(commit):
        failures.append(f"issuer-commit-unsafe: {commit!r} is not a hex "
                        "commit; refusing to check it out")
        return
    issuer_dir = tmp / "issuer"
    p = _run(["git", "clone", "--quiet", f"{clone_base}/{issuer}",
              str(issuer_dir)])
    if p.returncode != 0:
        failures.append(f"issuer-clone-failed: {clone_base}/{issuer}: "
                        f"{_tail(p)}")
        return
    p = _run(["git", "-C", str(issuer_dir), "checkout", "--quiet", commit])
    if p.returncode != 0:
        failures.append(f"issuer-checkout-failed: {commit}: {_tail(p)}")
        return
    p = _run([sys.executable, "-m", "pip", "install", "--quiet",
              "-e", f"{issuer_dir}[test]"])
    if p.returncode != 0:
        failures.append(f"issuer-install-failed: {_tail(p)}")
        return
    ran.append(f"semantic regrade: {issuer} cloned at {commit}; its own "
               "regrader re-earned every verdict")
    for art in [c["artifact"] for c in checks]:
        p = _run([sys.executable, "-m", "certlab.regrade",
                  str(bundle / art)])
        out = (p.stdout + p.stderr).strip()
        if out:
            print(out)
        if p.returncode != 0:
            failures.append(f"regrade-failed: {art}: regrader exited "
                            f"{p.returncode} — its report is above")
        elif ": consistent" not in p.stdout or "stale-code" in p.stdout \
                or "mismatch" in p.stdout:
            failures.append(f"regrade-not-consistent: {art}: anything but "
                            "'consistent' fails the gate — the regrader's "
                            "report is above")


def main(argv: list[str] | None = None) -> int:
    e = os.environ.get
    ap = argparse.ArgumentParser(
        description="require a verified capability contract (VAC bundle) "
                    "before this workflow passes")
    ap.add_argument("--bundle-path", default=e("VAC_GATE_BUNDLE_PATH", ""))
    ap.add_argument("--registry-entry",
                    default=e("VAC_GATE_REGISTRY_ENTRY", ""))
    ap.add_argument("--require-agent", default=e("VAC_GATE_REQUIRE_AGENT", ""))
    ap.add_argument("--require-family",
                    default=e("VAC_GATE_REQUIRE_FAMILY", ""))
    ap.add_argument("--regrade", default=e("VAC_GATE_REGRADE", "false"))
    ap.add_argument("--clone-base",
                    default=e("VAC_GATE_CLONE_BASE", DEFAULT_CLONE_BASE))
    a = ap.parse_args(argv)
    want_regrade = a.regrade.strip().lower() in ("true", "1", "yes")

    failures: list[str] = []
    ran: list[str] = []      # what this run actually checked
    skipped: list[str] = []  # what it deliberately did not
    where = "no bundle"
    with tempfile.TemporaryDirectory() as td:
        tmp = pathlib.Path(td)
        bundle: pathlib.Path | None = None
        if a.bundle_path and a.registry_entry:
            failures.append("ambiguous-bundle-input: exactly one of "
                            "bundle_path / registry_entry, got both")
        elif a.bundle_path:
            where = a.bundle_path
            bundle = pathlib.Path(a.bundle_path)
            if not bundle.is_dir():
                failures.append(f"bundle-not-found: {a.bundle_path!r} is "
                                "not a directory in this checkout")
                bundle = None
        elif a.registry_entry:
            where = f"registry entry {a.registry_entry!r}"
            bundle = fetch_registry_bundle(a.registry_entry, tmp,
                                           a.clone_base, failures)
            if bundle is not None:
                ran.append(f"registry fetch: {a.registry_entry!r}, every "
                           "artifact sha256-checked against its registry "
                           "pin")
        else:
            failures.append("no-bundle-input: exactly one of bundle_path / "
                            "registry_entry required")

        structural_ok = False
        man = None
        if bundle is not None:
            structural_ok = structural_verify(bundle, failures)
            ran.append("structural verification: python -m vac.verify "
                       "(offline: schema, sha256s, closure, limitations, "
                       "results recomputed from artifacts)")
            try:  # requirements still run on a parseable manifest so one
                # run names every reason; regrade never does (see below)
                man = json.loads((bundle / "vac.json")
                                 .read_text(encoding="utf-8"))
            except (OSError, UnicodeDecodeError, json.JSONDecodeError):
                man = None  # vac.verify already named it
        if isinstance(man, dict):
            check_requirements(man, a.require_agent, a.require_family,
                               failures, ran)
        if not a.require_agent:
            skipped.append("require_agent: not set — any subject.id passes")
        if not a.require_family:
            skipped.append("require_family: not set — any protocol.task "
                           "passes")
        if want_regrade:
            if isinstance(man, dict) and structural_ok:
                run_regrade(man, bundle, tmp, a.clone_base, failures, ran)
            elif bundle is not None:
                skipped.append("semantic regrade: refused — no issuer code "
                               "is installed or run for a bundle that "
                               "failed structural verification")
        else:
            skipped.append("semantic regrade: not requested (regrade: "
                           "false) — this gate did NOT re-earn the "
                           "verdicts, only their internal honesty")

    for f in failures:
        print(f"FAIL {f}")
    verdict = ("PASS" if not failures
               else f"FAIL — {len(failures)} named reason(s)")
    print(f"vac-gate: {verdict} ({where})")
    for line in ran:
        print(f"  ran: {line}")
    for line in skipped:
        print(f"  not run: {line}")
    print("  freshness: VAC bundles carry no dates by design — this gate "
          "proves pinned-and-honest, not recent (README, v2)")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
