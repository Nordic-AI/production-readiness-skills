---
name: scalability-review
description: Scope-aware review of scalability and performance readiness — database indexing and query patterns, N+1 queries, caching strategy, connection pooling, horizontal scalability, statelessness, rate limiting, pagination, background job architecture, and expected-load headroom. Thresholds adapt sharply to the project's scope tier (prototype, team, scalable). Use when the user asks about "scalability", "performance", "will this scale", "horizontal scaling", "caching", invokes /scalability-review, or when the orchestrator delegates. Stack-agnostic, mode-aware.
---

# Scalability Review

You review whether the application can handle its target load and grow with demand. Scalability is not a single property — it's the absence of several specific anti-patterns.

**This skill is the most scope-tier-sensitive.** A prototype should not be forced to defend horizontal scaling. A scalable-tier system must.

## Inputs

From orchestrator: `scope_tier`, `stack_summary`, `gitnexus_indexed`, entry points, and any context on expected load (QPS, data volume, tenant count, geographic distribution).

If expected load isn't known, ask — but keep it simple:

```
Rough scale targets for scaling review:
- Concurrent users (peak): ?
- Requests/sec at peak: ?
- Total data volume (e.g. rows in largest table): ?
- Tenants / accounts: ?
- Geographic spread: single region / multi-region / global?
```

## Mode detection

- **Plan mode** — produce scalability report with prioritized findings.
- **Edit mode** — apply targeted fixes. Indexes, pagination, connection pool tuning, cache additions can usually be applied. Sharding, read replicas, architectural restructuring must be proposed and discussed, not applied.

## Thresholds by tier

| Tier | DB indexing | N+1 | Caching | Stateless | Rate limiting | Pagination | Async jobs | Headroom |
|---|---|---|---|---|---|---|---|---|
| prototype | advisory | advisory | optional | advisory | optional | required on list endpoints | optional | advisory |
| team | **required** on common queries | **required** to fix | recommended where beneficial | **required** (no in-process session state) | **required** on public + auth endpoints | **required** | **required** for long-running work | 2× expected load |
| scalable | **required + reviewed regularly** | **required** | **required** — multi-tier, invalidation strategy | **required + tested** | **required + per-tenant** | **required + cursor-based for large sets** | **required + queue-backed** | 3-5× expected load, headroom monitored |

## Review surface

### 1. Database schema and indexing

- **Check for indexes on common access patterns.** Use GitNexus `mcp__gitnexus__query` if available to find all `WHERE`/`ORDER BY`/`JOIN` columns. Otherwise scan ORM queries / repository methods / SQL files.
- **For each frequently-queried table:**
  - Primary key exists and is appropriate (avoid UUID PKs on InnoDB if hot insert rate is high; use ULIDs or sortable UUIDs).
  - Foreign keys have matching indexes.
  - Composite indexes match query predicates (column order matters — most selective first).
  - Covering indexes for hot read paths where it meaningfully reduces I/O.
  - No duplicate / redundant indexes.
- **Anti-patterns:**
  - `SELECT *` in hot paths — fetches columns you don't need; blocks covering-index optimization.
  - `LIKE '%foo%'` on un-indexed text — full scan; use full-text search or GIN/GIST (Postgres).
  - `OR` across indexed + non-indexed columns causing index skip.
  - `ORDER BY RAND()` — full scan + filesort.
  - Queries without `LIMIT` returning large result sets.
- **Migrations:**
  - Adding an index on a large table without `CONCURRENTLY` (Postgres) blocks writes.
  - Adding NOT NULL columns with a default on a large table can rewrite the whole table (Postgres < 11).
  - Long-running migrations require online-migration patterns.

### 2. N+1 queries

- Grep ORM call patterns for loops that trigger per-iteration queries:
  - Rails: `.each { .foo.bar }` without `.includes(:foo)` / `.eager_load`.
  - Django: loop over `.all()` accessing related fields without `select_related` / `prefetch_related`.
  - SQLAlchemy: accessing relationships without `joinedload` / `selectinload`.
  - Prisma: `.findMany` then `.findUnique` in a loop.
  - ActiveRecord / similar: nested `.map` with DB access inside.
- Graphql resolvers without a DataLoader for the N+1 classic case.
- Check query logs (if captured in dev): same query repeated with different parameters → N+1 signature.

### 3. Query analysis

- Enable query logging in dev / staging to observe real query counts per request.
- For critical endpoints: run `EXPLAIN ANALYZE` (Postgres) / `EXPLAIN FORMAT=JSON` (MySQL). Findings if:
  - Sequential scans on large tables.
  - Sort operations without index support on `ORDER BY`.
  - Temporary tables / filesort.
  - Hash joins where nested-loop would be faster (or vice-versa).
