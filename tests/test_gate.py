"""pytest over gate.py — every gate check gets a test that feeds it
corrupted input and proves it fires (CONTRIBUTING: a gate without a
liveness test is untested code). The green path runs against a REAL
committed bundle: agent-certlab's claude-code-machine-2026-08-14, copied
verbatim as a fixture; the second fixture is reference-fleet's board
bundle, whose profile v1 regrade must REFUSE by name, never silently
skip. The gate is driven the way CI drives it — a real subprocess of
gate.py with real exit codes and env — not by importing its functions.

Requires vac-protocol installed (pip install
git+https://github.com/egnaro9/vac-protocol), exactly as the composite
installs it. Network paths (registry fetch, issuer clone from GitHub) are
exercised up to their first subprocess via the --clone-base test seam;
the full regrade green path runs in agent-certlab's dogfood workflow
(examples/agent-certlab-dogfood.yml), not here.
"""
from __future__ import annotations

import os
import pathlib
import shutil
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
GATE = ROOT / "gate.py"
CERTLAB = ROOT / "tests" / "fixtures" / "claude-code-machine-2026-08-14"
FLEET = ROOT / "tests" / "fixtures" / "fleet-board-vac"


def _env(extra: dict[str, str] | None = None) -> dict[str, str]:
    """The parent env minus any VAC_GATE_* leakage, plus `extra`."""
    env = {k: v for k, v in os.environ.items()
           if not k.startswith("VAC_GATE_")}
    env.update(extra or {})
    return env


def gate(*args: str, env_extra: dict[str, str] | None = None,
         ) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(GATE), *args],
                          capture_output=True, text=True, env=_env(env_extra))


# ---------------------------------------------------------------- green path
def test_green_path_real_certlab_bundle():
    p = gate("--bundle-path", str(CERTLAB))
    assert p.returncode == 0, p.stdout + p.stderr
    assert "structural verification: PASS" in p.stdout
    assert "vac-gate: PASS" in p.stdout
    # honesty: a PASS without regrade must say the verdicts were not
    # re-earned — 'checked and clean' must never read like 'never checked'
    assert "not run: semantic regrade" in p.stdout
    assert "carry no dates by design" in p.stdout


def test_green_path_with_matching_requirements():
    p = gate("--bundle-path", str(CERTLAB),
             "--require-agent", "claude-code-headless",
             "--require-family", "machine")
    assert p.returncode == 0, p.stdout + p.stderr
    assert "ran: require_agent: subject.id == 'claude-code-headless'" \
        in p.stdout
    assert "ran: require_family: protocol.task == 'machine'" in p.stdout


def test_env_configuration_matches_action_yml():
    # the composite passes inputs as VAC_GATE_* env, no argv — prove that
    # seam works end to end
    p = gate(env_extra={"VAC_GATE_BUNDLE_PATH": str(CERTLAB),
                        "VAC_GATE_REQUIRE_AGENT": "claude-code-headless",
                        "VAC_GATE_REQUIRE_FAMILY": "machine",
                        "VAC_GATE_REGRADE": "false"})
    assert p.returncode == 0, p.stdout + p.stderr
    assert "vac-gate: PASS" in p.stdout


def test_fleet_bundle_green_without_regrade():
    p = gate("--bundle-path", str(FLEET))
    assert p.returncode == 0, p.stdout + p.stderr


# ----------------------------------------------------- named-failure paths
def test_wrong_agent_named():
    p = gate("--bundle-path", str(CERTLAB), "--require-agent", "aider")
    assert p.returncode == 1
    assert "FAIL agent-mismatch" in p.stdout
    assert "'claude-code-headless'" in p.stdout  # names what it DOES certify


def test_agent_match_is_exact_not_prefix():
    p = gate("--bundle-path", str(CERTLAB),
             "--require-agent", "claude-code")
    assert p.returncode == 1
    assert "FAIL agent-mismatch" in p.stdout


def test_wrong_family_named():
    p = gate("--bundle-path", str(CERTLAB), "--require-family", "ledger")
    assert p.returncode == 1
    assert "FAIL family-mismatch" in p.stdout
    assert "'machine'" in p.stdout


def test_wrong_agent_and_family_both_named_in_one_run():
    p = gate("--bundle-path", str(CERTLAB), "--require-agent", "aider",
             "--require-family", "ledger")
    assert p.returncode == 1
    assert "FAIL agent-mismatch" in p.stdout
    assert "FAIL family-mismatch" in p.stdout


def test_tampered_artifact_fails_structurally(tmp_path):
    b = tmp_path / "bundle"
    shutil.copytree(CERTLAB, b)
    data = (b / "bundle.json").read_bytes()
    tampered = data.replace(b'"fixed": true', b'"fixed": false', 1)
    assert tampered != data
    (b / "bundle.json").write_bytes(tampered)
    p = gate("--bundle-path", str(b))
    assert p.returncode == 1
    assert "sha256-mismatch" in p.stdout
    assert "FAIL structural-verification-failed" in p.stdout
    # and the gate refuses to regrade what failed structure
    p = gate("--bundle-path", str(b), "--regrade", "true")
    assert p.returncode == 1
    assert "not run: semantic regrade: refused" in p.stdout


def test_smuggled_file_fails_closure(tmp_path):
    b = tmp_path / "bundle"
    shutil.copytree(CERTLAB, b)
    (b / "rider.txt").write_text("smuggled")
    p = gate("--bundle-path", str(b))
    assert p.returncode == 1
    assert "unlisted-file" in p.stdout


def test_no_input_named():
    p = gate()
    assert p.returncode == 1
    assert "FAIL no-bundle-input" in p.stdout


def test_both_inputs_named():
    p = gate("--bundle-path", str(CERTLAB),
             "--registry-entry", "evalmut/vac")
    assert p.returncode == 1
    assert "FAIL ambiguous-bundle-input" in p.stdout


def test_bundle_not_found_named():
    p = gate("--bundle-path", "does/not/exist")
    assert p.returncode == 1
    assert "FAIL bundle-not-found" in p.stdout


# ----------------------------------------------------------------- regrade
def test_regrade_refuses_non_certlab_profile():
    p = gate("--bundle-path", str(FLEET), "--regrade", "true")
    assert p.returncode == 1
    assert "FAIL regrade-unsupported" in p.stdout
    assert "fleet-board-v1" in p.stdout  # names the profile it refused
    # the refusal is about regrade scope, not the bundle: structure passed
    assert "structural verification: PASS" in p.stdout


def test_regrade_dispatch_reaches_issuer_clone(tmp_path):
    # clone base pointing at an empty directory: the regrade path must get
    # as far as cloning the PINNED issuer and name that failure — proving
    # the dispatch is live without network and without installing anything
    p = gate("--bundle-path", str(CERTLAB), "--regrade", "true",
             "--clone-base", str(tmp_path))
    assert p.returncode == 1
    assert "FAIL issuer-clone-failed" in p.stdout
    assert "agent-certlab" in p.stdout  # the issuer it tried to clone


def test_registry_mode_clone_failure_named(tmp_path):
    p = gate("--registry-entry",
             "agent-certlab/claude-code-machine-2026-08-14",
             "--clone-base", str(tmp_path))
    assert p.returncode == 1
    assert "FAIL registry-clone-failed" in p.stdout
