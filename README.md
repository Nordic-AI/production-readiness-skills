# Nordic AI Production Readiness Skills

A library of [Claude Skills](https://docs.claude.com/en/docs/claude-code/skills) for evaluating and remediating production-readiness of software applications. EU-first on compliance, stack-agnostic on everything else.

## What this library does

It turns Claude Code (or any Skill-aware Claude client) into a production-readiness reviewer that can:

- **Audit** — in plan mode, produce a structured report of gaps across security, compliance, testing, reliability, observability, supply chain, data protection, and scalability.
- **Remediate** — in edit mode, propose and apply fixes for each finding, scoped to severity and project tier.

The skills are composable. Invoke the orchestrator `/production-readiness` to run a full review, or invoke a single audit skill (e.g. `/security-audit`) to focus on one dimension.

## Installation

### As a Claude Code plugin

```bash
# Clone into a plugin location Claude Code watches
git clone https://github.com/nordic-ai/production-readiness-skills.git ~/.claude/plugins/nordic-ai-production-readiness
```

Restart Claude Code. The skills will appear under `/production-readiness`, `/security-audit`, etc.

### As user-scoped skills

```bash
# Copy each skill into ~/.claude/skills/
cp -r skills/* ~/.claude/skills/
```

### As project-scoped skills

```bash
# Inside your project
mkdir -p .claude/skills
cp -r /path/to/this/repo/skills/* .claude/skills/
```

## The 9 skills

| Skill | Purpose |
|---|---|
| [`production-readiness`](skills/production-readiness/SKILL.md) | Orchestrator — scopes the project, then delegates to the relevant audit skills and aggregates findings. |
| [`security-audit`](skills/security-audit/SKILL.md) | OWASP Top 10, authN/Z, secrets, input validation, crypto, session management, security headers. |
| [`compliance-check`](skills/compliance-check/SKILL.md) | Jurisdiction discovery → GDPR / NIS2 / EU AI Act / DORA / HIPAA / CCPA / sector-specific controls. |
| [`test-coverage`](skills/test-coverage/SKILL.md) | Enforces 90% line + branch coverage, demands integration and stress/load testing beyond unit tests. |
| [`reliability-audit`](skills/reliability-audit/SKILL.md) | Error handling, retry + backoff, timeouts, idempotency, graceful degradation, transaction boundaries. |
| [`observability-audit`](skills/observability-audit/SKILL.md) | Structured logging, RED/USE metrics, distributed tracing, alerting, runbooks. |
| [`supply-chain-audit`](skills/supply-chain-audit/SKILL.md) | Dependency vulnerability scanning, SBOM, lockfile pinning, signature verification, base image hygiene. |
| [`data-protection-audit`](skills/data-protection-audit/SKILL.md) | Encryption at rest / in transit, PII classification, retention, residency, key management, backups. |
| [`scalability-review`](skills/scalability-review/SKILL.md) | Scope-aware review: DB indexing, N+1, caching, connection pooling, horizontal scaling, rate limiting. |

## How it works

Each audit skill is designed around four principles:

1. **Mode-aware.** In plan mode, skills only report. In edit mode, they propose and apply remediations (with confirmation on risky changes).
2. **Scope-aware.** The orchestrator classifies the project as one of three tiers — `prototype`, `team`, `scalable` — and passes that tier down. A prototype doesn't need the same controls as a payment-critical scalable system, and findings are graded accordingly.
3. **Jurisdiction-aware.** `compliance-check` asks targeted questions up front (EU presence? EU-resident data subjects? regulated industry?) and maps answers to the applicable frameworks. EU-first, but other jurisdictions are surfaced when relevant.
4. **GitNexus-aware.** When the [GitNexus MCP](https://github.com/nordic-ai/gitnexus) is available and the repo is indexed, skills use the knowledge graph for blast-radius analysis, route discovery, PII field discovery, and API impact. Skills degrade gracefully when GitNexus is unavailable.

## Output format

Every audit skill emits findings in this shape:

```yaml
finding:
  id: SEC-001
  skill: security-audit
  severity: critical | high | medium | low | info
  category: authentication
  title: "JWT signature verification disabled"
  location: "src/auth/middleware.ts:42"
  description: >
    <what>, <why it matters>, <what attacker/regulator would do with this>
  evidence:
    - code snippet
    - GitNexus impact (optional)
  remediation:
    plan_mode: <how to fix, described>
    edit_mode: <diff or patch to apply>
  references:
    - <OWASP / CWE / regulation / RFC>
  blocker_at_tier: [team, scalable]    # which scope tiers treat this as blocking
```

The orchestrator aggregates all findings into a single report with a top-level go / no-go per scope tier.

## Scope tiers

| Tier | Description | Default thresholds |
|---|---|---|
| `prototype` | Pre-PMF, internal-only, no real user data. | Critical findings blocking only. Test coverage advisory. |
| `team` | Production with real users, single team owns it. | All high+ findings blocking. 90% coverage required. |
| `scalable` | Multi-team, high availability, regulated / payment-critical. | All medium+ findings blocking. 90% coverage + stress tests + runbooks required. |

Tiers are set during orchestrator scoping or can be passed explicitly: `/production-readiness --tier=scalable`.

## Contributing

Contributions welcome. See [CONTRIBUTING.md](CONTRIBUTING.md) (TBD).

When adding or modifying a skill, keep the four design principles above intact, and ensure the `description` in frontmatter accurately reflects when the skill should be routed to.

## License

Apache License 2.0 — see [LICENSE](LICENSE).

## Authors

[Nordic AI](https://github.com/nordic-ai)