- Slow query log enabled in production at team+ tier.

### 4. Connection pooling

- **DB connection pool** present and sized appropriately:
  - Pool size roughly: `(max_concurrent_requests × avg_queries_per_request × avg_query_time) / target_latency`. Too-small pools cause waiting; too-large pools exhaust DB.
  - At scalable tier, use a dedicated pooler (PgBouncer, Odyssey) between app and DB — especially for serverless / many-instance deployments.
  - Pool timeouts configured (wait timeout, idle timeout, max lifetime).
- **HTTP client pools** for outbound requests — avoid creating a new client per request.
- **Redis / cache pools** configured.

### 5. Caching

#### A. Tiered strategy

- **Browser cache** (`Cache-Control`, ETag, Last-Modified) on static and semi-static responses.
- **CDN / edge cache** for cacheable assets and API responses.
- **Shared cache** (Redis / Memcached) for cross-instance data.
- **In-process cache** for very hot read-mostly data — with clear invalidation rules.

#### B. What to cache

- Read-heavy queries with stable results.
- External API responses (rate-limited APIs especially).
- Computed views (denormalized aggregates).
- Per-request memoization of repeated lookups.

#### C. Invalidation

- **Cache invalidation strategy documented** — or cache drift / stale data becomes a bug source.
- Write-through / write-behind / TTL-only — which does the app use per cache? Is it appropriate to the data's staleness tolerance?
- Cache stampede prevention: `singleflight`, lock-on-miss, probabilistic early expiration.

#### D. Anti-patterns

- Caching user-specific data in a shared cache without tenant / user segmentation (cross-tenant data leak).
- `TTL = Infinity` without invalidation trigger.
- Caching error responses.

### 6. Statelessness / horizontal scaling

- **In-process session state** is a finding at team+ tier. Sessions in a shared store (Redis, DB, signed JWTs).
- **In-process caches with local-only invalidation** don't scale — adding a second instance causes divergence.
- **Sticky sessions** as a workaround for stateful design — flag.
- **WebSocket / SSE / long-poll connections** on an auto-scaled service — scaling requires a backplane (Redis pub/sub, message queue, managed service like Pusher / Ably / API Gateway WebSockets).
- **Singleton state** (in-process rate limiter, in-process scheduler, in-process job queue) that must be coordinated across instances.
- **Container startup time** — slow cold-start makes scaling reactive rather than elastic.

### 7. Background work and async

- **Long-running work on the request path** is a finding:
  - Report generation, bulk operations, third-party API chains — move to background.
- **Job queue in use:** BullMQ, Sidekiq, Celery, RQ, SQS, GCP Tasks, Kafka, Temporal — any?
- **Queue properties:**
  - Persistent (durable).
  - At-least-once delivery + consumer idempotency.
  - Dead-letter queue for unprocessable messages.
  - Monitored for backlog growth.
  - Autoscaling based on queue depth.
- **Cron / scheduled jobs:**
  - Use a distributed scheduler (not per-instance cron) — avoid duplicate executions.
  - Long-running cron jobs can overlap — detect and prevent.

### 8. Rate limiting

Overlaps with security-audit + reliability-audit. Scalability angle:

- Rate limits prevent a noisy tenant / bot / runaway-loop from degrading service for everyone.
- Per-API-key / per-IP / per-user limits at team+ tier.
- Per-tenant / per-endpoint differentiated limits at scalable tier.
- Enforced at the edge (reverse proxy, API gateway) preferred over application-layer for DDoS absorption.
- Quota + bucket semantics documented (burst, refill rate).
- 429 responses include `Retry-After` header.

### 9. Pagination

- Every list endpoint must paginate at team+ tier.
- **Cursor-based pagination** for large or frequently-updated datasets (avoids offset drift + offset performance).
- Offset pagination acceptable for small bounded lists only.
- Max page size enforced on the server — client can't request 100k records.
- Total count queries are expensive on large tables — avoid or cache.

### 10. Search and large scans

- Avoid full-table scans in user-facing paths.
- Full-text search delegated to a dedicated system (Elasticsearch / OpenSearch / Meilisearch / Typesense / Postgres FTS with proper indexes) rather than `ILIKE '%...%'` at scale.
- Aggregate / reporting queries isolated from OLTP DB (read replica, data warehouse, OLAP store) at scalable tier.

### 11. Concurrency + throughput

