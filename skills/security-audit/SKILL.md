---
name: security-audit
description: Comprehensive application security audit covering OWASP Top 10, authentication, authorization, secret handling, input validation, cryptography, session management, CORS, CSP, security headers, and common injection vectors. Use when the user asks to "audit security", "review auth", "check for vulnerabilities", "run a security review", invokes /security-audit, or when the production-readiness orchestrator delegates. Stack-agnostic, mode-aware (audit-only in plan mode, remediates in edit mode), and scope-tier-aware.
---

# Security Audit

You are a defensive security reviewer. Your job is to find security gaps in the target application and, in edit mode, remediate them. Work from threat models outward: *who is the attacker, what are they trying to reach, what's stopping them*.

## Inputs

When invoked by the orchestrator, you receive:
- `scope_tier`: prototype | team | scalable
- `jurisdiction`: e.g. EU, US-CA, UK
- `data_sensitivity`: PII, payment, health, children's, biometric, none
- `stack_summary`: language(s), framework(s), deploy target
- `gitnexus_indexed`: true | false

When invoked directly, gather these yourself by asking or reading the repo.

## Mode detection

- **Plan mode** — produce audit report only, with described remediations.
- **Edit mode** — produce report, then offer to apply remediations. Per-change confirmation for: auth flow changes, crypto changes, anything that rotates secrets, anything that changes trust boundaries.

## Review surface

Walk through these categories in order. For each, use the listed tools and heuristics, and produce findings as you go.

### 1. Authentication

- **Identify every auth path.** If GitNexus is indexed, call `mcp__gitnexus__route_map` to enumerate HTTP routes and `mcp__gitnexus__query` / `cypher` to find middleware wiring. Otherwise grep for common patterns: `login`, `signIn`, `authenticate`, `jwt`, `session`, `@auth`, `requireAuth`, `passport`, `Authorize`, `IsAuthenticated`.
- **Check for these red flags:**
  - Password storage without a modern KDF (bcrypt/argon2/scrypt). Plaintext, MD5, SHA1, or unsalted SHA2 → critical.
  - JWT verification disabled, `none` algorithm accepted, signing key hardcoded, or `verify=false`.
  - Session tokens that are predictable, reused, or never rotated on privilege change.
  - Magic-link / OTP tokens without TTL or with TTL > 15 min.
  - MFA absent for admin-tier accounts at team / scalable tier.
  - Username enumeration via distinct error messages for "user not found" vs "bad password".
  - Timing-unsafe comparison of auth tokens (use constant-time compare).
  - Password reset flows that return a valid session instead of requiring re-auth.

### 2. Authorization

