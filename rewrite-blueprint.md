# Rewrite blueprint

Read only after the gate returns REWRITE. This is the target architecture for v2 —
adapt it, don't transcribe it.

## The shape that works for operational check skills

The reason most check skills degrade is that they interleave collection and judgment.
The model reads one metric, forms an opinion, and then reads the rest through that
opinion. Splitting the phases removes that failure mode and makes the output auditable.

```
Phase 1 — Bind context      (what release, which build, which window, what else changed)
Phase 2 — Collect evidence  (run every check, record raw values, NO interpretation)
Phase 3 — Evaluate          (compare each value to its baseline, mark PASS/FAIL/UNAVAILABLE)
Phase 4 — Decide            (apply the stated verdict rules to the evaluation table)
Phase 5 — Emit              (fixed-format decision record)
```

Phase 2 must be explicitly instructed to record values without commentary. Phase 4 must
be a rule application, not a judgment call — the rules live in the skill, so two people
running it on the same data get the same verdict.

## Data contract

Give Phase 2 a fixed row shape. This is what makes the output diffable across releases
and what makes an unsourced claim structurally impossible:

```
signal | query_or_source | value | baseline_value | window | entity_id | status
```

`status` ∈ PASS / FAIL / UNAVAILABLE. `UNAVAILABLE` requires a reason. A row with a
value but no query is invalid and should be dropped rather than reported.

## Verdict rules

State them as rules, in the skill, before any run:

```
NO-GO / ROLLBACK  if any rollback-trigger signal is FAIL
NO-GO             if two or more FAIL in the same subsystem
INCONCLUSIVE      if any rollback-trigger signal is UNAVAILABLE
INCONCLUSIVE      if the new build received less than <N> requests in the window
GO                if all rollback-trigger signals PASS and the soak period completed
```

Name the rollback-trigger set explicitly. If everything is a trigger, nothing is.

## Progressive disclosure layout

```
skill-name/
├── SKILL.md                  phases, verdict rules, output format   (aim < 200 lines)
├── references/
│   ├── signals-<stack>.md    the query catalog per platform, read on demand
│   └── degraded-modes.md     what to do when a source is down
└── scripts/                  optional: fixed queries as executable, for determinism
```

Depth belongs in `references/`. SKILL.md holds the control flow and the rules, because
that is what has to be in context every single run. A 600-line SKILL.md that pastes an
entire query catalog inline pays that cost on every invocation for signals most runs
never touch.

## Output format for v2

Fixed template, no free prose above the verdict:

```
RELEASE CHECK — <service> <build> — <window>
VERDICT: GO | NO-GO | ROLLBACK | INCONCLUSIVE
Owner: <name/team>    Next action: <one imperative sentence>

Evidence
<the data-contract table>

Failures and unavailable signals
<one line each: what, why it matters, what to do>

Not checked
<explicit list — the coverage the run did not have>
```

The "Not checked" block matters more than it looks. It converts a silent coverage gap
into a stated limitation, which is the difference between an honest GO and a lucky one.

## Things not to add

- A "confidence: high/medium/low" field. It is a place to hide a guess. The verdict set
  already includes INCONCLUSIVE.
- Severity scoring on every signal. It invents precision that the data does not support.
- Remediation steps inside a verification skill. Link to the runbook; do not inline it.
- Personas, tone instructions, or a preamble about being a careful SRE. Costs tokens on
  every run and changes no output.
