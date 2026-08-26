# SRE release / observability check — failure catalog

Read this before scoring checks 3 (signal specificity), 4 (threshold & baseline),
5 (surface coverage), and 9 (inconclusive path) on an operational skill.

Every item below is a way a release-check skill produces a **confident false GO** —
the failure that matters, because a false NO-GO only costs a delay while a false GO
costs an incident.

## Contents
1. Baseline and comparison errors
2. The silent-success traps
3. Surface gaps
4. Verdict and evidence failures
5. What a solid check skill actually specifies

---

## 1. Baseline and comparison errors

| Failure | Why it bites |
|---|---|
| Post-deploy window compared to a 24h or 7d **average** | Diurnal traffic makes every morning deploy look degraded and every 2am deploy look perfect. Compare to the same window on a prior comparable day, or to the pre-deploy window of equal length on the same day. |
| **Averages for latency** | Mean latency hides the tail that users and SLOs actually feel. Require p50/p95/p99, and require the same percentile on both sides of the comparison. |
| **Raw error counts** instead of a ratio | A deploy that halves traffic also halves error count. Errors must be per-request or per-transaction. |
| Fixed absolute thresholds with no owner | "Alert if CPU > 80%" is meaningless without knowing the normal range for that workload. Either derive the threshold from the baseline or cite where the number came from. |
| Observation window too short | A 2-minute check after deploy catches nothing that warms up: connection pools, JIT, cache fill, GC pressure, leaking handles. Require a stated soak period and say what it is bounded by. |
| Baseline window overlapping a prior incident or a prior bad deploy | Comparing to a degraded baseline makes degraded look normal. The skill should require checking whether the baseline window was clean. |

## 2. The silent-success traps

These are the ones that make a broken release look *perfect*:

- **No traffic-arrival check.** If routing, the ingress, or the API gateway never sent
  requests to the new version, every error-rate and latency panel is beautifully green
  because it is empty. The first check in any release verification should be "did the
  new version receive real traffic, and how much."
- **No version/build confirmation.** The skill checks health but never confirms which
  artifact is actually running. Healthy old code passes every test.
- **Aggregate hides per-instance skew.** One bad pod out of twelve barely moves the
  service-level average. Require a per-instance or per-pod breakdown of the top signals,
  or an explicit max-across-instances rather than an average.
- **Async paths not checked.** Synchronous request metrics can be flawless while messages
  pile up. Consumer lag, queue depth, dead-letter growth, and redelivery counts are
  where a broken consumer shows up first — nowhere else.
- **Saturation ignored.** Thread pools, connection pools, heap and GC time, file
  descriptors. A pool that is filling but not yet full shows zero errors right up to
  the moment it shows nothing but errors. Trend on saturation, not just breach.
- **Downstream and upstream unchecked.** The deployed service is fine; the thing it
  calls is now getting 3x the calls, or the caller is now timing out. Scope must include
  at least one hop in each direction.
- **No dependency-config check.** Certificate expiry, secret or credential rotation,
  changed connection strings, and pool sizing changes ship silently and fail later.

## 3. Surface gaps

A release-check skill should say explicitly which of these it covers and which it does
not. Silence on any of them is a coverage gap, not a design choice:

- Request path: rate, error ratio, latency percentiles, per-instance spread
- Async path: consumer lag, queue/topic depth, DLQ growth, redelivery, oldest-message age
- Runtime saturation: heap, GC pause, thread pool active/queued, connection pool in-use vs max
- Data layer: session count, wait events, lock contention, long-running queries, connection errors
- Platform: pod restarts, CrashLoopBackOff, OOMKills, readiness probe flaps, node pressure
- Edge: gateway error rates, quota/rate-limit rejections, TLS handshake failures, cert expiry
- Change context: what else deployed in the same window, and any open incident overlapping it
- Business/transaction level: at least one end-to-end transaction that proves the feature works

## 4. Verdict and evidence failures

- **Narrative output.** "Everything looks stable overall" is unfalsifiable and unactionable.
  The output must terminate in GO / NO-GO / ROLLBACK / INCONCLUSIVE, with the owner and
  the next action named.
- **No rollback trigger.** The skill says how to check but never states the condition that
  means roll back now. Define it before the deploy, not during the argument.
- **Forced binary.** With partial data the only honest answer is INCONCLUSIVE plus the
  specific missing signal. A skill that cannot say this will guess, and it will guess GO.
- **Unsourced claims.** Any signal characterized without a query result, a time range,
  and an entity identifier is a hallucination with good posture. The skill must forbid
  this in its own instructions, not just hope for it.
- **Remediation drift.** A verification skill that starts restarting things has exceeded
  its mandate and destroyed the evidence. Read-only by default; writes gated on a human.

## 5. What a solid check skill actually specifies

Score check 3 a 2 only if, for each signal, the skill names all of:

1. The metric or entity — precisely enough to run without guessing
2. The query, filter, or dashboard link — the literal thing to execute
3. The comparison window and the baseline it compares against
4. The threshold *and* where that threshold came from
5. What it means when the signal is unavailable

If any of those five are missing across most signals, it scores 1. If the skill mostly
says "review the relevant dashboards and confirm health," it scores 0.
