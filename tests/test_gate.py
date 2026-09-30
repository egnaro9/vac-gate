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

import json
import os
import pathlib
import shutil
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
GATE = ROOT / "gate.py"
CERTLAB = ROOT / "tests" / "fixtures" / "claude-code-machine-2026-08-14"
FLEET = ROOT / "tests" / "fixtures" / "fleet-board-vac"
BINDINGS_FIXTURE = ROOT / "tests" / "fixtures" / \
    "bindings-claude-code-machine.json"

# what the certlab fixture actually records, declared as current inputs —
# every natural mapping exercised, including the whole-pin-object alias
MATCHING = {"agent_id": "claude-code-headless",
            "agent_version": {"model": None, "harness_commit": "7954393",
                              "python": "3.14.6"},
            "family": "machine",
            "issuer": "egnaro9/agent-certlab",
            "issuer_commit": "7954393",
            "harness_commit": "7954393",
            "python": "3.14.6",
            "taskset_hash": "4430506556753096",
            "prompt_hash": "a61a9abe48592e97"}


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


# ------------------------------------------- semantic invalidation (bindings)
def _bindings(tmp_path: pathlib.Path, obj) -> str:
    p = tmp_path / "bindings.json"
    p.write_text(json.dumps(obj), encoding="utf-8")
    return str(p)


def test_bindings_all_matching_pass(tmp_path):
    p = gate("--bundle-path", str(CERTLAB),
             "--bindings", _bindings(tmp_path, MATCHING))
    assert p.returncode == 0, p.stdout + p.stderr
    assert ("ran: semantic invalidation: 9 declared binding(s) compared "
            "to recorded subject/protocol pins, 9 matched exactly"
            ) in p.stdout


def test_committed_bindings_fixture_matches():
    # the fixture ci.yml feeds the composite must stay true to the bundle
    p = gate("--bundle-path", str(CERTLAB),
             "--bindings", str(BINDINGS_FIXTURE))
    assert p.returncode == 0, p.stdout + p.stderr


def test_each_drifted_binding_fails_with_its_name(tmp_path):
    for key in ("agent_id", "family", "issuer", "issuer_commit",
                "harness_commit", "python", "taskset_hash", "prompt_hash"):
        drifted = dict(MATCHING)
        drifted[key] = "DRIFTED"
        p = gate("--bundle-path", str(CERTLAB),
                 "--bindings", _bindings(tmp_path, drifted))
        assert p.returncode == 1, key
        assert f"FAIL binding-drift: {key}: current 'DRIFTED' != contract " \
            in p.stdout, (key, p.stdout)


def test_drifted_pin_object_fails_deep_compare(tmp_path):
    drifted = dict(MATCHING)
    drifted["agent_version"] = {"model": None, "harness_commit": "7954393",
                                "python": "3.99.0"}
    p = gate("--bundle-path", str(CERTLAB),
             "--bindings", _bindings(tmp_path, drifted))
    assert p.returncode == 1
    assert "FAIL binding-drift: agent_version:" in p.stdout


def test_exact_means_no_type_coercion(tmp_path):
    drifted = dict(MATCHING)
    drifted["taskset_hash"] = 4430506556753096  # number, bundle records str
    p = gate("--bundle-path", str(CERTLAB),
             "--bindings", _bindings(tmp_path, drifted))
    assert p.returncode == 1
    assert "FAIL binding-drift: taskset_hash:" in p.stdout


def test_unrecorded_binding_fails(tmp_path):
    p = gate("--bundle-path", str(CERTLAB),
             "--bindings", _bindings(tmp_path,
                                     {**MATCHING, "temperature": 0.0}))
    assert p.returncode == 1
    assert ("FAIL binding-unrecorded: temperature — the contract does "
            "not bind this input") in p.stdout


def test_null_pin_is_unrecorded_not_matching_and_not_drift(tmp_path):
    # the certlab bundle records subject.version.model: null — explicitly
    # unpinned. Declaring a current model must fail, and must NOT be
    # reported as drift: the contract never knew an old value to drift from
    p = gate("--bundle-path", str(CERTLAB),
             "--bindings", _bindings(tmp_path,
                                     {**MATCHING,
                                      "model": "claude-sonnet-4-6"}))
    assert p.returncode == 1
    assert "FAIL binding-unrecorded: model" in p.stdout
    assert "explicitly unpinned" in p.stdout
    assert "binding-drift: model" not in p.stdout


def test_missing_bindings_file_fails_loudly():
    p = gate("--bundle-path", str(CERTLAB),
             "--bindings", "does/not/exist.json")
    assert p.returncode == 1
    assert "FAIL bindings-not-found" in p.stdout


def test_unparsable_bindings_fails(tmp_path):
    bad = tmp_path / "bindings.json"
    bad.write_text("not json{", encoding="utf-8")
    p = gate("--bundle-path", str(CERTLAB), "--bindings", str(bad))
    assert p.returncode == 1
    assert "FAIL bindings-unparsable" in p.stdout


def test_non_object_bindings_fails(tmp_path):
    p = gate("--bundle-path", str(CERTLAB),
             "--bindings", _bindings(tmp_path, ["model"]))
    assert p.returncode == 1
    assert "FAIL bindings-unparsable" in p.stdout
    assert "JSON object" in p.stdout


