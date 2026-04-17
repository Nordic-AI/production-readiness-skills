# Skill Template

Starting point for a new skill in this library. To create a new skill:

1. Create a directory under `skills/` with a kebab-case name (e.g. `skills/my-new-skill/`).
2. Create `skills/my-new-skill/SKILL.md` by copying the body below.
3. Fill in the placeholders.
4. Add any supporting assets in the same directory (YAML lookups, pattern files, etc.).
5. Run `python scripts/validate_skills.py` from repo root.
6. Add the skill to [`README.md`](../README.md) catalog and the orchestrator's delegation list.

Follow the rules in [`CONVENTIONS.md`](./CONVENTIONS.md) and the PR process in [`../CONTRIBUTING.md`](../CONTRIBUTING.md).

---

## Template (copy the fenced block into `skills/<name>/SKILL.md`)

The frontmatter keys below are what Claude Code supports for skills: `name`, `description`, `license`, `metadata`. Keep `metadata.version` (SemVer) and `metadata.id_prefix` — the validator expects them.

````markdown
---
name: <skill-name-in-kebab-case>
description: <one paragraph. Be specific about trigger phrases ("audit X", "review Y", invokes /skill-name), what it checks, and routing hints for Claude. This field is the primary signal for skill routing — clarity beats brevity.>
license: Apache-2.0
metadata:
  version: 0.1.0
  id_prefix: <PREFIX>
---

# <Skill Title>

<One or two sentences framing what this skill does and the mental model it uses.>

This skill follows the library-wide rules in [`docs/CONVENTIONS.md`](../../docs/CONVENTIONS.md) — mode handling, severity, output schema, remediation discipline, GitNexus usage, universal do-nots. This file documents what's specific to this dimension.

## Finding ID prefix

`<PREFIX>` — see `CONVENTIONS.md` §4.

## Inputs

From orchestrator: `scope_tier`, `jurisdiction`, `data_sensitivity`, `stack_summary`, `gitnexus_indexed`, plus:
- <skill-specific input>

When invoked directly, gather via scoping questions.

## Tier thresholds

| Tier | <control 1> | <control 2> |
|---|---|---|
| prototype | advisory | optional |
| team | required | recommended |
| scalable | required + <stronger> | required |

## Review surface

### 1. <Category>

- <Check item>
- <Red flag>

### 2. <Category>

...

## Category enum (for findings)

- `<category-1>`
- `<category-2>`
- `<category-3>`

## Severity guidance

Severity uses the library rubric (`CONVENTIONS.md` §2). Skill-specific nuance:

| Level | What this skill treats as this severity |
|---|---|
| critical | <skill-specific examples> |
| high | ... |
| medium | ... |

## Example findings

At least three worked examples, conforming to [`finding.schema.json`](../../schemas/finding.schema.json).

### Example 1 — <short title>

```yaml
- id: <PREFIX>-001
  severity: <level>
  category: <from enum>
  title: <short imperative>
  location: <file:line>
  description: |
    <what, why, realistic scenario>
  evidence:
    - |
      <code or config snippet>
  remediation:
    plan_mode: |
      <described fix>
    edit_mode: |
      <diff or command>
  references:
    - <authoritative source>
  blocker_at_tier: [<tiers>]
```

### Example 2 — <short title>

```yaml
...
```

### Example 3 — <short title>

```yaml
...
```

## Dimension summary template

```markdown
## <Skill Name> Summary

<skill-specific metadata>

Findings: <N critical, N high, N medium, N low, N info>
Top 3 risks:
  1. <id> — <title>
  2. ...
Not assessed: <list with reasons>
```

## Edit-mode remediation guidance

Safe to apply:
- <change>

Require per-change confirmation:
- <change>

See `CONVENTIONS.md` §5.

## Skill-specific do-nots

In addition to the universal do-nots in `CONVENTIONS.md` §8:

- Do not <skill-specific anti-pattern>.
````
