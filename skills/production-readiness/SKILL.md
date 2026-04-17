---
name: production-readiness
description: Orchestrates a full production-readiness review of an application. Use when the user asks "is this production-ready", "audit my app", "what's missing before we ship", "prepare this for launch", or when they invoke /production-readiness. Triages scope, jurisdiction, and stack, then delegates to the 8 specialist audit skills (security, compliance, test-coverage, reliability, observability, supply-chain, data-protection, scalability) and aggregates their findings into a single go / no-go report.
---

# Production Readiness Orchestrator

You are the entry point for a full production-readiness review. Your job is to **scope the project correctly**, **delegate to the right specialist skills**, and **aggregate their findings into a single actionable report**. You do not perform the audits yourself — each specialist skill is better at its dimension than you would be.

## When to run

Trigger when the user:
- Explicitly invokes `/production-readiness`
- Asks whether an app is "ready for production", "ready to ship", "ready to launch"
- Asks for a general audit without specifying a dimension
- Asks what's "missing" before going live

If the user asks about a specific dimension (e.g. "audit my auth"), hand off directly to that specialist skill instead of running the full orchestrator.

## Mode detection

Determine the current mode before anything else:

- **Plan mode** — you can read but not edit. Produce the full audit report with severity-ranked findings and described remediations. Do not attempt to apply fixes.
- **Edit mode** — after producing the audit report, offer to apply remediations. Ask the user whether to fix everything at a given severity level or walk through them one by one. Risky changes (migrations, dependency upgrades, auth flow changes, anything that affects production behavior on deploy) always require explicit per-change confirmation.

State the detected mode at the top of the run so the user can correct you.

## Step 1 — scoping

Ask the user these questions in a single batched prompt. Keep it short. Do not skip this step even if you think you can infer answers from the repo — the user's intent matters more than what the code suggests.

```
Before I run the review, I need to scope it:

1. **Scope tier** — how critical is this?
   - prototype: pre-PMF, internal, no real user data
   - team: production, real users, one team owns it
   - scalable: multi-team, high availability, regulated / payment-critical
2. **Jurisdiction** — where does the product operate, and where do users live?
   (EU-first, but I'll adapt. Tell me countries or "unknown".)
3. **Data sensitivity** — does the app process: PII, payment data, health data,
   children's data, biometric data, or none of the above?
4. **Industry / sector** — finance, health, critical infrastructure, government,
   education, e-commerce, consumer, B2B SaaS, other?
5. **Deployment target** — cloud (which?), on-prem, hybrid, edge, mobile client?
6. **Anything I should skip?** — dimensions already covered by another team,
   or out of scope for this review.
```

Wait for answers before proceeding. If the user says "you decide" or gives partial answers, use sensible defaults (team tier, EU jurisdiction, general consumer SaaS) and state them explicitly so they can be corrected.

## Step 2 — stack + repo discovery

Once scope is set, gather the technical context:

1. Read the project's root manifest(s): `package.json`, `pyproject.toml`, `go.mod`, `Cargo.toml`, `pom.xml`, `Gemfile`, `composer.json`, etc. If none exist, ask the user what the stack is.
2. Note the test framework, CI config (`.github/workflows`, `.gitlab-ci.yml`, `Jenkinsfile`, etc.), container setup (`Dockerfile`, `docker-compose*.yml`, `k8s/`), and IaC (`terraform/`, `pulumi/`).
3. Detect whether GitNexus is available and the repo is indexed:
   - Call `mcp__gitnexus__list_repos` (if the MCP is connected).
   - If the repo is indexed, note it. Specialist skills will use GitNexus tools for blast-radius and PII analysis.
   - If GitNexus is available but the repo is not indexed, ask the user whether to index it (non-blocking — skills work without it).
4. Identify the primary entry points: HTTP handlers, CLI commands, background workers, scheduled jobs, message consumers. A brief map here helps every downstream specialist skill.

Produce a one-paragraph **Project context** summary before delegating. Include: stack, scope tier, jurisdiction, data sensitivity, deployment, and GitNexus availability.

## Step 3 — delegation

Invoke the specialist skills in this order (the order matters — later skills benefit from findings in earlier ones):

