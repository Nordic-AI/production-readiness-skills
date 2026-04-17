# Contributing

Thanks for your interest. This library improves by deliberate, testable contributions. Read this before opening a PR.

## What we accept

- **New skills** that fill a genuine coverage gap in production readiness.
- **Extensions to existing skills** — new categories, sharper heuristics, additional language / framework coverage.
- **Worked example findings** — these are disproportionately valuable, and we want more.
- **Fixes** — incorrect citations (wrong article number, wrong CWE), stale regulation references, typos, broken links.
- **Tooling** — better validator, better CI checks, better local dev ergonomics.

## What we don't accept (without discussion first)

- Changes to the core framework (severity rubric, scope tiers, finding schema, conventions). These affect every skill — open an issue first.
- Branding / promotional content in skills.
- Skills that duplicate existing coverage — extend instead.
- Pseudo-compliance claims (e.g. "ISO 27001 compliance skill" — we review controls, we don't certify).

## Adding a new skill

1. **Open an issue first.** Describe the gap, the scope tier distinctions, and a rough list of categories. Avoid duplicating an existing skill's surface.
2. **Copy the template** from [`docs/skill-template.md`](docs/skill-template.md) into `skills/<your-skill-name>/SKILL.md`.
3. **Read** [`docs/CONVENTIONS.md`](docs/CONVENTIONS.md). The skill must reference, not re-state, the conventions.
4. **Claim a finding ID prefix** that's unique across the library. Update the table in `docs/CONVENTIONS.md` §4 and `schemas/finding.schema.json`.
5. **Fill in the review surface.** Organize by category. Each category should have: what to check, heuristics / tools, common anti-patterns.
6. **Write at least 3 worked example findings** conforming to `finding.schema.json`. Real code snippets, realistic severities, realistic remediations. Examples are how Claude learns the shape of good findings.
7. **Add delegation** in `skills/production-readiness/SKILL.md` — insert your skill in the correct position in the orchestrator's delegation sequence, with rationale.
8. **Update `README.md`** skill catalog table.
9. **Run validation locally** (see below).
10. **Open a PR.** Describe the gap the skill addresses and the scope tiers it targets most.

## Extending an existing skill

- Prefer adding a new category to creating a new skill.
- If adding cross-language coverage (e.g. adding Ruby heuristics to an existing skill), group them under a clearly-labeled subsection.
- Bump the skill's `metadata.version` in frontmatter per SemVer (see `docs/CONVENTIONS.md` §11).

## Frontmatter requirements

Every `SKILL.md` must start with:

```yaml
---
name: <kebab-case, matches directory name>
description: <one paragraph, specific about triggers and coverage>
license: Apache-2.0
metadata:
  version: <SemVer>
  id_prefix: <PREFIX>
---
```

- `name` must match the directory name and may only contain lowercase letters, numbers, and hyphens (Claude Code's skill loader enforces this).
- `description` is the primary routing signal — be specific about what triggers invocation.
- `license` should be `Apache-2.0` (library convention).
- `metadata.version` starts at `0.1.0` for new skills; increment per SemVer.
- `metadata.id_prefix` is the finding ID prefix (registered in `docs/CONVENTIONS.md` §4).

Claude Code's supported skill-frontmatter keys include `name`, `description`, `license`, `metadata`, plus a few routing controls. Anything outside that set is flagged by the IDE — we use `metadata` for library-specific extensions.

## Output schema

All findings conform to [`schemas/finding.schema.json`](schemas/finding.schema.json). The CI validator parses every `### Example N` block in your skill and validates against the schema. Fix examples until they pass.

## Local validation

We ship a lightweight validator. From repo root:

```bash
# Python 3.10+ required
python scripts/validate_skills.py
```

It checks:
- Every `skills/<name>/SKILL.md` has valid frontmatter with required fields.
- `name` in frontmatter matches directory name.
- Finding ID prefix in example findings matches the one registered in `CONVENTIONS.md`.
- Example findings parse as YAML and validate against `finding.schema.json`.
- Internal links resolve.
- `description` is not empty and not a single word.

The same runs in CI (`.github/workflows/validate-skills.yml`) on every PR.

## Style

- **Be direct.** Skills are read by Claude, which parses markdown. Short imperative sentences beat flowery prose.
- **Ground advice in evidence.** "Flag if there's no timeout" is useful. "Think about reliability" is not.
- **Cite authoritatively.** Regulation articles must be correct; CWE / CVE / RFC / OWASP ASVS references must be real and current. If unsure, omit.
- **EU-first on compliance, stack-agnostic on everything else.** We welcome region-specific additions to `compliance-check/frameworks.yaml` and language-specific additions to other skills.
- **No emoji in skills.** They don't improve routing and add noise to the rendered output.
- **No absolute "production-ready" claims.** Skills produce findings; they never certify.

## Review criteria

PRs are reviewed on:

1. **Coverage correctness** — does it actually catch the problem it claims to catch?
2. **No false promises** — does it over-claim what it detects?
3. **Scope-tier sensitivity** — does it punish prototypes or under-demand from scalable systems?
4. **Evidence discipline** — can a developer act on the finding, or is it too abstract?
5. **Schema conformance** — does every example validate?
6. **Does not duplicate** existing skills or conflict with the library's conventions.

## Reporting security issues in the skills themselves

If you find a skill that could lead Claude to take a destructive action (wrong auto-remediation, missing confirmation gate, etc.), open a private security advisory on the repo rather than a public issue.

## License

By contributing, you agree that your contributions are licensed under Apache License 2.0 (see [`LICENSE`](LICENSE)).