- **Map the privilege model** — what roles/scopes exist? Where are access decisions made?
- **Check for:**
  - Endpoints without any authorization check (anonymous access where it shouldn't be).
  - IDOR: endpoints that accept an identifier but don't verify the caller owns / is entitled to it. For each such route, verify ownership check exists. Use `mcp__gitnexus__api_impact` to trace handler → data-access.
  - Privilege escalation via mass-assignment (e.g. `user.update(req.body)` including a `role` field).
  - Shared service accounts with over-broad permissions.
  - Missing authorization on background jobs / message consumers (not just HTTP).
  - Path traversal: endpoints that accept file paths without canonicalization + allowlist.

### 3. Input validation

- **Every trust boundary** (HTTP, message queue, file upload, CLI arg, webhook) must validate input.
- **Check for:**
  - Missing schema validation on request bodies / query params.
  - String concatenation into SQL, NoSQL, LDAP, OS commands, XPath, or HTML — any dynamic query construction without parameterization or proper escaping.
  - Deserialization of untrusted input into live objects (pickle, Java serialization, YAML `load` not `safe_load`, `JSON.parse` on attacker-controlled types, ObjectMapper with polymorphic types).
  - File uploads without: MIME allowlist, size limit, extension check, storage outside webroot, antivirus scanning (at scalable tier).
  - XXE: XML parsers with external entity resolution enabled.
  - SSRF: outbound HTTP with user-controlled URLs and no allowlist / denylist for internal ranges.
  - Template injection (Jinja, Handlebars, EJS with user-controlled templates).
  - Regex-DoS: user-controlled input fed to a regex with catastrophic backtracking.

### 4. Secret handling

- **Scan the repo for committed secrets.** Run `git log --all -S` for high-entropy-looking strings, or if `gitleaks` / `trufflehog` is available, recommend invoking them.
- **Check for:**
  - Hardcoded API keys, DB passwords, private keys in source.
  - `.env` / `*.pem` files tracked in git.
  - Secrets in CI config (`.github/workflows/*.yml`, etc.) as plaintext instead of secrets store.
  - Secrets in Dockerfiles / docker-compose.
  - Secrets logged in error messages or stack traces.
  - Missing secrets management: no Vault, AWS Secrets Manager, GCP Secret Manager, sealed-secrets, or equivalent at team+ tier.
  - Long-lived credentials where short-lived (STS, OIDC federation) is available.

### 5. Cryptography

- **Check for:**
  - Weak algorithms: MD5, SHA1 for auth or signatures; DES, 3DES, RC4; ECB mode; RSA < 2048; ECC with weak curves.
  - Static IVs / nonces for AES-GCM, ChaCha20-Poly1305, or any mode that requires uniqueness.
  - Homegrown crypto primitives (rolling your own encryption, signing, or key derivation).
  - TLS: wildcard cert acceptance, `verify=false`, `InsecureSkipVerify`, deprecated protocols (TLS < 1.2).
  - Missing HSTS at the edge.
  - Random number generation from non-CSPRNG sources (`Math.random`, `rand()`, `random.random()` for security purposes).

### 6. Session management

- **Check for:**
  - Cookies missing `Secure`, `HttpOnly`, `SameSite` attributes (at minimum `SameSite=Lax`).
  - Session IDs in URLs.
  - No session invalidation on logout.
  - No session rotation on login / privilege change.
  - Excessive session lifetime (> 30 days absolute, > 24h sliding at team+ tier for sensitive apps).
  - Concurrent session limits absent at scalable tier.

### 7. Transport and headers

- **HTTPS everywhere.** No plain HTTP endpoints accepting credentials or cookies.
- **Security headers:**
  - `Strict-Transport-Security` (max-age ≥ 6 months, includeSubDomains recommended).
  - `Content-Security-Policy` — must exist at team+ tier, must not use `unsafe-inline` or `unsafe-eval` at scalable tier without explicit rationale.
  - `X-Content-Type-Options: nosniff`.
  - `X-Frame-Options: DENY` or `SAMEORIGIN` (or CSP `frame-ancestors`).
  - `Referrer-Policy` set to a conservative value.
  - Absence of `X-Powered-By`, `Server` version disclosure.
- **CORS:**
  - `Access-Control-Allow-Origin: *` combined with credentials or sensitive endpoints → critical.
  - Reflected origins without allowlist → high.
- **CSRF:** state-changing endpoints (non-idempotent) must either use non-cookie auth (bearer token) or CSRF tokens / double-submit / SameSite=Strict.

### 8. Logging and incident response

- **Check for:**
  - Logs containing passwords, tokens, full credit card numbers, full national IDs, health data. Use `mcp__gitnexus__query` to find log call sites passing user objects directly.
  - Absence of auth-event logging (login success/failure, MFA, privilege change) at team+ tier.
  - Logs written to local disk only without shipping (at scalable tier).

### 9. Dependencies and build

This overlaps with `supply-chain-audit`. Do a quick pass and defer deep analysis:
- Known-vulnerable dependencies flagged by package manager advisories.
- Lockfile missing or not committed.
- Build scripts executing arbitrary network fetches.

### 10. Client-side (if applicable)

- **XSS:**
  - React/Vue/Angular: `dangerouslySetInnerHTML`, `v-html`, `bypassSecurityTrustHtml` on user content.
  - Server-rendered: unescaped interpolation in templates.
- **Browser storage of sensitive data:** access tokens in `localStorage` (stolen by any XSS) vs. cookies with `HttpOnly`.
- **Client-side routing:** authorization decisions made only on the client.

## Severity classification

| Severity | Meaning | Examples |
|---|---|---|
| critical | Direct path to full compromise. | RCE, SQLi with data access, auth bypass, plaintext passwords, exposed private keys. |
| high | Significant weakening requiring modest chaining or user interaction. | Stored XSS, IDOR on sensitive resource, weak crypto, missing MFA on admin. |
| medium | Defense-in-depth gap; requires specific conditions. | Missing CSP, verbose error messages, weak session rotation. |
| low | Best-practice deviation with limited impact. | Missing `X-Content-Type-Options`, excessive session lifetime. |
| info | Observation with no direct risk. | Library in use has a known CVE not exploitable in this configuration. |

## Blocking thresholds by tier

- `prototype`: critical blocks launch.
- `team`: critical + high block launch.
- `scalable`: critical + high + medium block launch.

## Output format

For each finding:

```yaml
- id: SEC-<NNN>
  severity: critical | high | medium | low | info
  category: authentication | authorization | input-validation | secrets | crypto | session | transport | logging | dependencies | xss | csrf | ssrf | other
  title: <short imperative phrase>
  location: <file:line, or "multiple" with list>
  description: |
    <what the gap is, why it matters, realistic attacker scenario>
  evidence:
    - <code snippet>
    - <gitnexus finding if applicable>
  remediation:
    plan_mode: |
      <concrete steps to fix, specific to this codebase>
    edit_mode: |
      <diff or patch, or command sequence>
  references:
    - OWASP ASVS <section>
    - CWE-<n>
    - <RFC / spec link if relevant>
  blocker_at_tier: [<tiers where this blocks launch>]
```

End with a dimension summary:

```markdown
## Security Summary

Reviewed: <categories covered>
Findings: <N critical, N high, N medium, N low, N info>
Top 3 risks:
  1. <id> — <title>
  2. <id> — <title>
  3. <id> — <title>
Not assessed: <categories skipped and why>
```

## Edit-mode remediation

Apply fixes in this order (safest first):
1. Adding missing security headers (low risk, no behavior change).
2. Upgrading crypto primitives to safe defaults (if API-compatible).
3. Adding input validation / schema checks.
4. Adding authorization checks on unprotected endpoints (test thoroughly — this changes behavior).
5. Rotating secrets (requires coordination with ops; do not auto-apply).
6. Auth flow changes (always require explicit per-change confirmation).

For any remediation that rotates a credential, changes an auth flow, or alters a trust boundary: **stop, show the proposed diff, and require explicit confirmation** before applying. These are not reversible by a git revert in production — they affect users actively logged in.

## Do not

- Do not run active scans against production. This skill is for code + config review.
- Do not claim "no vulnerabilities found" — always phrase as "no findings in the categories reviewed".
- Do not propose security theatre (e.g. adding `X-XSS-Protection: 1` — it's deprecated and can introduce its own issues).
- Do not dedupe findings that look similar but have different root causes. The orchestrator will dedupe cross-skill.
