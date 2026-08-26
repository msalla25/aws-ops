# One-off prompt version

Paste this with the skill's text when you can't install the skill. Same gate, same
rubric, condensed.

---

You are auditing an existing Claude skill. Read it once. Do not run it, do not fetch
anything external, do not re-read it.

Score these 12 checks 0 (absent) / 1 (partial) / 2 (solid). Checks marked `!` are
critical — they make an operational skill dangerous, not just mediocre.

1. Trigger fidelity — description matches real user phrasing without over-firing
2. Scope boundary — states what it does NOT do and when to hand back to a human
3. `!` Signal specificity — names the actual query/metric/entity, not "check the dashboards"
4. `!` Threshold & baseline discipline — defines the comparison window and what it compares against; percentiles not averages; ratios not raw counts
5. Surface coverage — async/queue paths, saturation, per-instance skew, downstream hops, "did traffic actually arrive", "is the new build actually running"
6. `!` Evidence binding — every claim carries a query result, time range, and entity ID; unsourced claims forbidden by the skill itself
7. Degraded mode — what to do when a source is down or coverage is partial
8. `!` Action safety — read-only by default; writes/restarts/rollbacks gated on a human
9. Inconclusive path — can return "not enough signal" instead of guessing
10. `!` Verdict discipline — ends in a decision + owner + next action, not a summary
11. Token economy — progressive disclosure, no inlined runbooks or restated tool docs
12. Maintainability — no hardcoded hosts, entity IDs, dates, or single-team assumptions

Every score below 2 must quote a line from the skill. A finding you cannot cite is a
finding you invented — delete it before scoring.

Then apply the gate, first match wins:

- **REWRITE** if total < 14, or two or more `!` checks scored 0
- **PATCH** if total is 14–19, or exactly one `!` check scored 0
- **KEEP** if total ≥ 20 and no `!` check scored 0

Output exactly one of:

**KEEP** — about 12 lines: score, two things holding up well (cited), the weakest point
with its one-line fix, and the condition that would justify re-auditing. Then stop. Do
not produce a v2, do not offer to, do not list the passing checks.

**PATCH** — score line, failing checks in a compact table, then 1–5 exact find/replace
edits against the skill's real text. No full file, no restructuring.

**REWRITE** — a design-delta table first (what structurally changed, which check each
change fixes), then the new skill, then a revert note, then three realistic test prompts.
The rewrite must make at least two structural changes: gated phases with stop conditions,
evidence-collection separated from interpretation, a fixed data contract for output,
depth moved into reference files, deterministic queries replacing model judgment, or an
added negative path. If v2 only says the same things in better words, downgrade to PATCH
and ship the edits instead.

Prettier is not a finding. "Keep it" is a valid answer and should be the cheap one.
