# Shared Conventions

All audit skills in this library follow the rules below. Skill files reference this document rather than duplicating its contents. If you are authoring a new skill, read this first, then copy the template from [`docs/skill-template.md`](./skill-template.md).

## 1. Mode handling

Claude does not receive a direct "plan mode" vs "edit mode" signal. A skill must infer mode from context and, when unclear, **ask**:

```
Should I (a) produce an audit report only (plan mode), or
         (b) produce the report and apply remediations (edit mode)?
```

If the user's turn already includes edits or explicitly says "fix", assume edit mode. If it asks to "review" or "check", assume plan mode. When edit mode is active, **risky changes still require per-change confirmation** (see §5).

## 2. Severity rubric

All skills use this scale. Do not invent new levels.

| Level | Meaning |
|---|---|
| `critical` | Direct path to compromise, outage, data loss, or regulatory violation with active enforcement history. |
| `high` | Significant weakness that amplifies blast radius or requires only modest chaining. |
| `medium` | Defense-in-depth gap, best-practice deviation with realistic but conditional impact. |
| `low` | Minor deviation with limited real-world impact. |
| `info` | Observation — no action required, recorded for awareness. |

Skill-specific categories (e.g. `authentication`, `gdpr`, `n-plus-1`) are defined per skill, but severity is uniform.

## 3. Scope-tier blocking matrix

Scope tiers are set by the orchestrator (or the user directly). Each skill decides its own blocking thresholds *within* this frame:

| Tier | Description | Default blocking severity |
|---|---|---|
| `prototype` | Pre-PMF, internal, no real user data. | `critical` only. |
| `team` | Production, real users, one team. | `critical` + `high`. |
| `scalable` | Multi-team, HA, regulated / payment-critical. | `critical` + `high` + `medium`. |

A finding's `blocker_at_tier:` field lists the tiers in which it *blocks* launch. A finding can be `medium` severity but still blocker at `team` tier if the dimension warrants — each skill justifies this in its own section.

## 4. Output: finding schema

Every skill emits findings conforming to [`schemas/finding.schema.json`](../schemas/finding.schema.json). Minimum required fields:

```yaml
- id: <PREFIX>-<NNN>           # e.g. SEC-001, COMP-042, AI-013
  severity: critical | high | medium | low | info
  category: <skill-specific enum>
  title: <short imperative>
  description: |
    <what, why it matters, realistic exploitation / failure / enforcement scenario>
  blocker_at_tier: [prototype?, team?, scalable?]
```

Optional but encouraged:

```yaml
  location: <file:line, or "process-level" / "system-level" / "multiple">
  evidence:
    - <code snippet, config snippet, log sample, tool output>
  remediation:
    plan_mode: |
      <concrete steps to fix, specific to this codebase>
    edit_mode: |
      <diff, patch, or command sequence>
  references:
    - <OWASP / CWE / regulation + article / RFC / vendor doc>
  related_findings: [SEC-003, DATA-012]    # cross-skill dedup + context
  cve_ids: [CVE-2024-XXXX]                 # supply-chain findings
```

Each skill ends its output with a **dimension summary** (counts by severity, top 3 risks, not-assessed list). See skill files for the exact summary template.

### Finding ID prefixes

| Skill | Prefix |
|---|---|
| security-audit | `SEC` |
| compliance-check | `COMP` |
| test-coverage | `TEST` |
| reliability-audit | `REL` |
| observability-audit | `OBS` |
| supply-chain-audit | `SUPP` |
| data-protection-audit | `DATA` |
| scalability-review | `SCALE` |
| ai-readiness | `AI` |
| accessibility-audit | `A11Y` |
| release-readiness | `REL-R` |
| orchestrator (cross-cutting) | `ORCH` |

## 5. Remediation discipline (edit mode)

### Safe to apply without per-change confirmation

- Non-behavior-changing additions (headers, comments, type annotations).
- Tightening of defaults (narrower CORS, shorter TTLs, stricter validators) where the previous behavior was a clear vulnerability.
- Adding missing instrumentation (logs, metrics, traces) that can't break behavior.
- Adding missing tests (never removing or skipping existing tests to do so).

### Always require per-change confirmation

