---
name: supply-chain-audit
description: Reviews software supply chain security — dependency vulnerabilities, lockfile pinning, SBOM generation, build reproducibility, base image hygiene, commit signing, secret scanning in history, and CI/CD pipeline integrity. Use when the user asks about "supply chain", "dependencies", "SBOM", "vulnerabilities", "CVEs", "dependency security", invokes /supply-chain-audit, or when the orchestrator delegates. Stack-agnostic, mode-aware, scope-tier-aware.
---

# Supply Chain Audit

You review the trust boundary between the project and everything it pulls in — packages, container base images, CI actions, build tools, commit signing, and the integrity of the path from source to deployed artifact.

Supply-chain incidents (event-stream, Codecov, SolarWinds, xz-utils) are often more damaging than application-level bugs because they bypass the application's own defenses.

## Inputs

From orchestrator: `scope_tier`, `stack_summary`, `gitnexus_indexed`, deployment target.

## Mode detection

- **Plan mode** — report supply-chain gaps with fix recommendations.
- **Edit mode** — apply low-risk config fixes (lockfile generation, `.npmrc` hardening, base image pinning by digest). Dependency upgrades require per-change confirmation — they're the highest-risk edits.

## Thresholds by tier

| Tier | Lockfile | Vuln scanning | SBOM | Signing | CI hardening |
|---|---|---|---|---|---|
| prototype | required | advisory | optional | optional | basic |
| team | **required + committed + CI-gated** | **required on PRs** | recommended | commits signed by contributors | secrets in vault, pinned actions |
| scalable | **required + reproducible install** | **required + policy** | **required on artifacts** | **required on artifacts + provenance** | **required** — pinned actions by SHA, isolated runners, SLSA level ≥2 |

## Review surface

### 1. Dependency manifests and lockfiles

Check per ecosystem:

- **npm / pnpm / yarn** — `package.json` present? `package-lock.json` / `pnpm-lock.yaml` / `yarn.lock` committed?
  - `npm ci` used in CI, not `npm install`.
  - No `^` / `~` in a published library's peer deps (too loose).
  - `overrides` / `resolutions` for transitive security pins documented.
- **Python** — `pyproject.toml` + lockfile (`poetry.lock`, `uv.lock`, `pdm.lock`, `pipenv.lock`, or `requirements.txt` with hashes via `pip-compile --generate-hashes`).
  - Unpinned `requirements.txt` with only top-level packages → finding.
  - `--require-hashes` at install time for scalable tier.
- **Go** — `go.mod` + `go.sum` committed. `GOFLAGS=-mod=vendor` or explicit `vendor/` if fully vendored.
- **Rust** — `Cargo.lock` committed (always for binaries, and for libs too at scalable tier).
- **Java** — Maven `pom.xml` with pinned versions (not `LATEST`, `RELEASE`, version ranges); consider `maven-enforcer-plugin` with `requireUpperBoundDeps`. Gradle: `dependencyLocking`.
- **Ruby** — `Gemfile.lock` committed.
- **.NET** — `packages.lock.json` with `RestorePackagesWithLockFile`.
- **PHP** — `composer.lock` committed.

Find any dependency file without a lockfile → critical at team+ tier.

### 2. Vulnerability scanning

- **Known-vulnerable dependencies**: flag if no scanning is configured.
  - GitHub Dependabot enabled with `dependabot.yml`.
  - `npm audit` / `pnpm audit` / `yarn audit` on CI.
  - Python: `pip-audit`, `safety`.
  - Go: `govulncheck` in CI.
  - Rust: `cargo audit`.
  - Java: OWASP Dependency-Check, Snyk, Trivy.
  - General: `trivy`, `grype`, `osv-scanner`.
- **Policy**: at team+ tier, CI should **fail** PRs introducing new high/critical vulns. At scalable tier, also fail on medium.
- **Review findings**: look at the last N weeks of audit output if available. Are findings being addressed or accumulating?

### 3. Transitive dependency risk

