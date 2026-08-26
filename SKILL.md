---
name: skill-refactor
description: Audit an existing Claude skill, score it against a fixed rubric, and either declare it good enough to keep or produce a structurally different rewrite. Use this whenever the user wants a skill reviewed, critiqued, hardened, slimmed down, "made better", or rewritten — including SRE release-verification, observability-check, runbook, triage, and change-management skills. Also use when the user asks whether an existing skill is worth keeping, why a skill misfires or produces vague output, or wants a second opinion before adopting a skill from another team.
---

# Skill Refactor

Most skill reviews fail in one of two directions: they rubber-stamp a mediocre skill,
or they rewrite a perfectly good one to prove they did work. This skill exists to make
both failures expensive and the honest answer cheap.

The core rule: **a rewrite must be earned by evidence, and "keep it" is a valid, fast,
low-token outcome.** If the target skill scores well, say so in a dozen lines and stop.

## Step 0 — Get the target, once

Resolve the skill under review in this order:

1. A path was given → read the `SKILL.md` plus any referenced files that actually exist.
2. Content was pasted or uploaded → use it as-is.
3. Neither → ask for it in one sentence and stop. Do not guess, do not draft a
   speculative skill, do not search the web for "SRE release check skill examples."

Read the target **once**. Do not re-read it to "double check" — quote from what you
already have. Do not execute the skill. Do not fetch external documentation unless the
target references a local file you can open.

Then record the baseline in two lines: file count, total line count of `SKILL.md`, and
whether bundled resources exist. This is the token-economy baseline you will score
against later.

## Step 1 — Score against the rubric

Twelve checks. Each scores **0 (absent/broken), 1 (partial), 2 (solid)**. Max 24.
Five are marked `!` — these are the checks that make an operational skill *dangerous*
rather than merely mediocre.

| # | Check | What "solid" looks like |
|---|---|---|
| 1 | Trigger fidelity | Description names real user phrasing and contexts; doesn't over-fire on adjacent work |
| 2 | Scope boundary | States what the skill does *not* do and when to hand back to a human |
| 3 | `!` Signal specificity | Names the actual query, metric, entity, or endpoint. "Check the dashboards" scores 0 |
| 4 | `!` Threshold & baseline discipline | Defines the comparison window and what it compares *against*; not bare absolute numbers |
| 5 | Surface coverage | Covers the paths that actually break, not just the happy-path service metrics |
| 6 | `!` Evidence binding | Every claim in the output must carry a query result, timestamp, and entity ID. Unsourced assertions are forbidden by the skill itself |
| 7 | Degraded mode | Says what to do when a data source is down, a tag is missing, or coverage is partial |
| 8 | `!` Action safety | Read-only by default; any write, restart, or rollback is gated on explicit human confirmation |
| 9 | Inconclusive path | The skill can return "not enough signal" instead of being forced into a binary |
| 10 | `!` Verdict discipline | Output ends in a decision + owner + next action, not a summary paragraph |
| 11 | Token economy | Progressive disclosure; no dumped runbooks, no repeated boilerplate, no restating tool docs |
| 12 | Maintainability | No hardcoded hostnames, entity IDs, dates, or one-team assumptions that rot in a quarter |

**Every score below 2 needs a citation** — a quoted snippet or line number from the
target. A finding you cannot cite is a finding you invented, and inventing findings to
justify a rewrite is the single worst outcome of this skill. Delete uncitable findings
before scoring.

If the target is an SRE release-verification or observability-check skill, read
`references/sre-check-failure-catalog.md` **before scoring checks 3–5 and 9**. It lists
the specific ways these skills produce confident false GOs. Skip it for non-operational
skills.

## Step 2 — Gate

Apply in order; first match wins.

| Verdict | Condition |
|---|---|
| **REWRITE** | Total < 14, **or** two or more `!` checks scored 0 |
| **PATCH** | Total 14–19, **or** exactly one `!` check scored 0 at any total |
| **KEEP** | Total ≥ 20 and no `!` check scored 0 |

The gate is not a suggestion. A skill scoring 21 does not get a rewrite because the
rewrite would be prettier. Prettier is not a finding.

## Step 3 — Produce exactly one output

### KEEP — hard cap, roughly 12 lines

```
VERDICT: KEEP — <score>/24

This skill is in good shape. A rewrite would cost more than it returns.

Holding up well: <two specifics, each citing a line or section>
Weakest point: <one specific, with the one-line fix, or "none material">

No rewrite produced. Re-run this audit if <the one condition that would change the answer —
e.g. the toolchain changes, or the skill starts producing false GOs in practice>.
```

Then **stop**. Do not append a v2 "just in case." Do not offer to write one. Do not
list the other eleven checks. The value of this path is that it is cheap.

### PATCH — surgical edits only

Open with the score line and the failing checks in a compact table. Then give **1–5**
edits, each as an exact find/replace against the target's real text:

```
Edit 2/4 — fixes check #6 (evidence binding)
FIND:    Summarize the health of the release.
REPLACE: For each signal, report: metric name, query used, value, comparison window,
         and entity ID. If a value could not be retrieved, write UNAVAILABLE and the
         reason. Never characterize a signal you did not query.
```

No full file. No restructuring. If you find yourself wanting to reorder the whole skill,
you picked the wrong verdict — go back to the gate and check your scores.

### REWRITE — earn the "significantly different"

First read `references/rewrite-blueprint.md`, then produce, in this order:

1. **Design delta** (a short table): what structurally changed and which failing check
   each change fixes. This comes *before* the new skill so the user can reject the
   architecture before reading 200 lines of it.
2. **The v2 skill**, as files.
3. **Migration note**: what breaks for existing users, and how to revert.
4. **Three test prompts** phrased the way the team actually talks, plus what a correct
   run looks like for each.

A rewrite must make **at least two structural changes** from this list, not just
rewording:

- Change the control flow — linear prose → gated phases with explicit stop conditions.
- Change the output artifact — free-form summary → a fixed decision record with a
  data contract.
- Invert to evidence-first — collect and pin all signals before any interpretation.
- Split by progressive disclosure — move depth into reference files loaded on demand.
- Add a determinism layer — a script or fixed query set replacing model judgment.
- Add a negative path — degraded mode, inconclusive verdict, or abort condition.

**Self-check before delivering**: if the v2 says the same things in nicer words, it is
not a rewrite. Downgrade to PATCH and ship the edits instead. Also compare line counts —
if v2 is meaningfully longer *and* the failing checks did not include a coverage gap,
you have added bloat, not rigor. Cut it back.

## Stop conditions

Stop and report what you have if any of these hit:

- The target could not be read → say so, ask once, stop.
- The target is not a skill (it's a runbook, a doc, a prompt fragment) → say which it is
  and what it would take to make it a skill. Do not audit it against a skill rubric.
- You have completed one audit pass → deliver. There is no second pass unless the user
  asks. Iterating alone burns tokens and drifts toward rewriting for its own sake.
- The user asked only "is this good?" → answer the gate verdict and the score. Nothing else.

## Notes on tone

Write findings the way a good reviewer talks: name the line, name the consequence,
name the fix. "Check 4 scores 1: the skill compares the 5-minute post-deploy error rate
to a 24-hour average, so a Monday 9am deploy will look degraded every time" beats
"baselines could be improved."
