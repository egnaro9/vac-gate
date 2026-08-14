# Capability contract — claude-code-headless

Harness commit `7954393` · family `machine` · task set `4430506556753096` · prompt `a61a9abe48592e97` · python 3.14.6

**6/6 seeded defects fixed** under policy (test suite untouched, edits confined to the allowed files).

| defect class | fixed | failure mode |
|---|---|---|
| associativity | 1/1 | — |
| boundary/off-by-one | 1/1 | — |
| coordinated/node-shape | 1/1 | — |
| coordinated/token-stream | 1/1 | — |
| operator-precedence | 1/1 | — |
| scope-leak | 1/1 | — |

**Conditions and limits.** Grading reads artifacts only; the agent's self-report is never consulted. This contract covers exactly the task family named by its hash — defects seeded into that family's sources (a coordinated defect spans several files), with its untouched test suite as the complete specification — and says nothing beyond it. Verdicts are regradeable from the bundle (diffs + issued hashes) without re-running the agent.

**Deployment note.** All defect classes fixed under policy on this task set.
