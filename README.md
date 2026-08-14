# vac-gate

**Require a verified capability contract before this workflow passes.**

Before an agent can merge, generate a capability contract: what it
demonstrably handles, under which conditions, where it fails, and which
human gate remains required. That contract is a
[VAC bundle](https://github.com/egnaro9/vac-protocol) — a claim with
pinned evidence, mandatory limitations, and an issuer-replayable grading
recipe. vac-gate is the composite GitHub Action that holds a workflow to
one: no verified contract, no green check.

## What it gates

Given a bundle — a directory in your checkout, or an accepted entry
fetched sha256-checked from
[egnaro9/vac-protocol](https://github.com/egnaro9/vac-protocol)'s
registry — the gate:

1. **verifies it structurally** with the real `python -m vac.verify`
   (SPEC v0.1): manifest schema, every artifact present and
   sha256-identical, bundle closure, stated limitations, stamps agreeing,
   every declared number recomputed from the artifacts themselves;
2. **holds it to your requirements**: `require_agent` must equal the
   bundle's `subject.id` exactly, `require_family` its `protocol.task`
   exactly — no prefix or substring matching;
3. optionally **re-earns the verdicts** (`regrade: "true"`): clones the
   issuer at the pinned `issuer_commit` and runs its own regrader;
   anything but `consistent` fails, including the regrader's honest
   "stale-code" refusal — "cannot regrade" is not "regraded".

Every failure is one named reason and a nonzero exit. Every PASS states
what ran and what deliberately did not — a gate that cannot say what it
skipped is worse than no gate.

## Usage

```yaml
name: capability-contract
on: [pull_request]
jobs:
  gate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - uses: egnaro9/vac-gate@main
        with:
          bundle_path: certifications/claude-code-machine-2026-08-14
          require_agent: claude-code-headless
          require_family: machine
          regrade: "true"
```

Or gate on a registry entry instead of a committed bundle:

```yaml
      - uses: egnaro9/vac-gate@main
        with:
          registry_entry: agent-certlab/claude-code-machine-2026-08-14
          require_agent: claude-code-headless
```

`examples/agent-certlab-dogfood.yml` is the dogfood workflow for
agent-certlab itself — the repo that issues contracts, gating on its own
committed contract with a full regrade.

## Inputs

| input | meaning |
|---|---|
| `bundle_path` | a VAC bundle directory in this checkout. Exactly one of `bundle_path` / `registry_entry`. |
| `registry_entry` | name of an accepted entry in vac-protocol's `registry.json`; fetched via `python -m vac.registry --fetch-bundle`, every artifact sha256-checked against its registry pin. |
| `require_agent` | exact `subject.id` the bundle must certify; empty = any. |
| `require_family` | exact `protocol.task` the bundle must cover; empty = any. |
| `regrade` | `"true"` = clone the issuer at the pinned commit and re-earn every verdict with its own regrader. Default `"false"`. |

## What a PASS means — and does not

- **Structural PASS** means the bundle is *internally honest*: nothing in
  it contradicts anything else in it, and every declared number was
  recomputed from committed artifacts. It does **not** mean the issuer's
  grader agrees — that is the regrade.
- **Regrade PASS** means the issuer's own deterministic regrader, at the
  pinned commit, re-earned every verdict today.
- **v1 regrades `certlab-bundle-v1` bundles only.** Requesting `regrade`
  on any other profile **fails** with `regrade-unsupported` rather than
  silently skipping: a gate must never report green on a check it did not
  run.

## Named failure reasons

`no-bundle-input`, `ambiguous-bundle-input`, `bundle-not-found`,
`registry-clone-failed`, `registry-fetch-failed`, `vac-protocol-missing`,
`structural-verification-failed` (with `vac.verify`'s own named reasons
passed through: `sha256-mismatch`, `unlisted-file`, `summary-mismatch`,
…), `agent-mismatch`, `family-mismatch`, `regrade-unsupported`,
`issuer-unsafe`, `issuer-commit-unsafe`, `issuer-clone-failed`,
`issuer-checkout-failed`, `issuer-install-failed`, `regrade-failed`,
`regrade-not-consistent`.

## Freshness: the honest gap

VAC bundles carry **no dates by design** — the SPEC expresses time as
commits and content hashes, which are checkable, where dates are not. So
an age-based freshness input ("fail bundles older than 30 days") is
**not in v1**: there is nothing in the format to check it against, and a
gate that read a file mtime or a registry commit date would be enforcing
a signal the bundle never carried — theater, not verification.

What the gate does prove: the claim is *pinned* (issuer commit, sha256s)
and *internally honest*, and — with `regrade` — that the issuer's grader
still re-earns every verdict at the pinned commit today. What it cannot
prove: that the pinned commit is *recent*. A v2 freshness policy needs a
dated signal the format deliberately lacks; commit-ancestry policies are
the likely shape — "`issuer_commit` is an ancestor of the issuer's
current main, and at most N code-commits behind it" is checkable from git
history alone, no clock required. Until something like that is specified,
this gate does not pretend.

## Security posture

The manifest's `replay.commands` are **never executed** — they are opaque
shell text addressed to humans (SPEC section 2.6), and executing them
from a gate would hand any bundle author a shell. Regrade is structured
from validated fields only: `protocol.issuer` must be plain `owner/name`,
`issuer_commit` a hex commit, every subprocess is list-form, and no
issuer code is installed or run unless structural verification passed
first.

## Development

```
pip install pytest "git+https://github.com/egnaro9/vac-protocol"
python -m pytest tests/ -q
```

The tests drive `gate.py` as a real subprocess — real exit codes, the
same `VAC_GATE_*` env seam the composite uses — against two real
committed bundles copied verbatim as fixtures (agent-certlab's
`claude-code-machine-2026-08-14`, reference-fleet's board bundle). Every
named failure has a test that feeds the gate corrupted input and proves
it fires; CI also runs the composite entry point itself against the
fixture, so the `action.yml` wiring has a liveness check too.