- **Anything irreversible by `git revert`**: secret rotation, key rotation, DB migration with backfill, destructive data operations.
- **Auth flow changes**: login, signup, session, MFA, password reset, token issuance — these affect users actively logged in.
- **Trust boundary changes**: adding/removing authorization checks, changing CORS allowlists, changing CSP.
- **Dependency upgrades** (especially majors) and removals.
- **CI/CD changes** — workflows, branch protection, signing requirements.
- **Feature flag flips** in production.
- **Changes affecting >10 files or crossing service boundaries.**

Present the diff, state why confirmation is required, wait for explicit approval.

## 6. GitNexus integration

When the GitNexus MCP is available AND the repo is indexed, skills use its tools to accelerate discovery (routes, PII fields, call graphs, blast-radius). Rules:

- Always **check first** (`mcp__gitnexus__list_repos`) before calling analysis tools.
- Always **degrade gracefully** — skills must work without GitNexus, using `grep`/`glob`/manifests.
- Never gate a finding on GitNexus — if GitNexus suggests an issue but static inspection can't confirm, record as `info` with a note recommending re-analysis after indexing.
- When indexed but stale, note the staleness; don't silently trust stale graph data.

## 7. Cross-skill referencing

Skills may reference each other's findings by `id` in `related_findings:`. The orchestrator dedupes and merges. Never copy another skill's finding verbatim — reference it.

When a skill *triggers* the need for another skill's check (e.g. data-protection needs GDPR article mapping from compliance-check), it notes this in its report and delegates via the orchestrator rather than duplicating the logic.

## 8. Universal do-nots

Every skill inherits these:

- **Do not claim compliance, security, or readiness as a binary verdict.** Say "no findings in the categories reviewed" — absence of detection is not absence of problems.
- **Do not silently loosen a ratchet.** Lowering a threshold, removing a test, loosening a validator, or widening a permission — never a fix. Always a finding.
- **Do not propose security / safety theatre.** Don't recommend deprecated controls (`X-XSS-Protection: 1`, SMS-only 2FA for high-risk) or checklist items that don't address the threat.
- **Do not treat tooling presence as adequacy.** "We have Sentry" ≠ observability. "We have SOC 2" ≠ security. "We have a test suite" ≠ test coverage.
- **Do not invent facts.** If you cite an article number, CVE, or RFC, it must be correct. If uncertain, cite the closest you know and flag the uncertainty.
- **Do not skip scoping.** Running audits without tier + jurisdiction + data-sensitivity context produces bad findings.
- **Do not leave `TODO: fix later` in code.** Either fix or record a finding.

## 9. Evidence discipline

Every non-trivial finding needs evidence. Accepted forms:
- Code snippet with file path + line numbers.
- Config snippet (same).
- Command output (e.g. `npm audit` JSON excerpt).
- GitNexus query result (cite the query).
- Directory listing where *absence* is the evidence (e.g. "no `.github/workflows/*.yml` files present").

Findings without evidence are `info` at best; they should rarely appear above `low`.

## 10. Uncertainty and limits

A skill must name what it **could not assess** and why — network isolation, missing tooling, out-of-scope user decision, insufficient access. This goes in the dimension summary's `Not assessed:` section. Silent gaps are worse than acknowledged ones.

## 11. Versioning

Each skill's frontmatter `metadata.version` field follows SemVer:

- **Patch** — typo / wording fixes, added examples.
- **Minor** — new findings categories, tightened thresholds with clear upgrade path.
- **Major** — changed finding ID prefix, changed output schema, removed categories.

Claude Code's supported skill-frontmatter keys are `name`, `description`, `license`, `metadata` (and a few others for routing control). We put `version` and `id_prefix` under `metadata` so they coexist cleanly with the Claude Code skill loader.

The orchestrator records each specialist skill's version in its aggregate report so past reports remain comparable.

## 12. Skill authoring checklist

New skills must:

1. Use the template at [`docs/skill-template.md`](./skill-template.md).
2. Frontmatter has `name`, `description`, `license: Apache-2.0`, `metadata.version` (SemVer), and `metadata.id_prefix`.
3. Declare a finding ID prefix unique across the library.
4. Reference these conventions — not re-state them.
5. Include at least 3 worked example findings.
6. Pass `python scripts/validate_skills.py` locally.
7. Be added to `README.md` skill catalog and orchestrator delegation order.

See [`CONTRIBUTING.md`](../CONTRIBUTING.md) for the full process.