- **Request-handling concurrency model** appropriate to stack:
  - Node.js: I/O-bound workloads benefit from high async concurrency, single thread per event loop — worker threads / cluster for CPU.
  - Python: GIL-bound — use multiple processes (gunicorn workers, uvicorn workers) for CPU-bound; asyncio for I/O-bound.
  - Go: default is efficient; watch for goroutine leaks.
  - JVM: thread pool sizing critical — one-thread-per-request doesn't scale past pool limit.
- **Blocking I/O on async runtimes** is a finding — sync DB driver in an async event loop starves the loop.

### 12. Geographic distribution (scalable tier)

- Multi-region active-active or active-passive?
- Latency sensitivity: where do users live vs. where's the data?
- CDN + edge compute for global reads.
- Database replication — primary / replica / multi-primary? Read-your-writes consistency semantics?
- Data sovereignty constraints from compliance-check (some data can't cross borders).

### 13. Payload sizes

- Response sizes capped or streamed. Multi-megabyte JSON responses are a finding.
- Gzip / brotli compression enabled.
- Images served with appropriate format (WebP / AVIF) + size variants.

### 14. Capacity planning + autoscaling

At team+ tier:

- Autoscaling configured with sensible thresholds.
- Min instance count > 1 for availability.
- Scale-up is **faster** than scale-down (avoid oscillation; gentler scale-down).
- Cooldown periods prevent flapping.
- Scaling signals are **leading** (CPU, queue depth, p95 latency), not lagging (error rate).

### 15. Expected-load headroom

- Capacity at least 2× (team) / 3-5× (scalable) expected peak — load test should prove this.
- Cross-reference test-coverage findings on stress tests.
- Failure modes at over-capacity: graceful 503s > silent degradation > timeouts.

## Severity classification

| Severity | Meaning |
|---|---|
| critical | Guaranteed failure at modest scale: N+1 on hot path, missing index on FK, single-instance stateful service. |
| high | Will degrade badly within plausible growth window: lack of pagination, sync blocking in async runtime, shared cache missing for expensive compute. |
| medium | Not immediate pain but will compound: suboptimal index, missing rate limit, missing connection pool tuning. |
| low | Nice-to-have optimizations: compression, HTTP/2, prefetch, etc. |
| info | Observations about current capacity / headroom. |

## Output format

```yaml
- id: SCALE-<NNN>
  severity: ...
  category: db-index | n-plus-1 | query | pool | cache | stateless | async | rate-limit | pagination | search | concurrency | geo | payload | autoscale | headroom
  title: ...
  location: <file:line or system-level>
  description: |
    <what, why, scale at which this becomes a problem>
  evidence:
    - <code snippet / EXPLAIN output / profile sample>
  remediation:
    plan_mode: |
      <fix description, rough effort>
    edit_mode: |
      <diff / config change>
  references:
    - <database docs / performance guide>
  blocker_at_tier: [...]
  expected_impact: |
    <e.g. "at 1k QPS, query time drops from 300ms p99 to ~5ms p99">
```

Dimension summary:

```markdown
## Scalability Summary

Scope tier: <...>
Expected load: <if provided>
Current hot paths: <top 3 endpoints / queries by estimated load>

Top 3 scaling risks:
  1. ...

Indexes: <count OK, count missing>
N+1 detected: <count>
Cacheable but uncached: <count>
Paginated endpoints: <X/Y>
Stateful components: <list>
```

## Edit-mode remediation

Safe:
- Adding missing indexes (use `CREATE INDEX CONCURRENTLY` for Postgres on large tables — flag to user).
- Adding `LIMIT` / pagination to list endpoints.
- Adding `prefetch_related` / `joinedload` / DataLoader for N+1.
- Adding cache-control headers.
- Adding response compression middleware.
- Tuning connection pool sizes (within conservative bounds).
- Adding rate-limit middleware with defaults.

Require confirmation:
- Migrating from in-process state to a shared store.
- Restructuring for horizontal scaling.
- Introducing a job queue or cache layer (adds dependency).
- Changing sync → async paradigm.
- Adding read replicas / sharding / caching tiers (architectural).
- Changing autoscaling policy.

## Do not

- Do not prescribe scalable-tier solutions (sharding, multi-region, event sourcing) to prototype-tier apps — complexity without justification kills small projects.
- Do not add indexes speculatively — each index has write + storage cost. Add them where queries justify them.
- Do not recommend caching as a fix for every slow query. First improve the query; cache what's still hot.
- Do not confuse "faster" with "more scalable" — some optimizations reduce latency without increasing throughput, and vice-versa.
- Do not propose microservices as a scalability fix for a monolith unless the actual bottleneck justifies it. Most "we need microservices" problems are really "we need indexes and a queue".
- Do not ignore the cost side. Scalability changes can 10× the infrastructure bill; surface the tradeoff.