1. **`security-audit`** — covers the broadest surface, often surfaces cross-cutting issues the other skills then contextualize.
2. **`compliance-check`** — consumes the security findings to determine which are regulatory-blocking vs. merely technical-debt. Uses jurisdiction from scoping.
3. **`data-protection-audit`** — overlaps with both security and compliance; runs after them so it can cross-reference and dedupe.
4. **`supply-chain-audit`** — dependency and build-chain surface.
5. **`test-coverage`** — enforces 90% line + branch and demands integration + stress/load tests appropriate to the scope tier.
6. **`reliability-audit`** — error handling, retries, idempotency, timeouts.
7. **`observability-audit`** — logging, metrics, tracing, alerting, runbooks.
8. **`scalability-review`** — runs last because its thresholds are the most scope-tier-sensitive.

For each specialist skill:

- Pass the project context, scope tier, jurisdiction, and data sensitivity as inputs.
- Run the skill via the `Skill` tool.
- Collect its structured findings (see Output Format below).
- Do not let one skill's failure stop the run — if a skill errors or returns nothing useful, note it and continue.

If the user asked for a subset (e.g. "skip scalability"), honor that.

## Step 4 — dedupe and cross-reference

Different skills will flag overlapping issues (e.g. "passwords stored in plaintext" is security, compliance, and data-protection). Merge duplicates:

- Pick the most specific severity (highest) across overlapping findings.
- Concatenate categories from all contributing skills in a `categories:` list.
- Cite all relevant references (OWASP + GDPR Art. X + CWE-Y).

## Step 5 — aggregate report

Produce a single unified report with this structure:

```markdown
# Production Readiness Report

**Project:** <name>
**Scope tier:** <prototype|team|scalable>
**Jurisdiction:** <...>
**Data sensitivity:** <...>
**Reviewed:** <ISO date>
**Mode:** <plan|edit>

## Verdict

**Go / No-Go for <tier> tier:** <GO | NO-GO | GO WITH CAVEATS>

<one-paragraph executive summary — the 3 things that most matter>

## Blocking findings (must fix before launch at this tier)

<findings where severity ≥ blocker_at_tier threshold>

## Recommended findings (should fix soon)

<findings below blocker threshold but still meaningful>

## Advisory findings (nice to have)

<low severity + info>

## Dimension summaries

### Security (N findings: X critical, Y high, Z medium)
<short summary + link to each finding by id>

### Compliance — GDPR / NIS2 / etc.
<...>

<... one section per dimension audited>

## Remediation plan

<grouped by severity, with an effort estimate if possible — small/medium/large>

## Out of scope / skipped

<anything the user asked to skip, plus anything the skills couldn't assess>
```

## Step 6 — remediation (edit mode only)

If in edit mode and the report contains fixable findings:

1. Group remediations by severity.
2. Ask the user how to proceed: apply all criticals? walk through one-by-one? generate a single PR with everything?
3. Apply fixes in dependency order — security and supply-chain first (they often unblock other fixes), then the rest.
4. For each applied fix, re-run the relevant skill's verification step to confirm the finding is resolved.
5. Stop and re-confirm before any of:
   - Dependency major-version upgrades
   - Database schema migrations
   - Auth flow changes
   - Deletion of existing code paths
   - Changes to CI / deployment config
   - Changes that affect >10 files

## Scope-tier thresholds (reference)

| Tier | Blocking threshold | Test coverage | Stress testing | Runbooks |
|---|---|---|---|---|
| prototype | critical only | advisory | not required | not required |
| team | high+ | 90% line+branch required | basic smoke load required | recommended |
| scalable | medium+ | 90% line+branch + integration required | realistic stress + chaos required | required |

Each specialist skill receives the tier and applies its own dimension-specific thresholds. Do not override them — if a specialist marks something as non-blocking at the current tier, trust it.

## Do not

- **Do not skip scoping.** Even an "obvious" project benefits from explicit scope. The tier setting alone determines half the findings' severity.
- **Do not invent findings.** If a specialist skill missed something you notice, add a note in the report but attribute it to yourself (orchestrator), not to the specialist.
- **Do not batch risky edits.** Even in edit mode, anything affecting production deploy behavior needs explicit confirmation per change.
- **Do not silently ignore GitNexus.** If the MCP is available but the repo isn't indexed, surface it — the user may want richer analysis.
- **Do not conflate plan mode with edit mode.** Re-check the mode before doing anything that writes to the filesystem.
