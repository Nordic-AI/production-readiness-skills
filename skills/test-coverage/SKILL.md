---
name: test-coverage
description: Enforces a 90% line and branch coverage threshold and audits for meaningful integration, end-to-end, stress, and property-based tests beyond unit tests. Identifies critical paths that lack coverage, flags tests that pass without asserting, and in edit mode generates missing test scaffolds. Use when the user asks to "check test coverage", "audit tests", "are we tested enough", "add tests", invokes /test-coverage, or when the orchestrator delegates. Stack-agnostic, mode-aware, scope-tier-aware.
---

# Test Coverage Audit

You review the adequacy of automated testing. Coverage percentage is necessary but not sufficient — you also check *what* is covered, *how* it's covered, and *whether the tests actually assert meaningful behavior*.

## Inputs

From orchestrator: `scope_tier`, `stack_summary`, `gitnexus_indexed`, and critical-path map (entry points, HTTP handlers, workers, jobs).

## Mode detection

- **Plan mode** — produce coverage report with gap list.
- **Edit mode** — after report, offer to generate missing tests. Generate test scaffolds with meaningful assertions, not just `expect(thing).toBeDefined()`.

## Thresholds by tier

| Tier | Line | Branch | Integration tests | Stress/load | Property-based |
|---|---|---|---|---|---|
| prototype | advisory (aim 60%+) | advisory | optional | not required | optional |
| team | **90% required** | **90% required** | required for every critical path | basic smoke load (happy-path + 2× expected throughput) | recommended |
| scalable | **90% required** | **90% required** | required + contract tests between services | realistic stress + chaos + soak (24h+) | required for serialization / parsing / state machines |

"Critical path" = any code path that handles: authentication, authorization, payments, PII reads/writes, external data writes, anything invoked by a scheduled job or message consumer, anything with regulatory relevance.

## Step 1 — discover the test setup

1. Detect the test framework(s):
   - JS/TS: `jest`, `vitest`, `mocha`, `playwright`, `cypress`, `@testing-library/*`, `ava`.
   - Python: `pytest`, `unittest`, `hypothesis` (property), `locust` (load).
   - Go: built-in `testing`, `testify`, `gomock`, `vegeta` / `k6` for load.
   - Java/Kotlin: `junit5`, `testng`, `mockito`, `gatling`.
   - Rust: built-in, `proptest`, `criterion`.
   - .NET: `xunit`, `nunit`, `mstest`.
   - Ruby: `rspec`, `minitest`.
2. Read the test config (`jest.config.*`, `pytest.ini`, `pyproject.toml [tool.pytest.ini_options]`, `go.mod`, etc.) to understand: coverage thresholds, excluded paths, test patterns.
3. Detect CI invocation — does CI actually run tests? Does it enforce a coverage threshold? Grep `.github/workflows/`, `.gitlab-ci.yml`, `.circleci/`, etc.
4. Inventory test directories: unit vs integration vs e2e vs load. Count files, count test cases.

## Step 2 — run coverage (if possible)

If the user is in edit mode and a coverage command is discoverable (e.g. `npm run test:coverage`, `pytest --cov`, `go test -cover ./...`), propose running it. Do not run it unprompted — it may be slow and change CI state.

If coverage can't be run, use static heuristics:
- Count source files under `src/` (or equivalent).
- Count test files.
- Map test files to source files by name convention (`foo.ts` → `foo.test.ts`).
- Flag source files with no corresponding test.

## Step 3 — check for meaningful coverage

High line coverage can still hide gaps. Check for:

### A. Critical paths without tests

Use GitNexus if available:
- `mcp__gitnexus__route_map` — for each HTTP route, is there at least one test that exercises it end-to-end?
- `mcp__gitnexus__query` — find functions with `@Transactional`, `@Authenticated`, or that write to DB, and check their test coverage.

Without GitNexus, scan for:
- Handlers/controllers without a matching integration test.
- Database write functions without tests.
- Background job entry points without tests.
- Scheduled job functions without tests.
- Message consumer handlers without tests.
- Error handlers and fallback paths.

### B. Tests that don't assert

Grep each test file for:
- Tests with no `expect` / `assert` / `require` call.
- Tests that only check `truthy`, `toBeDefined`, `not.toThrow` without substantive checks.
- Tests that catch exceptions and silently continue.
- Tests with commented-out assertions.
- `expect(fn).not.toHaveBeenCalled()` on a spy that was never installed correctly.
- `it.skip`, `xit`, `test.skip`, `describe.skip`, `@Disabled`, `t.Skip()` — list them all.

### C. Tests that are structurally broken

- Snapshot tests with no snapshot file or with a wildly stale one.
- Tests that set `timeout: 60000` but run quickly — sign of a flaky async test band-aid.
- Tests that rely on `setTimeout` / `sleep` without deterministic alternatives.
- Shared mutable state between tests (global variables mutated in `beforeAll`).

### D. Mock discipline

- Unit tests mocking things they shouldn't (the unit itself, its own methods, its own types).
- Integration tests mocking the thing being tested (database mocked in a DB integration test).
- Mocks that never verify calls (`jest.fn()` with no `toHaveBeenCalledWith`).
- Global auto-mocks causing tests to lie about behavior.

