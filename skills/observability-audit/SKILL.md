---
name: observability-audit
description: Reviews logging, metrics, distributed tracing, error reporting, alerting, and operational runbooks. Checks that the system emits the right telemetry at the right granularity, that signals are actionable, and that on-call has what it needs. Use when the user asks about "observability", "logging", "metrics", "tracing", "monitoring", "alerting", invokes /observability-audit, or when the orchestrator delegates. Stack-agnostic, mode-aware, scope-tier-aware.
license: Apache-2.0
metadata:
  version: 0.1.0
  id_prefix: OBS
---

# Observability Audit

You review whether the running system can be understood from the outside — by an SRE staring at dashboards at 3am, by a developer triaging a bug report, by an auditor tracing a regulatory incident. Observability is not about having logs; it's about being able to answer questions you didn't know you'd ask.

## Inputs

From orchestrator: `scope_tier`, `stack_summary`, entry points, `gitnexus_indexed`.

## Mode detection

- **Plan mode** — report observability gaps with concrete additions recommended.
- **Edit mode** — apply code-level instrumentation. Runbooks and dashboard configs can be scaffolded but require the user to hook them into their actual observability stack.

## Thresholds by tier

| Tier | Structured logs | Metrics | Traces | Alerts | Runbooks |
|---|---|---|---|---|---|
| prototype | advisory | optional | optional | advisory | not required |
| team | **required** — structured + correlation IDs | **required** — RED per endpoint | recommended | required on critical errors + SLO burn | recommended for critical flows |
| scalable | **required** — structured + correlation + sampling discipline | **required** — RED + USE + business KPIs | **required** — OTel traces across services | **required** — SLO-based, on-call rotation | **required** per critical flow |

## Review surface

### 1. Logging

#### A. Format

- **Structured logging required at team+ tier.** JSON or logfmt, not plain text. Look for `winston`, `pino`, `zap`, `zerolog`, `logrus`, `log/slog`, `structlog`, `loguru`, SLF4J + Logback JSON encoder, Serilog JSON formatter, etc.
- Check for `console.log` / `print` / `fmt.Println` used for production logging — almost always an anti-pattern.
- Log lines must be **parseable as a single record** (no multi-line logs without proper framing; stack traces in a single field).

#### B. Correlation

- Every request/job/message must have a **correlation ID** (trace-id / request-id / correlation-id) threaded through all logs for that unit of work.
- Check middleware / interceptors for `X-Request-ID` propagation.
- Async boundaries (queue publish → consume) must carry correlation IDs in message metadata.
- User context (tenant-id, user-id) logged on authenticated requests — with PII discipline (see data-protection-audit overlap).

#### C. Levels and discipline

- Consistent level usage: `ERROR` for actionable failures, `WARN` for degraded-but-OK, `INFO` for business events, `DEBUG` for investigation-only.
- `ERROR` logs should be rare and each one should correspond to something that *should* page someone or be investigated. "Error log storms" devalue the signal.
- `INFO` at every function entry/exit is a smell — too noisy.
- Log levels configurable at runtime (without redeploy) at scalable tier.

#### D. Content

- Every `ERROR` log includes: the triggering event, relevant IDs, the error chain / stack trace, enough context to reproduce.
- Log messages are **searchable** — use stable event names (e.g. `"user.signup.failed"`) not free-form English strings that you'd need a regex to match.
- No PII / secrets logged (cross-reference security-audit + data-protection-audit). Grep for common patterns: `password`, `token`, `secret`, `authorization`, full card numbers, national IDs.
- Errors include their *cause* — wrapped / chained, not just the top-level message.

#### E. Shipping

- At team+ tier, logs must be shipped off the host. Local file only → a finding.
- Central aggregation: Elasticsearch / OpenSearch / Loki / Datadog / Splunk / CloudWatch Logs / GCP Logging / Sentry.
- Retention matches compliance requirements (check with compliance-check findings).