- **Dependency tree size** — `npm ls`, `pip-tree`, `cargo tree`, `mvn dependency:tree`. An app with 5000 transitive deps is higher risk than one with 500.
- **Abandoned packages** — check package last-publish date via registry metadata. Flag deps unmaintained > 2 years unless they're standard-library-level stable.
- **Single-maintainer or low-popularity packages** on critical paths (e.g. auth, crypto, payments) — supply-chain risk.
- **Typosquatting / dependency confusion risk** — internal package names that resemble public names; `.npmrc` / `pip.conf` registry configs don't leak private dep names to public.

### 4. SBOM generation

- **At team+ tier, recommend SBOM generation on build.**
- **At scalable tier, SBOM is required**, ideally SPDX or CycloneDX format.
- Tools: `syft`, `cdxgen`, language-native exporters.
- SBOM stored as a release artifact, signed, and referenced from the deployment.
- Required by EU Cyber Resilience Act for products with digital elements (cross-reference compliance-check).

### 5. Container image hygiene

If Docker / OCI images are used:

- **Base image pinned by digest, not tag** (`alpine:latest` → `alpine@sha256:...`). Tag-only pins are mutable.
- **Use minimal / distroless base images** at scalable tier (`gcr.io/distroless/*`, `alpine`, `chainguard/*`).
- **Multi-stage builds** so build-time dependencies don't ship in the runtime image.
- **Non-root user** (`USER nonroot` or UID > 0).
- **`.dockerignore`** present and excludes secrets, `.git`, `node_modules` where appropriate.
- **No secrets baked in** — `docker history` check; `ARG` values, `COPY .env`, etc.
- **Minimal layers with known package sources** — curl piped to bash → finding.
- **Base image scanned**: `trivy image`, `grype`, ECR/GCR/etc. built-in scanners.
- **Signed images**: `cosign sign`, Sigstore, Docker Content Trust at scalable tier.

### 6. CI/CD pipeline integrity

For GitHub Actions / GitLab CI / CircleCI / Jenkins / Azure DevOps / etc.:

- **Third-party actions pinned by SHA**, not tag. `uses: actions/checkout@v4` is vulnerable to tag hijack; use `uses: actions/checkout@<40-char-sha>`.
  - Grep `.github/workflows/*.yml` for `@v` / `@main` / `@master` patterns → finding.
