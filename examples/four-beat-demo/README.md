# vac-gate-demo

**An agent opened this PR. CI will not go green without its capability
contract.**

This is the minimum viable version of a policy: an agent that opens PRs
carries a **capability contract** — a
[VAC bundle](https://github.com/egnaro9/vac-protocol): a claim with
pinned evidence, mandatory limitations, and an issuer-replayable grading
recipe — and CI holds every run to it with
[egnaro9/vac-gate](https://github.com/egnaro9/vac-gate). The "PR" here is
a prop (`slugify.py` and its test); the exhibit is the gate.

## What is vendored here

- `certifications/claude-code-machine-2026-08-14/` — a **real** contract
  issued by [agent-certlab](https://github.com/egnaro9/agent-certlab),
  copied verbatim, hashes intact: `claude-code-headless` fixed 6/6
  seeded defects in the `machine` task family under policy, graded from
  on-disk artifacts only, regradeable at the pinned issuer commit
  `7954393`.
- `bindings.json` — this repo's declaration of the CURRENT bound
  inputs: agent id, family, harness commit, python, task-set and prompt
  hashes. The gate holds every declared key to the contract's recorded
  pins, exactly.
- `bindings-drift.json` — the same declaration after the runtime moved:
  the harness commit changed, and a model is now explicitly bound.
- `certifications-tampered/claude-code-machine-2026-08-14/` — a copy of
  the contract with **one flipped hex character** in the recorded sha256
  of `bundle.json`, committed deliberately as beat 4's exhibit.

## The four beats

All four beats pass locally via `run_demo.sh`; the same four beats run as CI jobs on every push — the failure beats *assert that the gate
fails*, with its named reason. A demo that went green while the gate
stopped firing would be exactly the theater the gate exists to prevent.

### Beat 1 — the contract holds

Valid bundle, matching bindings, exact agent and family requirements:

```
vac-gate: PASS (certifications/claude-code-machine-2026-08-14)
  ran: structural verification: python -m vac.verify (offline: schema, sha256s, closure, limitations, results recomputed from artifacts)
  ran: require_agent: subject.id == 'claude-code-headless'
  ran: require_family: protocol.task == 'machine'
  ran: semantic invalidation: 6 declared binding(s) compared to recorded subject/protocol pins, 6 matched exactly
  not run: semantic regrade: not requested (regrade: false) — this gate did NOT re-earn the verdicts, only their internal honesty
```

### Beat 2 — the inputs drifted, the gate fails by name

`bindings-drift.json` says the runtime moved: harness commit `9f21c47`
(the contract was earned at `7954393`) and model `claude-sonnet-4-6` now
explicitly bound. Exit nonzero, two named reasons:

```
FAIL binding-drift: harness_commit: current '9f21c47' != contract '7954393'
FAIL binding-unrecorded: model — the contract does not bind this input (subject.version.model is recorded null: explicitly unpinned, and unpinned is not a match)
vac-gate: FAIL — 2 named reason(s) (certifications/claude-code-machine-2026-08-14)
```

Why the model change is `binding-unrecorded` and not `binding-drift`:
this real contract records `subject.version.model: null` — the issuer
explicitly pinned the harness and python, **not** the model. The
contract never knew a model, so it can neither vouch for the current one
nor name an old value it "drifted" from. A gate that read an unpinned
input as matching — or invented a drift — would be laundering the claim.
Unrecorded is not matching; that is the point.

### Beat 3 — "re-certified": re-pointed at the certified reality

Plainly: **this beat is mechanically beat 1 again, on purpose.** An
honest re-certification matching the drifted bindings would be a new
bundle from agent-certlab, actually re-earned at harness commit
`9f21c47` with the model pinned — a run only the issuer can produce, and
this demo does not have it. Fabricating a bundle variant that *claims*
such a run (edited pins, recomputed hashes, a nonexistent issuer commit)
would verify structurally and be a forgery — precisely what the replay
block and the challenge protocol exist to catch. So the honest
remediation shown here is the other direction: restore the bindings to
the reality the contract certified, and the gate passes again. When the
runtime genuinely must move, the remediation is a genuinely re-earned
contract — not an edited one.

### Beat 4 — the contract was tampered with

One flipped hex character in the recorded sha256 (`…780e` → `…780f`).
Exit nonzero, the structural reason named:

```
FAIL sha256-mismatch: bundle.json: manifest bd21e628a5c057babf4e55112ce778cec343b8cee529052af4f303b27482780f, file bd21e628a5c057babf4e55112ce778cec343b8cee529052af4f303b27482780e
structural verification: FAIL — 1 named reason(s) (claude-code-machine-2026-08-14)
FAIL structural-verification-failed: python -m vac.verify exited 1; its named reasons are above
```

## Run it yourself — ten minutes, local, no network after the installs

```
git clone https://github.com/egnaro9/vac-gate
git clone https://github.com/egnaro9/vac-gate-demo
python3 -m pip install "git+https://github.com/egnaro9/vac-protocol"
cd vac-gate-demo
./run_demo.sh        # all four beats; exit 0 = every beat behaved
./run_demo.sh 2      # or one beat at a time
```

`run_demo.sh` drives the sibling `vac-gate` checkout (`VAC_GATE=path` to
point elsewhere) and asserts each beat's expected outcome — including
that beats 2 and 4 exit nonzero with their named reasons. The prop has
its own trivial suite: `python3 -m pytest -q`.

## What a green check here does NOT mean

- It is **integrity-gate evidence, not a capability guarantee**: the
  contract covers exactly its pinned task family, harness commit, and
  hashes — nothing open-world, nothing about other tasks or other days.
- **Semantic invalidation reads declared bindings only.** Undisclosed
  provider changes behind a stable model id, runtime context nobody
  declared, tool behavior, distribution shift between the certified
  family and live traffic — all outside it.
- It is a **claim-integrity control, never runtime authorization**: a
  green check means the contract's evidence held and the declared pins
  agree. It does not clear an agent to act. Agent Release Readiness is
  a judgment made over replayable evidence like this; the gate supplies
  the evidence check, not the judgment.
- **No non-repudiation**: bundles are unsigned by design; the gate
  proves internal honesty and pin agreement, not authorship.
- Without `regrade`, the verdicts were **not re-earned** — every report
  says so on its face.

---

Would you require this gate for an agent allowed to open or merge PRs in
your organization?

---

*Moved here from the standalone `vac-gate-demo` repository (archived 2026-08-15).
It was two commits and one six-line source file; as a consumer-side example beside
the action it documents, it earns its place — as its own repo it was padding.*
