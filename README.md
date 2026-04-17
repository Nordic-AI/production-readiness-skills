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

## The 12 skills

| Skill | Purpose |
|---|---|
| [`production-readiness`](skills/production-readiness/SKILL.md) | Orchestrator — scopes the project, then delegates to the relevant audit skills and aggregates findings. |
| [`security-audit`](skills/security-audit/SKILL.md) | OWASP Top 10, authN/Z, secrets, input validation, crypto, session management, security headers. |
| [`compliance-check`](skills/compliance-check/SKILL.md) | Jurisdiction discovery → GDPR / NIS2 / EU AI Act / DORA / PCI-DSS / HIPAA / CCPA / sector-specific controls. |
| [`ai-readiness`](skills/ai-readiness/SKILL.md) | AI/ML review — EU AI Act classification, evals, prompt injection defenses, RAG quality + security, hallucination handling, output filtering, human oversight, fairness, agent safety. |
| [`test-coverage`](skills/test-coverage/SKILL.md) | Enforces 90% line + branch coverage, demands integration, stress/load, and (where relevant) property-based tests. |
| [`reliability-audit`](skills/reliability-audit/SKILL.md) | Error handling, retry + backoff + jitter, timeouts, idempotency, graceful degradation, transaction boundaries, circuit breakers. |
| [`observability-audit`](skills/observability-audit/SKILL.md) | Structured logging, correlation IDs, RED/USE metrics, distributed tracing, alerting, runbooks. |
| [`supply-chain-audit`](skills/supply-chain-audit/SKILL.md) | Dependency vulnerability scanning, SBOM, lockfile pinning, signature verification, base image hygiene, CI-actions pinning. |
| [`data-protection-audit`](skills/data-protection-audit/SKILL.md) | Encryption at rest / in transit, PII classification + inventory, retention, residency, key management, backups. |
| [`accessibility-audit`](skills/accessibility-audit/SKILL.md) | WCAG 2.2 AA + EU Accessibility Act — semantic HTML, keyboard, ARIA, contrast, screen-reader compatibility, forms. |
| [`release-readiness`](skills/release-readiness/SKILL.md) | CI/CD quality, deployment strategy (rolling / blue-green / canary), rollback, migrations, feature flags, environment parity. |
| [`scalability-review`](skills/scalability-review/SKILL.md) | Scope-aware review — DB indexing, N+1, caching, connection pooling, horizontal scaling, rate limiting, pagination. |

## How it works

Each audit skill is designed around four principles:

1. **Mode-aware.** In plan mode, skills only report. In edit mode, they propose and apply remediations (with confirmation on risky changes).
2. **Scope-aware.** The orchestrator classifies the project as one of three tiers — `prototype`, `team`, `scalable` — and passes that tier down. A prototype doesn't need the same controls as a payment-critical scalable system, and findings are graded accordingly.
3. **Jurisdiction-aware.** `compliance-check` asks targeted questions up front (EU presence? EU-resident data subjects? regulated industry?) and maps answers to the applicable frameworks. EU-first, but other jurisdictions are surfaced when relevant.
4. **GitNexus-aware.** When the [GitNexus MCP](https://github.com/nordic-ai/gitnexus) is available and the repo is indexed, skills use the knowledge graph for blast-radius analysis, route discovery, PII field discovery, and API impact. Skills degrade gracefully when GitNexus is unavailable.

## Output format

All findings conform to a shared JSON Schema at [`schemas/finding.schema.json`](schemas/finding.schema.json). Minimum shape:

```yaml
- id: SEC-001
  severity: critical | high | medium | low | info
  category: authentication
  title: "JWT signature verification disabled"
  location: "src/auth/middleware.ts:42"
  description: >
    <what>, <why it matters>, <what attacker / regulator would do with this>
  evidence:
    - code snippet
    - GitNexus impact (optional)
  remediation:
    plan_mode: <how to fix, described>
    edit_mode: <diff or patch to apply>
  references:
    - <OWASP / CWE / regulation / RFC>
  blocker_at_tier: [team, scalable]
```

Each skill owns a finding ID prefix (`SEC`, `COMP`, `AI`, `A11Y`, `REL-R`, etc.) so findings stay attributable across the aggregate report. The orchestrator dedupes cross-skill overlaps and produces a single go / no-go verdict per scope tier.

## Scope tiers

| Tier | Description | Default blocking threshold |
|---|---|---|
| `prototype` | Pre-PMF, internal-only, no real user data. | `critical` only. |
| `team` | Production with real users, single team owns it. | `critical` + `high`. 90% coverage required. |
| `scalable` | Multi-team, high availability, regulated / payment-critical. | `critical` + `high` + `medium`. 90% coverage + stress tests + runbooks required. |

Tiers are set during orchestrator scoping or passed explicitly: `/production-readiness --tier=scalable`.

## Repository layout

```
.
├── skills/                 # the skills themselves, one directory each
├── docs/
│   ├── CONVENTIONS.md      # library-wide rules: mode, severity, schema, remediation, do-nots
│   └── skill-template.md   # starting point for new skills
├── schemas/
│   └── finding.schema.json # JSON Schema every finding must satisfy
├── scripts/
│   └── validate_skills.py  # frontmatter + example-finding validator
└── .github/workflows/      # CI — validator + markdownlint + yamllint
```

## Contributing

PRs welcome. Read [`CONTRIBUTING.md`](CONTRIBUTING.md) and [`docs/CONVENTIONS.md`](docs/CONVENTIONS.md) first. Run the validator locally before opening a PR:

```bash
pip install pyyaml jsonschema
python scripts/validate_skills.py
```

When authoring a new skill, copy the template from [`docs/skill-template.md`](docs/skill-template.md), claim a unique finding ID prefix in `docs/CONVENTIONS.md` §4 and in the skill's `metadata.id_prefix` frontmatter field, and include at least 3 worked example findings.

## License

Apache License 2.0 — see [LICENSE](LICENSE).

## Authors

[Nordic AI](https://github.com/Nordic-AI)