### 2. Metrics

#### A. Coverage — the RED method (request-oriented)

Every HTTP endpoint / RPC / queue consumer should expose:
- **R**ate — requests per second.
- **E**rrors — error count (per error class at scalable tier).
- **D**uration — histogram of latencies (not just mean — use histograms for p50/p95/p99).

Check for metrics libraries: `prom-client`, `micrometer`, `prometheus/client_golang`, `opentelemetry-metrics`, StatsD clients, Datadog tracer metrics, CloudWatch metrics.

#### B. Coverage — the USE method (resource-oriented, scalable tier)

For each shared resource (CPU, memory, DB connection pool, cache, queue):
- **U**tilization
- **S**aturation
- **E**rrors

Many are provided by infra / runtime metrics, but **application-level USE** for things like DB connection pool (checked-out vs. pool-size) often missing — flag.

#### C. Business KPIs

At team+ tier, critical business events should be metrics, not just logs: signups, orders placed, payments succeeded/failed, etc. Enables business-aware alerting.

#### D. Cardinality discipline

- **No unbounded label values.** `user_id` as a Prometheus label → cardinality explosion. User IDs belong in traces/logs, not metric labels.
- IDs, free-form paths, and error messages are common high-cardinality offenders.
- Label sets should be small and bounded (method, status_code, route_template, etc.).

### 3. Distributed tracing

- Required at scalable tier (system with >1 service).
- **OpenTelemetry** is the current standard. Check for `@opentelemetry/*`, `opentelemetry-api` (Python/Java), `go.opentelemetry.io/otel`, etc.
- Check:
  - Tracer initialized and exported to a collector (Jaeger / Tempo / Honeycomb / Datadog / Grafana Cloud / CloudWatch X-Ray).
  - HTTP client + server instrumented (auto-instrumentation or manual).
  - DB client instrumented.
  - Queue producer/consumer propagates context (traceparent carried in message attributes).
  - Custom spans added for significant business logic (not just auto-instrumented boundaries).
  - Sampling strategy: always-on for errors, tail-based or head-based for successful requests with representative rate.

### 4. Error reporting

- Dedicated error tracker at team+ tier: Sentry, Rollbar, Honeybadger, Bugsnag, Datadog Error Tracking, Google Error Reporting, New Relic Errors.
- Errors deduplicated and fingerprinted.
- Source maps uploaded for minified frontend code.
- Release tagging for regression detection.
- User / tenant context attached (scrubbed of PII).
- Unhandled promise rejections / uncaught exceptions wired to the reporter.

### 5. Alerting

- At team+ tier, critical errors should alert — paging someone when something actionable breaks.
- Alerting on **symptoms**, not causes (alert on "latency p99 > SLO", not on "CPU > 80%").
- **SLO-based alerting** at scalable tier: burn-rate alerts on error budget (multi-window multi-burn-rate).
- Alert fatigue check: how many alerts fire per week? How many are actionable? If >20% are ignored or auto-resolved, it's a finding.
- **Runbooks linked from alerts** — every alert should have a runbook link.
- On-call rotation exists and is documented at scalable tier.
- Dependencies alerted on: external service degradation surfaces before user impact.

### 6. Dashboards

- Per-service "golden signal" dashboard (rate, errors, latency, saturation).
- Per-critical-flow dashboard (user-journey view, not infra view).
- No dashboards with only infra metrics — you also need product-level views.
- Dashboards version-controlled (e.g. Grafana-as-code via Jsonnet/Terraform) at scalable tier.

### 7. Audit logging

Overlaps with security-audit + compliance-check. Reliability-relevant aspects:
- Audit events are logged to a **separate stream** from operational logs — different retention, different access controls.
- Append-only / tamper-resistant storage for audit logs.

### 8. Profiling

