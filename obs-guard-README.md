# obs-guard

A Claude Code plugin that raises the observability and MR points from the
release-readiness skill **while the code is being written**, instead of after.

It is not a skill. Nothing invokes it, nobody remembers to run it, and it has no
model context cost when nothing fires.

## What it does

After every `Write`, `Edit`, or `MultiEdit`, a small Python script looks at **only the
text that was just written** and compares it against `rules/rules.json`. If something
matches, it returns a short note that Claude sees next to the tool result, so the fix
gets folded into the work in progress. If nothing matches, it prints nothing.

Guardrails against annoyance, in the order they apply:

| Guardrail | Default |
| --- | --- |
| Scans only newly written text, never the repo | always |
| Excluded paths (tests, generated, target, vendor) | `config.exclude_globs` |
| Same rule, same file, once per session | always |
| Notes per single edit | `max_notes_per_edit`: 2 |
| Notes per session, then fully silent | `max_notes_per_session`: 6 |
| Per-edit opt out — put `obs-guard:ignore` in the change | always |
| Blocks a tool call or fails a turn | never — the script cannot exit non-zero |
| End-of-session one-liner | `emit_session_summary`, set `false` to remove |

## Install (developer, one time)

The plugin has no dependencies beyond `python3`. If `python3` is missing the hook
no-ops silently.

**Option A — personal scope, no marketplace:**

```bash
cp -r obs-guard ~/.claude/skills/obs-guard
```

It loads on the next session as `obs-guard@skills-dir`. Verify with
`claude plugin list` and `/hooks`.

**Option B — committed to the repo, whole team:** publish it in your internal plugin
marketplace and install with `--scope project`, which writes to the repo's
`.claude/settings.json` so everyone who clones it gets it.

Confirm it is live: `claude plugin validate ./obs-guard`, then `/hooks` should list a
`PostToolUse` entry sourced from `Plugin Hooks`.

## Set up (SRE, one time)

The shipped `rules/rules.json` is a **seed**, not the real rule set. Derive the real one
from the existing release-readiness skill:

```
/obs-guard:sync-rules /path/to/release-readiness/SKILL.md
```

That command reads the skill, splits its checks into what is decidable at edit time and
what genuinely needs live telemetry, runs each candidate regex across the repo to reject
noisy ones, and rewrites `rules/rules.json`. Re-run it whenever the release skill changes.

It also prints the checks it could **not** convert. Those stay in the release skill —
that list is the honest scope boundary between the two tools.

## Tune it

Everything is in `rules/rules.json`. To silence one rule, set `"enabled": false` on it
rather than deleting it, and keep the reason next to it.

If a rule fires on legacy code all over the repo, that is the rule's fault, not the
developer's. Disable it and treat it as backlog.

## Test a rule without a session

```bash
echo '{"session_id":"t1","tool_name":"Write","tool_input":{"file_path":"/tmp/A.java","content":"try { x(); } catch (Exception e) { }"}}' \
  | CLAUDE_PLUGIN_ROOT=$(pwd) python3 scripts/check.py
```

Empty output means no rule fired. JSON output is what Claude would see.

## Rollout that works

1. Sync the rules against one repo you know well. Read the disabled-for-noise list.
2. Install it yourself for a week. Count how often it fires and whether the note was
   right. Cut anything that was wrong twice.
3. Give it to two developers who already use Claude Code. Ask one question: did it ever
   interrupt you for nothing.
4. Only then offer it to the team, and only as personal scope. Project scope is the
   step after it has earned trust.

## What it does not do

It does not verify anything about a running system: no traffic arrival, no error-rate
baseline, no consumer lag, no saturation trend, no per-instance skew. Those need a
deploy and live telemetry, and they remain the release-readiness skill's job. obs-guard
only removes the subset that never needed to wait that long.