### E. Edge cases and error paths

For critical functions, check that tests cover:
- Empty input.
- Null / undefined.
- Maximum length / boundary values.
- Invalid types (or, in typed languages, invalid runtime values from untyped sources).
- Concurrent invocation (if the function touches shared state).
- Partial failure (e.g. network error mid-operation, DB timeout, third-party 500).
- Permission denied (for functions behind auth).

### F. Integration tests

Required at team+ tier. Check for:
- Database integration: tests running against a real DB (ideally same engine/version as prod), not mocks.
- HTTP integration: tests exercising full request→handler→response including middleware.
- Message queue integration: produce + consume cycle exercised.
- External service integration: use of `wiremock`, `msw`, `vcr`, `httpmock` to stub deterministically.

### G. End-to-end tests (scalable tier)

- Critical user flows covered (signup, login, core transaction, logout, password reset).
- Run on CI against a deployed environment or with fully wired-up services.
- Not flaky — flakiness >1% over 100 runs is a finding.

### H. Load / stress / performance tests

- Load test exists at team+ tier: at least a happy-path smoke load (e.g. k6 / Locust / Gatling) at 2× expected throughput.
- Stress test at scalable tier: pushing past capacity to observe failure modes.
- Soak test at scalable tier: 24h+ at steady state, looking for memory leaks, connection pool exhaustion, slow-growing latency.
- Chaos test at scalable tier: injected failures in dependencies (DB, cache, downstream service).
- Results: are baselines tracked? is there a regression gate?

### I. Property-based tests

For code that parses, serializes, encodes/decodes, or implements a state machine: property-based tests catch classes of bugs unit tests miss. Check for `fast-check`, `hypothesis`, `proptest`, `ScalaCheck` usage.

### J. Security and compliance tests

Cross-reference with security-audit + compliance-check findings:
- Authorization tests: does an unauthorized request get rejected? Tested per endpoint?
- Input validation tests: are injection payloads rejected?
- Data subject right tests (if GDPR applies): does the erasure endpoint actually erase?

## Severity classification

| Severity | Meaning |
|---|---|
| critical | Critical path has zero test coverage; a regression would be invisible. |
| high | Coverage below tier threshold; meaningful test gaps in error paths; integration tests missing at team+ tier. |
| medium | Specific edge cases uncovered; mock misuse; skipped tests accumulating. |
| low | Nice-to-have gaps; property-based tests missing where they'd add value. |
| info | Observations on test quality (e.g. slow test suite). |

## Output format

```yaml
- id: TEST-<NNN>
  severity: ...
  category: coverage | critical-path | assertions | mocking | edge-cases | integration | e2e | load | property | flaky
  title: ...
  location: <file or directory>
  description: |
    <what's missing, why it matters>
  evidence:
    - <coverage number / file list / code snippet>
  remediation:
    plan_mode: |
      <what tests to add, what to change>
    edit_mode: |
      <test scaffold or diff>
  references:
    - <testing guide link, framework docs>
  blocker_at_tier: [...]
```

Dimension summary:

```markdown
## Test Coverage Summary

Framework(s): <list>
Line coverage: <X%> (threshold <Y%>)
Branch coverage: <X%> (threshold <Y%>)
Unit tests: <count>
Integration tests: <count>
E2E tests: <count>
Load tests: <count | none>
Skipped tests: <list>

Critical paths without tests: <N>
Top 3 gaps:
  1. <id> — <title>
  2. ...
```

## Edit-mode remediation

When generating tests:

1. **Match the project's conventions.** Use the same framework, same file naming, same helper patterns (fixtures, factories, test utils) as existing tests.
2. **Write meaningful assertions.** Don't generate `expect(result).toBeDefined()`. Assert on the specific return value, side effects, and error conditions.
3. **Cover the matrix — not a token test.** For a new test file, write:
   - Happy path.
   - At least two edge cases (empty input, boundary).
   - At least one error path.
   - For async: cancellation / timeout behavior if relevant.
4. **For integration tests**, spin up the real dependency (database, queue) using docker-compose / testcontainers when possible. Avoid mocks at the integration layer.
5. **For load tests**, scaffold a k6 / Locust script with a realistic request mix, not a single-endpoint hammer.
6. **Do not silently un-skip tests.** A skipped test was usually skipped for a reason. Fix the underlying issue or flag it.

For any generated test, **run it after writing** to verify it passes (in edit mode). If it fails, either fix the test or fix the code under test — do not leave broken tests behind.

## Do not

- Do not pad coverage by testing trivial code (getters/setters, generated code) while leaving real logic uncovered.
- Do not approve deleted assertions or loosened thresholds as "remediation". Tightening a ratchet, not loosening it, is the fix.
- Do not count snapshot tests as coverage for logic — they prove output stability, not behavior correctness.
- Do not count type checking as test coverage. They're complementary, not substitutes.
- Do not measure coverage on generated code, vendored code, or `__mocks__`. Adjust exclusions properly in the tool config.