At scalable tier:
- Continuous profiling (Pyroscope, Pprof, Parca) for CPU / memory / block / mutex profiles.
- Memory leak detection (heap growth monitoring).

### 9. Runbooks

At team+ tier (critical flows) and scalable (always):

- Each critical alert → a runbook.
- Runbook contains: symptom, likely causes, immediate mitigation steps, escalation path, verification after mitigation, postmortem template reference.
- Stored alongside the code, not on a wiki that drifts.
- Tested in game days at scalable tier.

### 10. Incident response wiring

- Alerts route to a paging system (PagerDuty, OpsGenie, VictorOps, Grafana IRM).
- Incident tooling: channel creation, status page updates, stakeholder notification — automated or at least scripted.
- Postmortem process exists and produces actionable follow-ups that are tracked.

## Severity classification

| Severity | Meaning |
|---|---|
| critical | Incidents will be invisible — no way to know the system is broken (no error tracking, no alerts, no central logs). |
| high | Incidents detectable but debugging severely impaired — no correlation IDs, no structured logs, no traces. |
| medium | Specific blind spots (e.g. queue consumer not traced, business KPI not a metric). |
| low | Best-practice gaps (e.g. missing runbook for non-critical path). |
| info | Observations on telemetry cost or noise. |

## Output format

```yaml
- id: OBS-<NNN>
  severity: ...
  category: logging | metrics | tracing | errors | alerts | dashboards | runbooks | profiling
  title: ...
  location: <file or stack-level>
  description: |
    <what, why, 3am-debugging scenario>
  evidence: [...]
  remediation:
    plan_mode: |
      <what to add, where>
    edit_mode: |
      <code instrumentation diff or config scaffold>
  references:
    - <SRE book / OTel docs / vendor docs>
  blocker_at_tier: [...]
```

Dimension summary:

```markdown
## Observability Summary

Logging stack: <detected libs>
Metrics stack: <detected libs>
Tracing stack: <detected libs>
Error tracker: <detected>
Alerting: <routed to?>
Runbooks: <count discovered>

Top 3 blind spots:
  1. ...
```

## Example findings

### Example 1 — Unbounded cardinality on Prometheus label

```yaml
- id: OBS-002
  severity: high
  category: metrics
  title: "http_requests_total uses user_id as a label — cardinality explosion"
  location: "src/metrics/http.ts:14"
  description: |
    `http_requests_total` is defined with a `user_id` label alongside
    `method` and `route`. With ~400k distinct users, the metric
    produces ~400k × N_routes × N_methods active time series per
    scrape — at the current rate of signup (~300/day), time series
    count grows monotonically. Prometheus storage and alerting rule
    evaluation cost scale linearly with this; the ingestion pipeline
    has already shown p95 scrape latency rising 4x over the last
    quarter, correlated with user growth. High cardinality is also
    expensive on managed backends (Datadog, New Relic).
  evidence:
    - |
      // src/metrics/http.ts:14
      export const httpRequests = new Counter({
        name: 'http_requests_total',
        labelNames: ['method', 'route', 'status', 'user_id'],
      });
  remediation:
    plan_mode: |
      1. Remove `user_id` from Prometheus labels.
      2. Per-user behavior belongs in logs or traces (or a separate
         OLAP system), not metrics labels.
      3. If per-tenant / per-region slicing is needed, use tenant-id
         (bounded) or a coarse geographic bucket, not unbounded IDs.
      4. Audit other metrics for similar unbounded labels.
    edit_mode: |
      Safe: drop the label. Adjust any dashboards / alerts filtering
      on user_id in metrics (likely none — they were always noisy).
  references:
    - "Prometheus docs — 'Naming things: Don't use labels for cardinality'"
  blocker_at_tier: [team, scalable]
```

### Example 2 — Production logging via console.log