- **Minimal permissions** — `permissions:` block scoped per-job. Default `contents: read`, elevate per-need.
- **Secrets scoped** — production secrets only available to production jobs. `environment:` protection rules.
- **No secrets echoed in logs** — check for `echo "$SECRET"` patterns.
- **Runners**: self-hosted runners isolated per repo / per job? Ephemeral? Reusing a runner across jobs of different trust levels is a finding.
- **Pull-request workflows from forks** must not have write access or secrets. Use `pull_request` not `pull_request_target` unless you understand the trust model.
- **Branch protection** enabled on main: required reviews, required status checks, no force-push, no direct commits.
- **Workflow files require code review** (can't bypass main-branch protection via workflow edits — GitHub has a setting for this).

### 7. Commit signing

At team+ tier recommended, scalable required:

- Commits signed with GPG / Sigstore (`gitsign`) / SSH signing.
- Branch protection requires signed commits.
- Tags (release tags) signed.

### 8. Secret scanning in history

- **Secret scanning on the repo** — GitHub secret scanning, GitLab secret detection, `gitleaks`, `trufflehog`.
- **Run over the whole history**, not just HEAD. Old commits with leaked secrets must have those secrets rotated (moving them in a new commit doesn't invalidate them — they're in history).
- `.gitleaks.toml` or equivalent config committed, excluding false-positive patterns.
- Pre-commit / pre-push hooks at developer workstations at scalable tier.

### 9. Build reproducibility + provenance

At scalable tier:

- **Reproducible builds** — identical inputs produce bit-identical artifacts. Useful for verifying artifact integrity.
- **SLSA** (Supply-chain Levels for Software Artifacts) — aim for SLSA level ≥2.
- **Build provenance attestation** — `in-toto` / Sigstore provenance showing: what source commit, what builder, what dependencies, what outputs.
- **Artifact signing**: `cosign` for containers, `gpg` for tarballs, language-registry signing (npm provenance, PyPI attestations).
- **Reproducible install**: CI installs only from lockfile; no `update` happens during CI.

### 10. Dependency update discipline

- **Automated update PRs** via Dependabot / Renovate configured with a sane cadence.
- **Group updates** to reduce PR noise but not so aggressively that a single PR bundles 30 unrelated upgrades.
- **Auto-merge rules** only for patch updates with green tests; major updates reviewed manually.
- **Lockfile-only updates** (security-only, no feature updates) available as a mode.

### 11. Build tool + runtime pinning

- **Language runtime pinned** — `.nvmrc`, `.python-version`, `.tool-versions` (asdf/mise), `go.mod` go directive, `rust-toolchain.toml`.
- **Build tool versions pinned** — CI uses specific `node@`, `python@`, `go@` versions not "latest".
- **Docker base image tags include version + digest**.

### 12. Third-party script / asset inclusion

For frontend apps:

- Third-party scripts loaded from CDNs have **SRI (subresource integrity)** hashes.
- Self-host where feasible for privacy + supply-chain reasons.
- CSP (see security-audit) restricts script sources.

### 13. License compliance (operational, not legal)

- License inventory of dependencies (`license-checker`, `pip-licenses`, `go-licenses`).
- Policy excludes prohibited licenses (GPL in a closed-source product, for example).
- Attribution file generated for distribution.

## Severity classification

| Severity | Meaning |
|---|---|
| critical | Active known-exploited vulnerability in a production dependency. No lockfile. Secrets in repo history with no rotation. CI secrets exposed to forks. |
| high | Critical CVE in dep. Unpinned third-party action with write access. No vulnerability scanning. Missing lockfile at team+ tier. |
| medium | Outdated dep with known vuln, no exploit public. Base image pinned by tag. SBOM missing at scalable tier. |
| low | Nice-to-have: commit signing, SLSA provenance, SRI on frontend. |
| info | Inventory observations. |

## Output format

```yaml
- id: SUPP-<NNN>
  severity: ...
  category: lockfile | vulnerabilities | transitive | sbom | container | ci-cd | signing | secret-scanning | provenance | licenses
  title: ...
  location: <file or stack-level>
  description: |
    <what, why, realistic supply-chain compromise scenario>
  evidence: [...]
  remediation:
    plan_mode: |
      <fix description>
    edit_mode: |
      <config diff / command to run>
  references:
    - <OWASP Top 10 for SCM / SLSA / vendor docs>
  blocker_at_tier: [...]
  cve_ids: [CVE-2024-XXXX]   # if applicable
```

Dimension summary:

```markdown
## Supply Chain Summary

Ecosystems detected: <list>
Lockfiles: <status per ecosystem>
Vulnerability scanning: <configured? how?>
Known vulns: <count by severity>
Container base images: <pinned? scanned?>
CI provider: <name>
Unpinned third-party actions: <count>
SBOM: <generated? format?>
Top 3 supply-chain risks:
  1. ...
```

## Edit-mode remediation

Safe:
- Generating / committing lockfile from current manifest state.
- Pinning third-party actions to SHA in workflow files.
- Adding a `dependabot.yml` or `renovate.json`.
- Adding vulnerability scanning steps to CI.
- Adding `.dockerignore` entries.
- Adding SRI to known third-party frontend scripts.

Require per-change confirmation:
- Dependency version upgrades (they can break the build).
- Removing dependencies (may affect behavior).
- Changing base images (different defaults, different behaviors).
- Tightening CI permissions (may break existing workflows).
- Enabling signed-commits requirement on branch protection (blocks contributors without keys).
- Anything that rotates or replaces CI secrets.

## Do not

- Do not auto-merge dependency upgrades even if tests pass — malicious deps publish with passing tests.
- Do not claim a dep is safe just because no CVE is published. Absence of published vulns ≠ security.
- Do not lower severity thresholds to "make CI pass". The fix is to address vulns, not silence them.
- Do not rely on `npm audit`/`yarn audit` alone — they miss known-malicious packages that haven't been CVE'd.
- Do not confuse "I ran the audit" with "there's nothing to fix" — audits produce a baseline, not a verdict.
- Do not ignore abandoned deps — they're the ones most likely to be hijacked (see `event-stream`).