def test_bindings_env_seam(tmp_path):
    drifted = dict(MATCHING)
    drifted["family"] = "ledger"
    p = gate(env_extra={"VAC_GATE_BUNDLE_PATH": str(CERTLAB),
                        "VAC_GATE_BINDINGS": _bindings(tmp_path, drifted)})
    assert p.returncode == 1
    assert "FAIL binding-drift: family:" in p.stdout


def test_no_bindings_is_reported_not_silent():
    p = gate("--bundle-path", str(CERTLAB))
    assert p.returncode == 0
    assert "not run: semantic invalidation: no bindings declared" in p.stdout


def test_scope_lines_always_printed():
    # the honesty scope must be in the output whether green or red
    for p in (gate("--bundle-path", str(CERTLAB)),
              gate("--bundle-path", "does/not/exist")):
        assert "scope: semantic invalidation reads DECLARED bindings only" \
            in p.stdout
        assert "never runtime authorization" in p.stdout
        assert "never a non-repudiation claim" in p.stdout


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
    # the dispatch is live without network and without installing anything.
    # The allowlist is REQUIRED to get here, which is the point of the three
    # tests below; passing it is what makes this test about the clone.
    p = gate("--bundle-path", str(CERTLAB), "--regrade", "true",
             "--allowed-issuers", "egnaro9/agent-certlab",
             "--clone-base", str(tmp_path))
    assert p.returncode == 1
    assert "FAIL issuer-clone-failed" in p.stdout
    assert "agent-certlab" in p.stdout  # the issuer it tried to clone


# --------------------------------------------- issuer allowlist (regrade RCE)
# regrade runs `pip install -e` on the repository protocol.issuer names, and
# protocol.issuer is written by the bundle's author, so the consumer has to
# say which issuers it trusts. Structural verification cannot substitute: it
# is a self-consistency checksum over an unsigned document, so a forged
# bundle is internally honest about an issuer it picked itself.

def test_regrade_refuses_when_no_allowlist_is_declared(tmp_path):
    p = gate("--bundle-path", str(CERTLAB), "--regrade", "true",
             "--clone-base", str(tmp_path))
    assert p.returncode == 1
    assert "FAIL regrade-no-allowlist" in p.stdout
    # and it stopped BEFORE the clone: the clone failure is not named
    assert "issuer-clone-failed" not in p.stdout
    # the bundle itself is fine; the refusal is about consumer policy
    assert "structural verification: PASS" in p.stdout


def test_regrade_refuses_an_issuer_outside_the_allowlist(tmp_path):
    p = gate("--bundle-path", str(CERTLAB), "--regrade", "true",
             "--allowed-issuers", "someone-else/trusted-tool",
             "--clone-base", str(tmp_path))
    assert p.returncode == 1
    assert "FAIL issuer-not-allowed" in p.stdout
    assert "egnaro9/agent-certlab" in p.stdout   # what it refused
    assert "issuer-clone-failed" not in p.stdout  # again, before the clone


def test_a_self_consistent_bundle_naming_an_attacker_repo_is_refused(
        tmp_path):
    """The exploit, as a regression test.

    A bundle that verifies clean and satisfies both exact-match requirements
    can still name any issuer it likes. Before the allowlist, that string
    reached `git clone` and then `pip install -e`, which executes the cloned
    repository's build backend: arbitrary code execution on the runner from a
    structurally valid bundle. It must now fail before anything is fetched.
    """
    b = tmp_path / "bundle"
    shutil.copytree(CERTLAB, b)
    man = json.loads((b / "vac.json").read_text(encoding="utf-8"))
    man["protocol"]["issuer"] = "attacker/evil"
    (b / "vac.json").write_text(json.dumps(man, indent=1), encoding="utf-8")

    p = gate("--bundle-path", str(b), "--regrade", "true",
             "--allowed-issuers", "egnaro9/agent-certlab",
             "--clone-base", str(tmp_path))
    assert p.returncode == 1
    assert "FAIL issuer-not-allowed" in p.stdout
    assert "attacker/evil" in p.stdout
    # nothing was fetched and nothing was installed
    assert "issuer-clone-failed" not in p.stdout
    assert "issuer-install-failed" not in p.stdout
    assert not (tmp_path / "issuer").exists()


def test_issuer_shape_refuses_a_dot_only_component():
    """'..' fullmatched the old shape class, because '.' is in it.

    So '../..' was a legal `protocol.issuer` and reached the clone URL
    builder. Shape is not the control, but a traversal should not get that
    far either.
    """
    from gate import issuer_shape_ok
    assert issuer_shape_ok("egnaro9/agent-certlab")
    assert issuer_shape_ok("owner/repo.name")     # a real dot still fine
    assert not issuer_shape_ok("../..")
    assert not issuer_shape_ok("./x")
    assert not issuer_shape_ok("x/..")
    assert not issuer_shape_ok("../x")


def test_registry_mode_clone_failure_named(tmp_path):
    p = gate("--registry-entry",
             "agent-certlab/claude-code-machine-2026-08-14",
             "--clone-base", str(tmp_path))
    assert p.returncode == 1
    assert "FAIL registry-clone-failed" in p.stdout