```yaml
- id: OBS-008
  severity: medium
  category: logging
  title: "31 files use console.log for production logging in src/"
  location: "multiple"
  description: |
    A grep finds 31 call sites using `console.log` / `console.error` in
    `src/`. These emit plaintext lines that can't be parsed as
    structured records, carry no correlation ID, and mix with other
    operational output. The observability story for any incident
    involving those paths is: SSH into the pod, `grep -i error
    /var/log/app`, hope the timestamp frames match. The project
    already includes `pino` for structured logging in a few files;
    the refactor has stalled.
  evidence:
    - "grep -rn 'console\\.' src | wc -l → 31"
    - "src/services/payments.ts, src/jobs/*.ts most affected"
  remediation:
    plan_mode: |
      1. Replace console.log with the existing `logger` (pino).
      2. Ensure request context (requestId, userId-hash, tenantId) is
         threaded into the logger via `logger.child({...})`.
      3. Add an ESLint rule (`no-console`) with an allowlist for CLI
         entry points only.
    edit_mode: |
      Safe. Script-assisted replacement; review before commit.
  references:
    - "Twelve-Factor App — XI. Logs"
  blocker_at_tier: [team, scalable]
```

### Example 3 — Correlation ID not propagated across async boundary

```yaml
- id: OBS-015
  severity: high
  category: logging
  title: "Queue consumers start fresh request IDs, breaking trace continuity"
  location: "src/workers/email_consumer.ts:7"
  description: |
    HTTP requests generate an `X-Request-ID` and threading it into the
    logger is handled by middleware. When the HTTP handler enqueues a
    job to the email queue, the request ID isn't serialized into the
    message body. The consumer starts a fresh UUID, making trace
    continuity from "user action → email sent" impossible. Every
    non-trivial incident (e.g. "why didn't user X get their receipt?")
    requires a manual timestamp + user-id forensic join that takes
    minutes per case.
  evidence:
    - |
      // src/routes/orders.ts — enqueues without passing request-id
      await queue.add('send-receipt', { orderId, userId });
      // src/workers/email_consumer.ts:7 — generates fresh id
      const requestId = uuid();
  remediation:
    plan_mode: |
      1. Include request-id (and trace-context if OTel is in use) as a
         message attribute when enqueuing.
      2. In consumers, adopt the received request-id into the logger
         context instead of minting a new one.
      3. For OTel: use the propagation API to carry trace context into
         the message and extract in the consumer (both BullMQ and AWS
         SQS OTel instrumentations support this).
    edit_mode: |
      Safe. Touches all queue enqueue + consume sites (grep shows 8
      call sites). Add a shared helper to avoid drift.
  references:
    - "OpenTelemetry — Messaging semantic conventions"
  blocker_at_tier: [team, scalable]
```

## Edit-mode remediation

Safe to apply:
- Replacing `console.log` / `print` with structured logger calls.
- Adding request-ID middleware + threading through contexts.
- Adding RED metrics to HTTP handlers (route-level middleware).
- Adding OTel auto-instrumentation setup.
- Scrubbing PII from existing log sites (require confirmation per site — might be removing intended debugging).

Require confirmation:
- Changing log level defaults.
- Adding sampling (affects cost + visibility).
- Installing a new observability SDK (adds dependency, may require credentials).
- Removing log statements (even noisy ones — someone might depend on them).

Scaffold only (don't attempt to wire up):
- Alert rules (need vendor-specific config).
- Dashboards (need data source).
- Runbooks (need ops context).

## Do not

- Do not recommend logging every function entry/exit. Noise without value.
- Do not propose high-cardinality metric labels (user_id, session_id, request_id).
- Do not alert on causes (CPU, memory) without symptom correlation — they produce false pages.
- Do not treat "we have Sentry" as adequate observability. Error tracking ≠ metrics ≠ traces ≠ logs.
- Do not enable PII logging even for "debugging" — compliance + security don't stop at "it was for debug".
- Do not confuse auto-instrumentation with full coverage. Custom spans for business-critical paths are still needed.
