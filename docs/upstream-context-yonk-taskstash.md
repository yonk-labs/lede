# yonk-taskstash: Architectural Design Document

> **Audience:** Engineers taking this POC to production
> **Status:** POC / Pre-Production
> **Last Updated:** 2026-02-15

---

## Table of Contents

1. [What Is This?](#1-what-is-this)
2. [Why Does This Exist?](#2-why-does-this-exist)
3. [Requirements, Expectations & Exit Criteria](#3-requirements-expectations--exit-criteria)
4. [System Architecture Overview](#4-system-architecture-overview)
5. [Core Data Model](#5-core-data-model)
6. [Storage Layer](#6-storage-layer)
7. [The Middleware Interception Pattern](#7-the-middleware-interception-pattern)
8. [LangChain Integration](#8-langchain-integration)
9. [Langflow Integration](#9-langflow-integration)
10. [MCP Server Integration](#10-mcp-server-integration)
11. [Configuration System](#11-configuration-system)
12. [Embedding & Summarization Providers](#12-embedding--summarization-providers)
13. [PII Detection & Content Safety](#13-pii-detection--content-safety)
14. [Cache Invalidation & Lifecycle Management](#14-cache-invalidation--lifecycle-management)
15. [Benchmark & Validation Framework](#15-benchmark--validation-framework)
16. [Known Limitations & POC Debt](#16-known-limitations--poc-debt)
17. [Ideas for Fixing or Overcoming Known Limitations](#17-ideas-for-fixing-or-overcoming-known-limitations)
18. [Production Readiness Checklist](#18-production-readiness-checklist)
19. [Glossary](#19-glossary)

---

## 1. What Is This?

**yonk-taskstash** is an *off-prompt memory* system for LLM-powered applications. It sits between your AI agent and its tools, intercepting large or sensitive data before it reaches the LLM's context window. Instead of sending a 50,000-character database query result directly to GPT-5 or Claude, TaskStash:

1. **Stores** the full content in a backend you control (memory, SQLite, PostgreSQL)
2. **Returns** a compact reference (`taskstash://namespace/uuid`) and a short summary to the LLM
3. **Provides tools** for the LLM to fetch the full content on-demand when it actually needs it

The net effect: your agent sees a ~200-token summary instead of a ~12,500-token raw dump. It can still access the original data, but only pays the token cost when the task requires it.

### What It Is Not

- **Not a vector database** -- it can *use* vector databases (pgvector) for semantic search, but it is primarily a content management and interception layer
- **Not a RAG framework** -- it complements RAG by managing what happens *after* retrieval (i.e., the retrieved content may still be too large for the context window)
- **Not a caching layer alone** -- while it does cache, its primary value is *intelligent interception* with structured summaries that preserve schema information

### Integration Surface

TaskStash provides adapters for three integration patterns. **These are not equivalent.** They differ fundamentally in whether interception is *guaranteed* or *suggested*:

| Integration | Pattern | Enforcement Model | Use Case |
|-------------|---------|-------------------|----------|
| **LangChain Middleware** | Python middleware wrapping tool calls | **Structural** -- interception happens in code before the LLM sees the output. The LLM cannot bypass it. | Production pipelines where cost control and data residency are non-negotiable |
| **Langflow Components** | Visual drag-and-drop pipeline nodes | **Structural** -- data physically routes through TaskStash components. No path exists to bypass the flow. | No-code/low-code teams, auditable pipelines, visual governance |
| **LangChain Toolkit** | LangChain tools given to the agent | **Advisory** -- the LLM decides when to use stash_store/stash_fetch. It may choose not to. | Flexible agent workflows where the LLM should have agency over storage decisions |
| **MCP Server** | Model Context Protocol tools | **Advisory** -- the LLM sees TaskStash tools and decides when to invoke them. No guarantee of use. | Claude Desktop, Claude Code, exploratory use, any MCP-compatible client |

**The critical question for production:** Do you need interception to be *guaranteed* (use middleware/components) or *available* (use toolkit/MCP)?

All four share the same core library. The adapters are thin wrappers.

---

## 2. Why Does This Exist?

### The Problem

Every LLM API call has a cost function: `price = f(input_tokens + output_tokens)`. When AI agents use tools -- database queries, API calls, file reads, web scrapes -- those tool outputs flow directly into the LLM context window. This creates four compounding problems:

**Cost Explosion.** A single SQL query returning 1,000 rows can consume 15,000+ tokens. An agent running 5 tool calls per turn, across a 10-turn conversation, can burn 750,000 tokens per session. At $15/M input tokens (Claude Opus), that's $11.25 per conversation.

**Context Window Saturation.** Even with 200K-token windows, agents that process documents, query databases, and analyze logs can exhaust their context in 3-4 turns. When the context is full, the agent loses access to earlier conversation history.

**Data Leakage Risk.** Every character sent to an LLM API leaves your infrastructure. Medical records, financial data, PII, proprietary source code -- all of it flows to third-party servers. Compliance frameworks (HIPAA, SOC2, GDPR) may prohibit this.

**Redundant Processing.** In multi-turn conversations, agents re-fetch the same data repeatedly. In multi-agent architectures, each agent independently retrieves and processes the same source material.

### The Thesis

**Most tool output is never fully consumed by the LLM.** Benchmarks across 25 realistic AI workload patterns (structured data + text documents) show:

- In 84% of scenarios (21/25), the agent can operate effectively from a summary + on-demand fetch
- Average token savings: **76.7%** (honest, fetch-probability-adjusted measurement)
- Only 4 of 25 patterns (16%) are worse with TaskStash -- specifically those where the agent *always* needs 100% of the data
- Quality comparison across 32 scenarios (JSON, SQL, text): FTS search preserves answers in 28/32 cases, hybrid (FTS + semantic) in 23/32

The key insight: **fetch probability varies by workload pattern**. Schema discovery queries (fetch probability ~20%) benefit enormously. Aggregation queries (fetch probability 100%) do not. TaskStash gives you the interception layer to exploit this variance. For text documents (API docs, meeting notes, incident reports), hybrid search excels at semantic queries where exact keyword matching falls short.

---

## 3. Requirements, Expectations & Exit Criteria

### Functional Requirements

| ID | Requirement | POC Status | Production Gap |
|----|-------------|------------|----------------|
| FR-1 | Store arbitrary text/JSON content with metadata | Done | Content size limits not enforced |
| FR-2 | Retrieve content by reference URI (`taskstash://`) | Done | No authentication on references |
| FR-3 | Query content by namespace, metadata, and full-text search | Done | SQLite FTS5 works; Postgres tsvector partially implemented |
| FR-4 | Automatically intercept LLM tool outputs above a configurable threshold | Done | Only string outputs intercepted; binary/streaming not handled |
| FR-5 | Generate structured summaries preserving JSON schema and SQL column info | Done | Heuristic detection only (no MIME-type awareness) |
| FR-6 | Support session-scoped and TTL-based artifact lifecycle management | Done | No background TTL reaper; lazy cleanup only |
| FR-7 | Provide LangChain middleware and toolkit adapters | Done | Custom BaseTool, not LangChain's native BaseTool |
| FR-8 | Provide Langflow drag-and-drop components | Done | Dual component hierarchy needs consolidation |
| FR-9 | Provide MCP server for Claude Desktop/Code integration | Done | Global singleton stash; no multi-user support |
| FR-10 | Support pluggable storage backends (memory, SQLite, PostgreSQL) | Done | PostgreSQL backend needs connection pool tuning |
| FR-11 | Support pluggable embedding providers | Done | Provider error handling is minimal |
| FR-12 | Optional PII detection and redaction | Done | Regex-based is basic; Presidio integration exists but needs tuning |

### Integration Enforcement Models: Advisory vs. Structural

This is the most important architectural distinction for production engineers to understand. **Not all integrations provide the same guarantees.**

#### Structural Integrations (Guaranteed Interception)

**LangChain Middleware** and **Langflow Components** are *structural* -- they sit in the data pipeline and physically intercept content before the LLM ever sees it:

```
  ┌──────────┐     ┌──────────────────┐     ┌─────────┐
  │ Tool     │────▶│ Middleware/       │────▶│ LLM     │
  │ Output   │     │ Component        │     │         │
  │ (50KB)   │     │ (forces stash)   │     │ (sees   │
  │          │     │                  │     │  200    │
  │          │     │ LLM NEVER SEES   │     │  tokens)│
  │          │     │ THE RAW OUTPUT   │     │         │
  └──────────┘     └──────────────────┘     └─────────┘
```

- The LLM cannot opt out of interception. It cannot "decide" to skip storage.
- Cost savings are deterministic: if content > threshold, it gets intercepted. Period.
- Data governance is enforceable: PII never reaches the LLM API.
- Token budgets are predictable: you know the max tokens per tool call.

**Use structural integrations when:** you need cost guarantees, compliance enforcement, predictable budgets, or data residency controls.

#### Advisory Integrations (LLM-Controlled)

**MCP Server** and **LangChain Toolkit** are *advisory* -- they give the LLM tools it *can* use, but the LLM decides whether and when to use them:

```
  ┌──────────┐                              ┌─────────┐
  │ Tool     │─────────────────────────────▶│ LLM     │
  │ Output   │     (full 50KB goes to LLM)  │         │
  │ (50KB)   │                              │ (sees   │
  │          │     LLM may or may not call   │  all    │
  │          │     taskstash_store() after   │  12,500 │
  │          │                              │  tokens)│
  └──────────┘                              └─────────┘
```

- The LLM receives the full output first, *then* decides if it should store it.
- An LLM might ignore the stash tools entirely (it has no obligation to use them).
- Cost savings depend on LLM behavior, which varies by model, prompt, and temperature.
- PII reaches the LLM API first -- the LLM would need to recognize and store it after the fact.

**Use advisory integrations when:** you want the LLM to have agency over storage decisions, for exploratory/interactive use (Claude Desktop), or when the LLM's judgment about what to store is valuable.

#### Hybrid Approach (Recommended for Production)

The strongest production architecture combines both:

```python
# Structural: Forces interception of all large outputs
middleware = ContentAwareMiddleware(threshold=5000)

# Advisory: Gives the agent fetch/query tools for on-demand retrieval
toolkit = TaskStashToolkit(stash, include_tools=["stash_fetch", "stash_query"])
```

This guarantees that large content is always intercepted (structural) while still giving the agent the ability to fetch and search stored content (advisory). The agent never sees raw 50KB outputs, but it can request them when its task requires it.

### Non-Functional Requirements

| ID | Requirement | POC Status | Production Gap |
|----|-------------|------------|----------------|
| NFR-1 | Interception overhead < 50ms for content < 100KB | Needs validation | No latency benchmarks in CI |
| NFR-2 | Support 100+ concurrent sessions | Not tested | Memory backend has no concurrency controls |
| NFR-3 | Graceful degradation when storage is unavailable | Not implemented | Exceptions propagate to agent |
| NFR-4 | Observability: structured logging, metrics, audit trail | Stubs exist | Prometheus/OTEL integration incomplete |
| NFR-5 | Zero data sent to LLM APIs that hasn't passed through PII check (when enabled) | Partial | PII check only on store path, not on fetch responses |

### Exit Criteria: POC to Production

The following must be true before this system is production-ready:

**Must-Have (P0):**

- [ ] All storage backends have integration tests running in CI with real databases
- [ ] Reference URIs include authentication/authorization (session token or HMAC)
- [ ] TTL expiration has a background reaper (not just lazy cleanup)
- [ ] Concurrency tests pass for SQLite (WAL mode) and PostgreSQL (connection pool)
- [ ] Content size limits are enforced and configurable
- [ ] Error handling returns structured errors, not raw exceptions, to LLM agents
- [ ] LangChain tools extend `langchain_core.tools.BaseTool` (not custom BaseTool)
- [ ] Langflow components validated against latest Langflow component parser
- [ ] MCP server supports multi-user sessions (not global singleton)
- [ ] PII detection coverage validated against benchmark dataset
- [ ] All `TODO`, `FIXME`, and `placeholder` comments resolved or tracked as issues

**Should-Have (P1):**

- [ ] Prometheus metrics endpoint for interception rate, storage size, latency percentiles
- [ ] OpenTelemetry tracing spans for store/fetch/query operations
- [ ] Rate limiting on MCP server tool calls
- [ ] Streaming support for large content fetch (chunked response)
- [ ] Admin API for storage health, artifact counts, namespace inventory
- [ ] Configurable content compression for storage backends
- [ ] Database migrations strategy (Alembic or equivalent)

**Nice-to-Have (P2):**

- [ ] Multi-tenancy with row-level security in PostgreSQL
- [ ] Cross-session artifact sharing with access control
- [ ] Webhook notifications on interception events
- [ ] Dashboard UI for storage monitoring

---

## 4. System Architecture Overview

### Layer Diagram

```
                    ┌──────────────────────────────────────────┐
                    │          Integration Layer               │
                    │                                          │
                    │  ┌──────────┐ ┌────────┐ ┌───────────┐  │
                    │  │LangChain │ │Langflow│ │MCP Server │  │
                    │  │Middleware│ │ Comps  │ │ (stdio)   │  │
                    │  │+ Toolkit │ │        │ │           │  │
                    │  └────┬─────┘ └───┬────┘ └─────┬─────┘  │
                    └───────┼───────────┼────────────┼─────────┘
                            │           │            │
                    ┌───────▼───────────▼────────────▼─────────┐
                    │              Core Library                 │
                    │                                          │
                    │  ┌──────────┐  ┌─────────┐  ┌────────┐  │
                    │  │TaskStash │  │ Session │  │Artifact│  │
                    │  │ (facade) │──│(scoping)│──│ (model)│  │
                    │  └────┬─────┘  └─────────┘  └────────┘  │
                    │       │                                  │
                    │  ┌────▼──────────────────────────────┐   │
                    │  │         Query Engine               │   │
                    │  │  metadata + FTS + semantic search  │   │
                    │  └────┬──────────────────────────────┘   │
                    └───────┼──────────────────────────────────┘
                            │
                    ┌───────▼──────────────────────────────────┐
                    │           Storage Layer                   │
                    │                                          │
                    │  ┌────────┐  ┌──────┐  ┌────────────┐   │
                    │  │ Memory │  │SQLite│  │ PostgreSQL │   │
                    │  │(dict)  │  │(FTS5)│  │(pgvector)  │   │
                    │  └────────┘  └──────┘  └────────────┘   │
                    └──────────────────────────────────────────┘
                            │
                    ┌───────▼──────────────────────────────────┐
                    │        Provider Layer (Optional)          │
                    │                                          │
                    │  ┌───────────────┐  ┌────────────────┐   │
                    │  │  Embeddings   │  │ Summarization  │   │
                    │  │ OpenAI,Ollama │  │ BART,Ollama    │   │
                    │  │ SentenceTrans │  │ OpenAI,llama   │   │
                    │  └───────────────┘  └────────────────┘   │
                    └──────────────────────────────────────────┘
```

### Request Flow: Tool Output Interception

This is the critical path -- the flow that saves tokens:

```
  Agent calls tool (e.g., SQL query)
         │
         ▼
  Tool returns raw output (e.g., 50,000 chars)
         │
         ▼
  ┌─────────────────────────┐
  │   Middleware Intercept   │
  │                         │
  │  Is it a string?        │──No──▶ Pass through unchanged
  │         │Yes            │
  │  Is len > threshold?    │──No──▶ Pass through unchanged
  │         │Yes            │
  │  Detect content type    │
  │  (JSON / SQL / text)    │
  │         │               │
  │  ┌──────▼──────┐        │
  │  │ Store full  │        │
  │  │ content in  │        │
  │  │ TaskStash   │        │
  │  └──────┬──────┘        │
  │         │               │
  │  Generate summary:      │
  │  - JSON: schema+sample  │
  │  - SQL: columns+sample  │
  │  - Text: extractive     │
  │    sentence selection   │
  │         │               │
  │  Return to agent:       │
  │  "[Stored in TaskStash] │
  │   Size: 50,234 chars    │
  │   Ref: taskstash://...  │
  │   Preview: (key         │
  │   sentences)"           │
  └─────────────────────────┘
         │
         ▼
  Agent sees ~200 tokens instead of ~12,500
  Agent calls taskstash_fetch(ref) only if needed
```

### Module Dependency Graph

```
pyproject.toml defines optional dependency groups:

  yonk-taskstash              (core: pydantic, pyyaml)
  yonk-taskstash[sqlite]      (+ stdlib sqlite3)
  yonk-taskstash[postgres]    (+ asyncpg, pgvector)
  yonk-taskstash[local]       (+ sentence-transformers, torch)
  yonk-taskstash[openai]      (+ openai)
  yonk-taskstash[ollama]      (+ httpx)
  yonk-taskstash[langchain]   (+ langchain-core, langchain)
  yonk-taskstash[langflow]    (+ langflow)
  yonk-taskstash[mcp]         (+ mcp)
  yonk-taskstash[presidio]    (+ presidio-analyzer, presidio-anonymizer, spacy)
  yonk-taskstash[observability] (+ prometheus-client, opentelemetry)
```

The core library (`TaskStash`, `Artifact`, `Session`, `MemoryBackend`) has only two dependencies: `pydantic` and `pyyaml`. Everything else is optional and loaded lazily.

---

## 5. Core Data Model

### Artifact

The fundamental unit of storage. Defined in `src/yonk_taskstash/core/artifact.py`:

```python
class Artifact(BaseModel):
    # Identity
    id: UUID                              # Auto-generated, globally unique
    session_id: str                       # Scoping key
    user_id: str | None                   # Optional user-level scoping
    namespace: str                        # Logical grouping ("documents", "api_results")

    # Content
    content: str                          # The actual data (no size limit in POC)
    content_type: ContentType             # TEXT | JSON | BLOB | IMAGE | AUDIO | VIDEO
    summary: str | None                   # Optional pre-computed summary
    embedding: list[float] | None         # Vector for semantic search

    # Metadata
    metadata: dict[str, Any]              # Arbitrary key-value pairs

    # Lifecycle
    lifecycle: Lifecycle                  # SESSION | TTL | MANUAL
    ttl_seconds: int | None              # For TTL lifecycle
    created_at: datetime                  # Auto-set on creation
    expires_at: datetime | None           # Computed from ttl_seconds

    # Computed (read-only)
    token_estimate: int                   # len(content) // 4
    byte_size: int                        # len(content.encode('utf-8'))
    reference: str                        # "taskstash://{namespace}/{id}"
    is_expired: bool                      # expires_at < datetime.now()
```

### Reference Format

```
taskstash://namespace/artifact-uuid
taskstash://documents/a1b2c3d4-e5f6-7890-abcd-ef1234567890
taskstash://api_results/search/nested-namespace/uuid
```

References are deterministic URIs computed from `namespace` and `id`. They are **not cryptographic** -- anyone with the reference and backend access can retrieve the content. Production systems need to add authentication (see [Exit Criteria](#3-requirements-expectations--exit-criteria)).

### Session

Sessions provide logical isolation for artifact operations. Defined in `src/yonk_taskstash/core/session.py`:

```python
class Session:
    def __init__(self, backend: StorageBackend, session_id: str = None, user_id: str = None)

    def store(content, namespace, metadata=None, content_type=TEXT,
              lifecycle=SESSION, ttl_seconds=None) -> Artifact
    def get(id_or_reference) -> Artifact | None
    def delete(id_or_reference) -> bool
    def query(namespace=None, filter=None, text_search=None, limit=100) -> list[Artifact]
    def list(namespace=None) -> list[Artifact]
    def close() -> None           # Deletes all SESSION-lifecycle artifacts
    def __enter__ / __exit__      # Context manager support
```

**Session scoping enforcement**: `get()` and `query()` filter by `session_id`. Session A cannot access Session B's artifacts. This is enforced at the application level (not database-level RLS), which is a known production gap.

### TaskStash (Facade)

The main entry point in `src/yonk_taskstash/core/stash.py`:

```python
class TaskStash:
    def __init__(self, backend: StorageBackend = None)  # Defaults to MemoryBackend

    # Convenience methods (use a "default" session internally)
    def store(content, namespace, ..., lifecycle=MANUAL) -> str   # Returns reference
    def get(reference) -> Artifact | None                         # Lazy expiry check
    def query(namespace=None, filter=None, text_search=None, limit=100) -> list[Artifact]
    def delete(reference) -> bool

    # Invalidation (bulk operations)
    def invalidate_namespace(namespace) -> int
    def invalidate_by_metadata(filter) -> int
    def invalidate_older_than(seconds) -> int
    def refresh_ttl(reference, ttl_seconds) -> Artifact

    # Session factory
    def session(session_id=None, user_id=None) -> Session

    # Factory constructors
    @classmethod def full_local(cls) -> TaskStash       # MemoryBackend
    @classmethod def production(cls, **kw) -> TaskStash  # Placeholder
```

**Critical design note**: `TaskStash.store()` defaults to `Lifecycle.MANUAL` (persistent). `Session.store()` defaults to `Lifecycle.SESSION` (auto-cleaned on close). This asymmetry is intentional -- the facade is for long-lived storage, sessions are for ephemeral data.

---

## 6. Storage Layer

All backends implement the abstract `StorageBackend` interface (`src/yonk_taskstash/storage/base.py`):

```python
class StorageBackend(ABC):
    def store(artifact: Artifact) -> None
    def get(artifact_id: str) -> Artifact | None
    def delete(artifact_id: str) -> bool
    def list_by_session(session_id: str) -> list[Artifact]
    def list_by_namespace(namespace: str, session_id: str = None) -> list[Artifact]
    def query(session_id, namespace=None, filter=None, text_search=None, limit=100) -> list
    def cleanup_session(session_id: str) -> int
    def cleanup_expired() -> int
    def delete_by_namespace(namespace: str) -> int
```

### MemoryBackend

**File:** `src/yonk_taskstash/storage/memory.py`

- Stores artifacts in a Python `dict[str, Artifact]`
- All operations are O(n) linear scans
- No persistence -- data lost on process exit
- No concurrency controls (not thread-safe)
- Best for: unit tests, development, single-request prototyping

### SQLiteBackend

**File:** `src/yonk_taskstash/storage/sqlite.py`

- Uses FTS5 virtual table for full-text search
- WAL mode enabled for concurrent reads
- `json_extract()` for metadata filtering
- Triggers keep FTS index synchronized
- Connection handling: fresh connection per operation (file-based) or persistent (`:memory:`)
- Best for: single-machine deployments, moderate scale

**Schema:**
```sql
CREATE TABLE artifacts (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    user_id TEXT,
    namespace TEXT NOT NULL,
    content TEXT NOT NULL,
    content_type TEXT DEFAULT 'text',
    lifecycle TEXT DEFAULT 'manual',
    ttl_seconds INTEGER,
    expires_at TEXT,
    metadata TEXT DEFAULT '{}',
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE INDEX idx_artifacts_session ON artifacts(session_id);
CREATE INDEX idx_artifacts_namespace ON artifacts(namespace);

CREATE VIRTUAL TABLE artifacts_fts USING fts5(id, content, content='artifacts', content_rowid='rowid');
```

### PostgresBackend

**File:** `src/yonk_taskstash/storage/postgres.py`

- Async implementation via `asyncpg` (sync wrappers provided)
- Connection pooling (min 2, max 10 by default)
- JSONB metadata with GIN indexing
- `tsvector` for full-text search
- `pgvector` for semantic search (vector embeddings)
- UUID native type for artifact IDs
- Best for: multi-user production, distributed architectures

---

## 7. The Middleware Interception Pattern

This is the core innovation. The middleware sits in the tool execution pipeline and transparently intercepts large outputs.

### Base Middleware

**File:** `src/yonk_taskstash/langchain/middleware.py`

```python
class TaskStashMiddleware:
    def __init__(
        self,
        stash: TaskStash = None,        # Auto-creates if None
        threshold: int = 5000,           # Characters; outputs larger get intercepted
        namespace: str = "auto",         # Where intercepted content is stored
        summary_length: int = 500,       # Preview size in replacement message
        include_reference: bool = True,  # Include fetch instructions
        auto_lifecycle: Lifecycle = MANUAL,
        auto_ttl: int = 3600,           # TTL in seconds
    )
```

The middleware tracks every reference it creates in `self._intercepted_refs`, enabling bulk cleanup after an agent run.

**Replacement message format:**
```
[Content auto-stored in TaskStash]
Size: 50,234 characters
Reference: taskstash://auto/a1b2c3d4-e5f6-7890-abcd-ef1234567890

Preview:
The dataset contains 500 customer records spanning October through December 2025. Enterprise accounts represent the largest segment with 127 active subscriptions.

Content summarized (50,234 chars total, showing key sentences within 500 chars).
Use taskstash_fetch("taskstash://auto/a1b2c3d4-e5f6-7890-abcd-ef1234567890") to retrieve the complete content.
```

### ContentAwareMiddleware

**File:** `src/yonk_taskstash/langchain/content_aware.py`

Extends `TaskStashMiddleware` with intelligent content-type detection. This is important because generic text truncation destroys the most useful information in structured data (column names, row counts, data types).

**Detection heuristics:**
- **JSON arrays**: Content starts with `[`, parses as JSON, first element is a dict
- **SQL tabular**: Lines match `col | col | col` pattern with `---+---+---` separator
- **Text**: Everything else (fallback)

**Two-tier threshold system:**

```
Content arrives (e.g., 3,000 chars of JSON)
         │
         ▼
  len > main threshold (5000)?
         │No
         ▼
  Pass through unchanged ──────────▶ Agent sees full content

  len > main threshold (5000)?
         │Yes
         ▼
  Detect content type
         │
    ┌────┼────┐
    │    │    │
  JSON  SQL  Text
    │    │    │
    ▼    ▼    ▼
  len > structured_bypass_threshold (2000)?
    │No        │Yes
    ▼          ▼
  Pass through  Intercept with structured summary
  unchanged     (preserves schema + sample rows)
```

**Why the two-tier system?** Small structured data (2,000-5,000 chars) is more token-efficient than its summary would be. The agent is better served by the complete 50-row JSON array than a summary that says "50 items, columns: id, name, email, sample: ...". But at 500 rows, the summary wins.

**JSON interception output:**
```
[JSON Array: 500 items, 45,234 chars]
Columns: id, name, email, status, created_at
Sample (3 of 500 items):
  {"id": 1, "name": "Alice", "email": "alice@example.com", "status": "active", ...}
  {"id": 2, "name": "Bob", "email": "bob@example.com", "status": "inactive", ...}
  {"id": 3, "name": "Charlie", "email": "charlie@example.com", "status": "active", ...}
Reference: taskstash://auto/a1b2c3d4-e5f6-7890-abcd-ef1234567890
497 additional items not shown. Use taskstash_fetch to retrieve all.
```

**SQL interception output:**
```
[SQL Result: 500 rows x 5 columns, 38,102 chars]
Columns: id | name | email | status | created_at
Sample (3 of 500 rows):
  1  | Alice   | alice@ex.com   | active   | 2024-01-01
  2  | Bob     | bob@ex.com     | inactive | 2024-01-15
  3  | Charlie | charlie@ex.com | active   | 2024-02-01
Reference: taskstash://auto/a1b2c3d4-e5f6-7890-abcd-ef1234567890
497 additional rows not shown. Use taskstash_fetch to retrieve all.
```

**Text interception output:**
```
[Text Document: 28,450 chars]
Preview: Sarah Chen presented the Q4 roadmap with three key initiatives. The team agreed to prioritize the authentication refactor, targeting a March 1 deadline. David Kim raised concerns about database migration timing.
Reference: taskstash://auto/b2c3d4e5-f6a7-8901-bcde-f12345678901
  To search: stash_search(query="...", reference="taskstash://auto/b2c3d4e5-...")
  To retrieve: stash_fetch(reference="taskstash://auto/b2c3d4e5-...")
```

Text documents are stored, summarized using **extractive sentence selection** (selecting the most important complete sentences via TF-IDF scoring), and -- critically -- submitted for background chunking and embedding via `_submit_for_indexing()`. This enables `stash_search` to find specific content within large documents (e.g., "What action items were assigned to Sarah?" in a 30KB meeting transcript). The extractive preview preserves key information from anywhere in the document, unlike truncation which only shows the beginning.

---

## 8. LangChain Integration

The LangChain integration is in `src/yonk_taskstash/langchain/` and provides three integration patterns, from least to most automatic.

### Pattern 1: Toolkit (Agent Gets TaskStash Tools)

Give the agent explicit tools to store, query, and fetch from TaskStash. The agent decides when to use them.

```python
from yonk_taskstash import TaskStash
from yonk_taskstash.langchain import TaskStashToolkit

stash = TaskStash()
toolkit = TaskStashToolkit(stash)

# Get all 7 tools
tools = toolkit.get_tools()

# Or filter to specific tools
toolkit = TaskStashToolkit(stash, include_tools=["stash_store", "stash_fetch", "stash_query"])
tools = toolkit.get_tools()
```

**Available tools:**

| Tool Name | Purpose | When Agent Uses It |
|-----------|---------|-------------------|
| `stash_store` | Store content, get reference | Agent wants to save data for later |
| `stash_fetch` | Get full content by reference | Agent needs complete data from a reference |
| `stash_query` | Search stored artifacts | Agent wants to find previously stored data |
| `stash_summarize` | Get extractive summary | Agent wants quick look without full fetch |
| `stash_list` | List artifacts in namespace | Agent wants inventory of stored data |
| `stash_delete` | Delete an artifact | Agent wants to clean up |
| `taskstash_invalidate` | Bulk delete by namespace | Agent wants to clean up a category |

**Full example with LangChain agent:**

```python
from langchain_openai import ChatOpenAI
from langchain.agents import create_tool_calling_agent, AgentExecutor
from langchain_core.prompts import ChatPromptTemplate
from yonk_taskstash import TaskStash
from yonk_taskstash.langchain import TaskStashToolkit

# 1. Create TaskStash with SQLite persistence
from yonk_taskstash.storage.sqlite import SQLiteBackend
stash = TaskStash(backend=SQLiteBackend("./data/taskstash.db"))

# 2. Create toolkit and get tools
toolkit = TaskStashToolkit(stash)
taskstash_tools = toolkit.get_tools()

# 3. Combine with your domain tools
all_tools = your_sql_tool + your_api_tool + taskstash_tools

# 4. Create agent with instructions about TaskStash
prompt = ChatPromptTemplate.from_messages([
    ("system", """You have access to TaskStash for managing large data.
     When tool outputs are large, store them with stash_store and work
     with the reference. Use stash_fetch when you need the full content."""),
    ("human", "{input}"),
    ("placeholder", "{agent_scratchpad}"),
])

llm = ChatOpenAI(model="gpt-4o")
agent = create_tool_calling_agent(llm, all_tools, prompt)
executor = AgentExecutor(agent=agent, tools=all_tools, verbose=True)

result = executor.invoke({"input": "Analyze our Q4 sales data"})
```

### Pattern 2: Middleware (Automatic Interception)

The middleware intercepts tool outputs transparently. The agent doesn't need to know about TaskStash -- it just sees summaries when outputs are large, and uses the `taskstash_fetch` tool to get full content.

```python
from yonk_taskstash import TaskStash
from yonk_taskstash.langchain import TaskStashMiddleware, ContentAwareMiddleware
from yonk_taskstash.langchain import TaskStashToolkit

stash = TaskStash()

# Basic middleware (extractive summarization for text)
middleware = TaskStashMiddleware(
    stash=stash,
    threshold=5000,          # Intercept outputs > 5000 chars
    namespace="auto",        # Store in "auto" namespace
    summary_length=500,      # 500-char preview
)

# OR: Content-aware middleware (structured summaries for JSON/SQL)
middleware = ContentAwareMiddleware(
    stash=stash,
    threshold=5000,
    structured_bypass_threshold=2000,  # Let small structured data through
    json_sample_rows=3,                # Show 3 sample rows for JSON
    sql_sample_rows=3,                 # Show 3 sample rows for SQL
)

# Get the fetch tool so the agent can retrieve full content
toolkit = TaskStashToolkit(stash, include_tools=["stash_fetch"])
fetch_tools = toolkit.get_tools()

# Wire into your agent
all_tools = your_tools + fetch_tools

# The middleware wraps tool calls:
# result = middleware._maybe_intercept(tool_output, tool_name)
# In a LangChain pipeline, this happens via wrap_tool_call()

# After agent completes, clean up:
middleware.invalidate_all()    # Delete all intercepted content
# OR
middleware.invalidate_namespace()  # Delete entire namespace
```

### Pattern 3: Decorator (Function-Level)

For wrapping specific functions that return large content:

```python
from yonk_taskstash import TaskStash
from yonk_taskstash.langchain import off_prompt

stash = TaskStash()

@off_prompt(stash, namespace="reports", min_tokens=500)
def generate_quarterly_report(quarter: str) -> str:
    """Generate a detailed quarterly report."""
    # ... returns 20,000 chars of report content
    return massive_report_string

# Instead of returning the full report, returns:
# "taskstash://reports/a1b2c3d4-e5f6-7890-abcd-ef1234567890"
reference = generate_quarterly_report("Q4-2025")

# Agent can fetch when needed
artifact = stash.get(reference)
print(artifact.content)  # Full 20,000 chars
```

### Putting It All Together: Production Agent Example

```python
from langchain_openai import ChatOpenAI
from langchain.agents import create_tool_calling_agent, AgentExecutor
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.tools import tool

from yonk_taskstash import TaskStash
from yonk_taskstash.storage.sqlite import SQLiteBackend
from yonk_taskstash.langchain import (
    ContentAwareMiddleware,
    TaskStashToolkit,
)


# --- Setup ---
stash = TaskStash(backend=SQLiteBackend("./data/agent.db"))

middleware = ContentAwareMiddleware(
    stash=stash,
    threshold=5000,
    structured_bypass_threshold=2000,
)

toolkit = TaskStashToolkit(stash, include_tools=["stash_fetch", "stash_query"])


# --- Your domain tools (middleware wraps these) ---
@tool
def query_database(sql: str) -> str:
    """Execute a SQL query and return results."""
    results = db.execute(sql)  # Could return 50,000 chars
    # Middleware will intercept if > threshold
    return format_results(results)

@tool
def read_document(path: str) -> str:
    """Read a document from the file system."""
    with open(path) as f:
        return f.read()  # Could be a 100-page PDF


# --- Wrap tools with middleware ---
wrapped_query = wrap_with_middleware(query_database, middleware)
wrapped_read = wrap_with_middleware(read_document, middleware)


# --- Agent ---
all_tools = [wrapped_query, wrapped_read] + toolkit.get_tools()

prompt = ChatPromptTemplate.from_messages([
    ("system", """You are a data analyst. When tool outputs show
    '[Content auto-stored in TaskStash]', use stash_fetch with the
    reference to get full content when needed for detailed analysis.
    For overview questions, the preview may be sufficient."""),
    ("human", "{input}"),
    ("placeholder", "{agent_scratchpad}"),
])

llm = ChatOpenAI(model="gpt-4o")
agent = create_tool_calling_agent(llm, all_tools, prompt)
executor = AgentExecutor(agent=agent, tools=all_tools)

# --- Run ---
result = executor.invoke({"input": "Compare Q3 and Q4 revenue by region"})

# --- Cleanup ---
print(f"Cleaned up {middleware.invalidate_all()} intercepted artifacts")
```

---

## 9. Langflow Integration

The Langflow integration provides visual drag-and-drop components for building AI workflows with TaskStash.

### Architecture

Langflow components live in `src/yonk_taskstash/langflow/components/` — a single hierarchy with try/except import stubs so they work both with and without Langflow installed.

### Available Components

| Component | Icon | Purpose |
|-----------|------|---------|
| **TaskStash Memory** | database | Creates and configures a TaskStash instance |
| **Stash Store** | save | Stores content, returns reference |
| **Stash Fetch** | download | Retrieves full content by reference |
| **Stash Query** | search | Searches stored artifacts |
| **Stash Summarize** | file-text | Gets extractive summary (auto/llm/extractive/truncate modes) |
| **Stash Invisible** | eye-off | Automatic interception (invisible mode) |
| **TaskStash Agent** | bot | Agent with built-in tool output interception |

### Component Data Flow Pattern

All components communicate via Langflow's `Data` wrapper objects. The wrapping/unwrapping pattern is consistent across all components:

```python
# Output: Wrap result in Data for Langflow
return Data(data={
    "stash": stash_instance,
    "reference": "taskstash://docs/abc123",
    "content": "...",
})

# Input: Unwrap Data from upstream component
stash_input = self.stash  # Could be Data or TaskStash
if hasattr(stash_input, "data") and isinstance(stash_input.data, dict):
    stash = stash_input.data.get("stash")
else:
    stash = stash_input
```

### Example Flow 1: Basic Document Store & Retrieve

```
┌────────────────┐     ┌────────────┐     ┌────────────┐
│ TaskStash      │────▶│ Stash      │────▶│ Text       │
│ Memory         │     │ Store      │     │ Output     │
│                │     │            │     │            │
│ backend:sqlite │     │ namespace: │     │ Shows ref  │
│ path: ./db     │     │ "documents"│     │            │
└────────────────┘     └────────────┘     └────────────┘
       │                     ▲
       │                     │
       │               ┌─────┴──────┐
       │               │ File       │
       │               │ Loader     │
       │               │            │
       │               │ input.pdf  │
       │               └────────────┘
       │
       │               ┌────────────┐     ┌────────────┐
       └──────────────▶│ Stash      │────▶│ Chat       │
                       │ Fetch      │     │ Output     │
                       │            │     │            │
                       │ ref: from  │     │ Full text  │
                       │ store      │     │            │
                       └────────────┘     └────────────┘
```

### Example Flow 2: RAG Chatbot with TaskStash

```
┌──────────┐     ┌──────────────┐     ┌──────────┐     ┌──────────┐     ┌──────────┐
│ Chat     │────▶│ Stash        │────▶│ Prompt   │────▶│ OpenAI   │────▶│ Chat     │
│ Input    │     │ Query        │     │ Template │     │ LLM      │     │ Output   │
│          │     │              │     │          │     │          │     │          │
│ question │     │ namespace:   │     │ context: │     │ gpt-4o   │     │ response │
│          │     │ "documents"  │     │ {results}│     │          │     │          │
│          │     │ limit: 3     │     │ question:│     │          │     │          │
│          │     │              │     │ {input}  │     │          │     │          │
└──────────┘     └──────────────┘     └──────────┘     └──────────┘     └──────────┘
                        ▲
                        │
                 ┌──────┴──────┐
                 │ TaskStash   │
                 │ Memory      │
                 │             │
                 │ SQLite +    │
                 │ embeddings  │
                 └─────────────┘
```

### Example Flow 3: Secure RAG with PII + Invisible Mode

```
┌──────────┐     ┌──────────────┐     ┌──────────┐     ┌──────────┐     ┌──────────┐     ┌──────────┐
│ Chat     │────▶│ Stash        │────▶│ Stash    │────▶│ Prompt   │────▶│ LLM      │────▶│ Chat     │
│ Input    │     │ Invisible    │     │ Query    │     │ Template │     │          │     │ Output   │
│          │     │              │     │          │     │          │     │          │     │          │
│          │     │ trigger:     │     │ ns:      │     │          │     │          │     │          │
│          │     │ size+pii     │     │ "docs"   │     │          │     │          │     │          │
│          │     │ pii: redact  │     │          │     │          │     │          │     │          │
└──────────┘     └──────────────┘     └──────────┘     └──────────┘     └──────────┘     └──────────┘
```

### The TaskStash Agent Component

The `TaskStashAgent` component is a self-contained agent node that wraps all tool execution with automatic interception:

```
┌──────────────────────────────────────┐
│         TaskStash Agent              │
│                                      │
│  Inputs:                             │
│    - llm: LanguageModel              │
│    - tools: [Tool, Tool, ...]        │
│    - stash: TaskStash Memory         │
│    - threshold: 5000                 │
│    - input_value: "user query"       │
│                                      │
│  Internal Flow:                      │
│    1. Wraps all tool.invoke() calls  │
│    2. Adds taskstash_fetch tool      │
│    3. Injects system prompt about    │
│       TaskStash references           │
│    4. Runs LangChain AgentExecutor   │
│                                      │
│  Output:                             │
│    - agent_response: Message         │
└──────────────────────────────────────┘
```

### Deployment to Langflow

**Option A: Docker volume mount (recommended for development)**

```bash
docker run -d \
  --name langflow \
  -p 7860:7860 \
  -v $(pwd)/src/yonk_taskstash/langflow/components:/app/langflow/components/taskstash \
  -v langflow-data:/app/data \
  langflowai/langflow:latest
```

**Option B: Custom Dockerfile (recommended for production)**

```dockerfile
FROM langflowai/langflow:latest
RUN pip install "yonk-taskstash[langflow,sqlite]"
```

**Option C: Docker Compose (full stack)**

```yaml
version: '3.8'
services:
  langflow:
    build:
      context: .
      dockerfile: Dockerfile.langflow
    ports:
      - "7860:7860"
    environment:
      - OPENAI_API_KEY=${OPENAI_API_KEY}
      - TASKSTASH_STORAGE_BACKEND=postgres
      - TASKSTASH_SQLITE_PATH=/app/data/taskstash.db
    volumes:
      - ./data:/app/data

  postgres:
    image: pgvector/pgvector:pg17
    environment:
      - POSTGRES_USER=taskstash
      - POSTGRES_PASSWORD=${POSTGRES_PASSWORD}
      - POSTGRES_DB=taskstash
    volumes:
      - pgdata:/var/lib/postgresql/data

volumes:
  pgdata:
```

### Stub Pattern for Testing Without Langflow

When Langflow is not installed, the integration provides stub classes so unit tests work:

```python
try:
    from langflow.custom import Component
    from langflow.io import HandleInput, StrInput, BoolInput, DropdownInput, Output
    from langflow.schema import Data
    LANGFLOW_AVAILABLE = True
except ImportError:
    LANGFLOW_AVAILABLE = False
    # Minimal stubs that mirror the Langflow API
    class Component: ...
    class Data:
        def __init__(self, data=None, **kwargs):
            self.data = data or {}
    # ... more stubs
```

This allows running `pytest` without a full Langflow installation.

---

## 10. MCP Server Integration

The MCP (Model Context Protocol) server enables TaskStash to work with Claude Desktop, Claude Code, and any MCP-compatible client.

### When MCP Is the Right Choice

MCP is ideal when:

- **Interactive use with Claude Desktop/Code.** A developer exploring data, analyzing logs, or writing reports benefits from the LLM deciding what to stash. The LLM can see a 10KB API response, decide "I only need the summary field," and skip storage entirely. That judgment is valuable.
- **Exploratory workflows.** When you don't know in advance what will be large or what the agent will need, letting the LLM decide is reasonable.
- **Single-user environments.** Claude Desktop is one user, one session. The global singleton pattern is fine here.
- **Rapid prototyping.** MCP requires zero code changes to your agent -- just configure the server and the tools appear.

### When MCP Is NOT the Right Choice

MCP has fundamental limitations that make it unsuitable as the *sole* integration for production systems:

**1. The LLM decides, not your policy.**

MCP tools are suggestions. The LLM sees `taskstash_store` in its tool list and *may* use it. But:
- A model with poor tool-use calibration might never call it
- A rushed agent under token pressure might skip the storage step to get to an answer faster
- Different models (GPT-4o vs Claude vs Llama) have different tool-use tendencies
- Prompt changes can inadvertently suppress tool use

You cannot write an SLA that says "we guarantee PII never reaches the LLM" if the mechanism depends on the LLM choosing to intercept it.

**2. The LLM sees the full output first.**

With MCP, the tool output flows to the LLM *first*, and then the LLM decides whether to store it. This means:
- The full 50KB already consumed context window tokens
- The PII already left your infrastructure and hit the LLM API
- The cost was already incurred

Even if the LLM then stores the content, the damage (cost, data leakage) already happened. MCP interception is *after-the-fact*, not *preventive*.

**3. No batch or pipeline support.**

MCP is a request-response protocol tied to a single LLM conversation. It doesn't support:
- Batch processing of documents through a pipeline
- Multi-agent architectures where interception needs to happen at the orchestrator level
- Automated ingestion workflows with no LLM in the loop

**4. Global singleton limits multi-tenancy.**

The current MCP server shares one TaskStash instance across all calls. There's no concept of "this user's artifacts vs. that user's artifacts" at the MCP level.

### Recommendation: MCP as Complement, Not Foundation

Use MCP for developer-facing tools (Claude Desktop, Claude Code) and exploratory use. Use **LangChain middleware** or **Langflow components** as the structural foundation for production pipelines. The hybrid approach:

```
Production Pipeline:
  [Tool] → [Middleware: FORCES interception] → [LLM] → [MCP tools available for fetch/query]

Developer Workflow:
  [Claude Desktop] → [MCP: tools for store/fetch/query] → [TaskStash]
```

### Architecture

**File:** `src/yonk_taskstash/mcp/server.py`

The server uses the official Anthropic MCP Python SDK with a registry-based tool discovery pattern:

```
TOOL_REGISTRY (tools.py)   →  maps tool names to async handler functions
TOOL_SCHEMAS (schemas.py)  →  provides descriptions + JSON Schema for each tool
MCP Server (server.py)     →  combines both for list_tools() and call_tool()
```

**Transport:** stdio (standard input/output), making it compatible with Claude Desktop's process-based MCP server model.

### Available MCP Tools

| Tool | Parameters | Returns |
|------|-----------|---------|
| `taskstash_store` | content, namespace, metadata? | reference, size_bytes |
| `taskstash_query` | query?, namespace?, limit? | results array with previews |
| `taskstash_fetch` | reference | full content |
| `taskstash_summarize` | reference, max_length? | extractive summary |
| `taskstash_list` | namespace? | artifact metadata array |
| `taskstash_delete` | reference | status |

### Configuration

**Claude Desktop (`claude_desktop_config.json`):**

```json
{
  "mcpServers": {
    "taskstash": {
      "command": "python",
      "args": ["-m", "yonk_taskstash.mcp"]
    }
  }
}
```

**Claude Code (`.mcp.json` in project root):**

```json
{
  "mcpServers": {
    "taskstash": {
      "command": "python",
      "args": ["-m", "yonk_taskstash.mcp"]
    }
  }
}
```

The MCP server reads `.taskstash.yaml` if present, or defaults to in-memory storage.

### Design Note: Global Singleton

The current MCP server uses a global `_stash` singleton:

```python
_stash = None

def get_stash():
    global _stash
    if _stash is None:
        _stash = TaskStash()
    return _stash
```

This means all MCP tool calls share one TaskStash instance. For production multi-user deployments, this needs to be replaced with session-aware stash creation.

---

## 11. Configuration System

**File:** `src/yonk_taskstash/core/config.py`

Configuration is loaded from `.taskstash.yaml` with environment variable overrides:

```yaml
version: "1"

storage:
  backend: sqlite              # memory | sqlite | postgres
  sqlite:
    path: ./data/taskstash.db
  postgres:
    host: localhost
    port: 5432
    database: taskstash
    user: taskstash
    # password: from TASKSTASH_DB_PASSWORD env var

embeddings:
  provider: sentence-transformers  # none | openai | ollama | sentence-transformers | nim
  model: all-MiniLM-L6-v2
  options:
    device: cpu                    # cpu | cuda | mps

summarization:
  provider: none               # none | extractive | openai | ollama | transformers | llama-cpp | external

pii:
  enabled: false
  action: redact               # redact | mask | block | warn | allow
  detect_types: [email, phone, ssn, credit_card]
  confidence_threshold: 0.9

invisible_mode:
  enabled: false
  default_namespace: invisible
  pass_through_summary: true
  summary_max_length: 200

multitenancy:
  enabled: false
  isolation_level: soft        # none | soft | strict
```

**Environment variables:**
- `TASKSTASH_DB_PASSWORD` -- PostgreSQL password
- `TASKSTASH_OPENAI_API_KEY` -- OpenAI API key
- `OPENAI_API_KEY` -- Fallback for OpenAI
- `TASKSTASH_OLLAMA_HOST` -- Ollama server URL
- `TASKSTASH_STORAGE_BACKEND` -- Override backend selection

---

## 12. Chunking, Embedding & Retrieval Pipeline

This section describes how TaskStash breaks stored content into searchable chunks,
embeds those chunks for semantic similarity, and exposes hybrid search (FTS + vector
+ metadata) so the LLM can retrieve **just the relevant fragments** instead of
fetching entire artifacts.

### 12.0 Why This Matters

Today the LLM has two retrieval modes:

| Mode | Tokens | When it helps |
|------|--------|---------------|
| **Summary** (~200 tokens) | Cheap | "How many rows?" / "What columns?" |
| **Full fetch** (all content) | Expensive | "Process every row" |

The missing middle is **targeted retrieval**: "Show me the 5 Enterprise customers"
or "Find the row where email contains 'acme.com'." Without chunking and search,
the LLM must fetch the entire 35,000-token artifact to answer a question about
3 rows. Chunked hybrid search closes this gap.

```
              THE THREE RETRIEVAL MODES

  ┌─────────────────────────────────────────────────────────────────┐
  │                                                                 │
  │  MODE 1: SUMMARY  (exists today)                                │
  │  ─────────────────                                              │
  │  LLM receives ~200 tokens: column names, row count, 3 samples  │
  │  Good for: overview, schema discovery, "how big is this?"       │
  │  Cost: minimal                                                  │
  │                                                                 │
  │  MODE 2: TARGETED SEARCH  (NEW — this section)                  │
  │  ────────────────────────                                       │
  │  LLM asks: "find Enterprise customers" or "rows with status=X" │
  │  TaskStash returns 5-20 matching chunks (ranked by relevance)   │
  │  Good for: needle-in-haystack, filtering, similarity questions  │
  │  Cost: proportional to answer size, not data size               │
  │                                                                 │
  │  MODE 3: FULL FETCH  (exists today)                             │
  │  ─────────────────────                                          │
  │  LLM receives the entire artifact                               │
  │  Good for: aggregation across all rows, export, full processing │
  │  Cost: high (all tokens)                                        │
  │                                                                 │
  └─────────────────────────────────────────────────────────────────┘
```

---

### 12.1 Architecture Overview

```
  STORE PATH (middleware intercepts tool output)
  ═══════════════════════════════════════════════════════════════════

  Tool Output (142,350 chars)
       │
       ▼
  ┌──────────────────────────────────────────────────────────────┐
  │  ContentAwareMiddleware._maybe_intercept()                   │
  │                                                              │
  │  CRITICAL PATH (sync, blocking — must be fast)               │
  │  ──────────────────────────────────────────────               │
  │  1. Detect content type (JSON / SQL / text)                  │
  │  2. Store full artifact in backend (one row)                 │
  │  3. Build summary (~200 tokens)                              │
  │  4. Return summary + reference to LLM                        │
  │                                                              │
  │  BACKGROUND PATH (async, non-blocking — can be slow)         │
  │  ────────────────────────────────────────────────             │
  │  5. Submit chunking + embedding job to ChunkIndexer          │
  │     └─► returns immediately, work happens in background      │
  │                                                              │
  └──────────────────────────────────────────────────────────────┘
       │                              │
       ▼ (immediate)                  ▼ (background)
  ┌──────────────┐           ┌──────────────────────────────────┐
  │ LLM receives │           │  ChunkIndexer (background)       │
  │ summary +    │           │                                  │
  │ reference    │           │  1. Split content → chunks        │
  │              │           │  2. Flatten chunks → embed text   │
  │              │           │  3. Generate embeddings (batch)   │
  │              │           │  4. Store chunks + vectors        │
  │              │           │  5. Mark artifact as "indexed"    │
  │              │           │                                  │
  └──────────────┘           └──────────────────────────────────┘


  SEARCH PATH (LLM calls stash_search tool)
  ═══════════════════════════════════════════════════════════════════

  LLM: stash_search(query="Enterprise plan", reference="taskstash://auto/abc")
       │
       ▼
  ┌──────────────────────────────────────────────────────────────┐
  │  HybridSearchEngine                                          │
  │                                                              │
  │  1. Check indexing status                                    │
  │     ├─ indexed=true  → run hybrid search (FTS + vector)     │
  │     └─ indexed=false → fall back to FTS on full artifact     │
  │                                                              │
  │  2. FTS search over chunks → ranked set A                   │
  │  3. Vector similarity search → ranked set B                 │
  │  4. Reciprocal Rank Fusion (RRF) → merged ranking           │
  │  5. Apply metadata filters (namespace, tool, content_type)  │
  │  6. Return top-K chunks                                     │
  │                                                              │
  └──────────────────────────────────────────────────────────────┘
       │
       ▼
  LLM receives 5-20 relevant chunks (~500-2,000 tokens)
  instead of the full 35,500-token artifact
```

---

### 12.2 Chunking Strategies

Content type determines how artifacts are split into chunks. Each strategy
produces chunks that are semantically meaningful, appropriately sized for
embedding models, and independently useful when returned to the LLM.

#### 12.2.1 JSON Array Chunking

**Trigger:** `content_type == "json_array"` (detected by ContentAwareMiddleware)

**Strategy:** One chunk per object (row). This is the natural semantic boundary
for tabular data — each row is a self-contained record.

```
Input:  [{"id":1,"name":"Alice","plan":"Enterprise"}, {"id":2,...}, ... 2847 objects]

Output: 2,847 chunks, each containing one JSON object

Chunk 0: {"id":1,"name":"Alice","plan":"Enterprise","status":"active","created_at":"2025-10-01"}
Chunk 1: {"id":2,"name":"Bob","plan":"Starter","status":"active","created_at":"2025-10-03"}
...
Chunk 2846: {"id":2847,"name":"Zara","plan":"Pro","status":"churned","created_at":"2025-12-28"}
```

**Chunk metadata** (stored per chunk for filtered retrieval):
```python
{
    "parent_artifact_id": "a1b2c3d4-...",
    "chunk_index": 0,              # position in original array
    "chunk_strategy": "json_row",
    "total_chunks": 2847,
    "keys": ["id", "name", "plan", "status", "created_at"],
}
```

**Mega-row handling:** If a single JSON object exceeds `max_chunk_size` (e.g.,
a deeply nested document), fall through to recursive text chunking on the
serialized object.

#### 12.2.2 SQL Tabular Chunking

**Trigger:** `content_type == "sql_tabular"` (pipe-separated table detected)

**Strategy:** One chunk per row, with column headers prepended. This ensures
each chunk is self-describing — the LLM doesn't need to cross-reference a
separate header row.

```
Input:
| id | name    | plan       | status |
|----|---------|------------|--------|
|  1 | Alice   | Enterprise | active |
|  2 | Bob     | Starter    | active |
...

Output:
Chunk 0: "id: 1 | name: Alice | plan: Enterprise | status: active"
Chunk 1: "id: 2 | name: Bob | plan: Starter | status: active"
...
```

**Why prepend headers:** A chunk containing `"1 | Alice | Enterprise | active"`
is useless to the LLM without knowing which field is which. Including
`"id: 1 | name: Alice | ..."` makes each chunk independently interpretable
and also produces much better embeddings (the embedding model understands
"name: Alice" far better than a bare "Alice" in a pipe-delimited string).

#### 12.2.3 Plain Text Chunking

**Trigger:** `content_type == "text"` (default fallback)

**Strategy:** Recursive split with overlap.

```
Split hierarchy (try each level, fall through if chunks still too large):
  1. Double newline (paragraph boundaries)
  2. Single newline (line boundaries)
  3. Sentence boundaries (regex: (?<=[.!?])\s+)
  4. Word boundaries (space)

Parameters:
  max_chunk_size:  computed from embedding model's max_seq_length
                   (model.max_seq_length × 3.5 chars/token × 0.85 headroom)
  overlap:         10-15% of max_chunk_size (preserves context at boundaries)
```

**Overlap rationale:** Without overlap, a question like "What did Alice say about
the Enterprise plan?" might miss the answer if "Alice" is at the end of chunk N
and "Enterprise plan" is at the start of chunk N+1. A 10-15% overlap window
ensures cross-boundary context is preserved in at least one chunk.

```
  ┌──────────────────────────────────────────────────────────┐
  │  Chunk 0: "Alice joined Acme Corp in 2024. She manages  │
  │  the Enterprise account for the APAC region. Her team..." │
  └──────────────────────────────────────────────────────────┘
                                        ▲ overlap ▼
  ┌──────────────────────────────────────────────────────────┐
  │  Chunk 1: "...the Enterprise account for the APAC        │
  │  region. Her team closed 14 deals in Q4, totaling..."    │
  └──────────────────────────────────────────────────────────┘
```

#### 12.2.4 Chunk Sizing (model-aware)

All strategies respect the embedding model's context window. Chunks that
exceed `max_seq_length` get silently truncated by sentence-transformers,
destroying embedding quality.

```python
def compute_max_chunk_size(model: EmbeddingProvider) -> int:
    """Derive safe chunk size from the model's token limit."""
    max_tokens = model.max_seq_length       # e.g., 256 for MiniLM
    chars_per_token = 3.5                   # conservative average
    headroom = 0.85                         # 15% safety margin
    return int(max_tokens * chars_per_token * headroom)
    # MiniLM: 256 × 3.5 × 0.85 ≈ 761 chars per chunk
```

| Model | max_seq_length | Safe chunk size |
|-------|---------------|-----------------|
| all-MiniLM-L6-v2 | 256 tokens | ~761 chars |
| all-mpnet-base-v2 | 384 tokens | ~1,142 chars |
| text-embedding-3-small | 8,191 tokens | ~24,367 chars |
| nomic-embed-text | 8,192 tokens | ~24,370 chars |

For JSON row chunking, most rows are well under 761 chars. The size limit
matters mainly for text chunking and mega-rows.

---

### 12.3 Embedding: What Gets Embedded

**Critical design decision:** We embed a **flattened natural-language
representation** of each chunk, not the raw stored content.

#### 12.3.1 The Problem with Embedding Raw JSON

Embedding models (sentence-transformers, OpenAI, etc.) are trained on natural
language. Raw JSON syntax is noise to them:

```json
{"id": 1, "name": "Alice Chen", "plan": "Enterprise", "status": "active"}
```

The braces, colons, and quotes consume tokens without adding semantic signal.
The model doesn't understand that `"plan"` is a field name and `"Enterprise"`
is its value — it sees them as unrelated tokens.

#### 12.3.2 Flattening for Embedding Quality

Each chunk stores two representations:

| Field | Purpose | Example |
|-------|---------|---------|
| `content` | Raw chunk (returned to LLM) | `{"id":1,"name":"Alice Chen","plan":"Enterprise"}` |
| `embedding_text` | Flattened text (used for embedding) | `"name: Alice Chen, plan: Enterprise, status: active"` |

**Flattening rules by content type:**

**JSON objects:**
```python
def flatten_json_for_embedding(obj: dict) -> str:
    """Convert JSON object to embeddable natural-language text."""
    parts = []
    for key, value in obj.items():
        if key in ("id", "rowid", "pk"):   # skip surrogate keys
            continue
        if value is None:
            continue
        # snake_case → "Title Case"
        label = key.replace("_", " ").title()
        parts.append(f"{label}: {value}")
    return ", ".join(parts)

# Input:  {"id": 1, "name": "Alice Chen", "plan": "Enterprise", "status": "active"}
# Output: "Name: Alice Chen, Plan: Enterprise, Status: active"
```

**SQL rows** (already flattened during chunking — `"name: Alice | plan: Enterprise"`).

**Plain text** chunks are embedded as-is (they're already natural language).

#### 12.3.3 Embedding Providers

All implement `EmbeddingProvider` ABC with `async embed(text)`,
`async embed_batch(texts)`, and `dimension` property.

| Provider | Model | Dimension | Notes |
|----------|-------|-----------|-------|
| sentence-transformers | all-MiniLM-L6-v2 | 384 | Local, no API key, lazy-loaded |
| sentence-transformers | all-mpnet-base-v2 | 768 | Higher quality, larger model |
| openai | text-embedding-3-small | 1536 | Requires API key |
| ollama | nomic-embed-text | varies | Requires local Ollama server |
| nim | varies | varies | NVIDIA NIM platform |

**Lazy loading:** Models are not loaded until the first `embed()` call. A
dimension lookup table (`MODEL_DIMENSIONS` in `sentence_transformers.py`)
avoids loading the model just to check dimensionality.

**Truncation warning:** `SentenceTransformersEmbeddingProvider._warn_if_truncated()`
logs a warning when input text exceeds `model.max_seq_length`, since
sentence-transformers silently truncates without error. This catches
mis-configured chunk sizes early.

### Summarization Providers

| Provider | Model | Latency | Dependencies | Notes |
|----------|-------|---------|--------------|-------|
| **extractive** | N/A (TF-IDF) | <1ms/KB | Zero | Default. Selects important sentences via TF-IDF scoring (60%) + position bias (25%) + length normalization (15%). Deterministic, no API key needed. Auto-upgrades to TextRank when `nltk` is installed. |
| transformers | facebook/bart-large-cnn | 100-500ms | `transformers`, `torch` | Local neural summarization |
| llama-cpp | Any GGUF model | 200-1000ms | `llama-cpp-python` | Efficient local LLM inference |
| openai | gpt-4o-mini | 500-2000ms | `openai` | API-based, highest quality |
| ollama | llama3, mistral | 200-1000ms | `ollama` running locally | Local LLM server |
| external | Custom endpoint | varies | `httpx` | Custom summarization API |

**Extractive vs. LLM summarization**: Extractive is the default for all preview/summary paths (middleware, MCP tools, Langflow components). It runs synchronously on the critical path with sub-millisecond latency. LLM providers are available via the `SummarizationConfig` for use cases requiring abstractive summarization — the Langflow `StashSummarize` component supports `auto | llm | extractive | truncate` mode selection, where `auto` uses the configured LLM provider if available, falling back to extractive.

The middleware and MCP layers use extractive summarization directly (via `smart_summarize()`) because they operate on the hot path where async LLM calls would add unacceptable latency. To use LLM summarization, configure a provider in `.taskstash.yaml` and use the `StashSummarize` component or `StashSummarizeTool` with an LLM provider.

---

### 12.4 Non-Blocking Pipeline Design

Chunking and embedding are **expensive operations** that must not block the
middleware's critical path. A 2,847-row JSON array might take 5-30 seconds to
chunk and embed (depending on model and hardware). The LLM cannot wait.

#### 12.4.1 Two-Phase Store

The store path is split into two phases:

```
Phase 1: CRITICAL PATH (sync, ≤50ms)
──────────────────────────────────────
  1. Store full artifact as a single row (existing behavior)
  2. Generate summary (existing behavior)
  3. Return summary + reference to LLM
  4. Submit background indexing job

Phase 2: BACKGROUND INDEXING (async, 1-30s)
──────────────────────────────────────
  5. Split content into chunks (CPU, fast)
  6. Flatten chunks → embedding text (CPU, fast)
  7. Batch-embed all chunks (CPU/GPU or API, slow)
  8. Store chunks + vectors in backend
  9. Set artifact.index_status = "ready"
```

**The LLM never waits for Phase 2.** It gets the summary immediately and
can start reasoning. If it later calls `stash_search`, the search engine
checks `index_status` and gracefully degrades:

| index_status | Search behavior |
|-------------|----------------|
| `"ready"` | Full hybrid search (FTS + vector + metadata) |
| `"indexing"` | FTS-only on full artifact content (still useful) |
| `"failed"` | FTS-only, log warning, surface error in search results |
| `"skipped"` | FTS-only (embeddings disabled in config) |

This means search **always works** — it just gets better once indexing completes.

#### 12.4.2 ChunkIndexer: Background Worker

```python
class ChunkIndexer:
    """Non-blocking chunk + embed pipeline.

    Accepts indexing jobs and processes them in the background
    without blocking the calling thread.
    """

    def __init__(
        self,
        backend: StorageBackend,
        embedding_provider: EmbeddingProvider | None,
        executor: ThreadPoolExecutor | None = None,
        max_workers: int = 2,
    ):
        self._backend = backend
        self._embedder = embedding_provider
        self._executor = executor or ThreadPoolExecutor(
            max_workers=max_workers,
            thread_name_prefix="taskstash-indexer",
        )
        self._futures: dict[str, Future] = {}  # artifact_id → Future

    def submit(self, artifact: Artifact) -> None:
        """Submit an artifact for background chunking + embedding.

        Returns immediately. The indexing work happens in a background
        thread (for CPU-bound embedding) or via asyncio (for API-based
        embedding).
        """
        future = self._executor.submit(self._index_artifact, artifact)
        self._futures[str(artifact.id)] = future
        future.add_done_callback(
            lambda f: self._on_complete(str(artifact.id), f)
        )

    def is_ready(self, artifact_id: str) -> bool:
        """Check if an artifact's chunks are indexed and searchable."""
        future = self._futures.get(artifact_id)
        if future is None:
            return False  # never submitted — or already cleaned up
        return future.done() and not future.exception()

    def _index_artifact(self, artifact: Artifact) -> int:
        """Chunk, embed, and store. Runs in background thread.

        Returns the number of chunks created.
        """
        # 1. Update status
        self._set_index_status(artifact, "indexing")

        # 2. Chunk
        chunker = get_chunker(artifact.content_type)
        chunks = chunker.split(artifact.content, artifact.metadata)

        # 3. Flatten for embedding
        embedding_texts = [
            chunker.flatten_for_embedding(chunk) for chunk in chunks
        ]

        # 4. Embed (batch)
        embeddings = None
        if self._embedder is not None:
            # Bridge async → sync for this thread
            embeddings = asyncio.run(
                self._embedder.embed_batch(embedding_texts)
            )

        # 5. Store chunks
        self._backend.store_chunks(
            artifact_id=str(artifact.id),
            chunks=chunks,
            embedding_texts=embedding_texts,
            embeddings=embeddings,
        )

        # 6. Mark ready
        self._set_index_status(artifact, "ready")
        return len(chunks)
```

#### 12.4.3 Threading Model

The non-blocking design uses different concurrency strategies depending on
the embedding provider type:

```
  ┌──────────────────────────────────────────────────────────────┐
  │  Embedding Provider Type     │  Concurrency Strategy          │
  │──────────────────────────────│────────────────────────────────│
  │  sentence-transformers       │  ThreadPoolExecutor            │
  │  (CPU-bound, local model)    │  Separate thread avoids        │
  │                              │  blocking the event loop or    │
  │                              │  the middleware's sync path.   │
  │                              │  model.encode() releases GIL   │
  │                              │  for numpy/torch operations.   │
  │──────────────────────────────│────────────────────────────────│
  │  OpenAI / Ollama / NIM       │  asyncio.run() in thread       │
  │  (IO-bound, API calls)       │  Background thread runs its    │
  │                              │  own event loop. API calls are  │
  │                              │  IO-bound → thread concurrency  │
  │                              │  is fine (no GIL contention).   │
  │──────────────────────────────│────────────────────────────────│
  │  None (embeddings disabled)  │  ThreadPoolExecutor            │
  │                              │  Still chunks for FTS — just   │
  │                              │  skips the embedding step.     │
  └──────────────────────────────────────────────────────────────┘
```

**Why ThreadPoolExecutor (not asyncio tasks):** The middleware layer is
synchronous (LangChain tool wrapping is sync). Spawning an `asyncio.Task`
from sync code requires an event loop, which may not exist or may belong to
a framework (FastAPI, Jupyter). A `ThreadPoolExecutor` is event-loop-agnostic
and works everywhere. The thread calls `asyncio.run()` internally if needed
for async embedding providers, with its own private loop.

**Worker pool sizing:** Default `max_workers=2`. Chunking is fast (pure Python
string operations), so the bottleneck is embedding. Two workers allow one
artifact to be embedding while the next is being chunked, without over-
subscribing CPU for local models.

#### 12.4.4 Batch Embedding Optimization

Embedding 2,847 chunks one-at-a-time would make 2,847 API calls (for OpenAI)
or 2,847 forward passes (for sentence-transformers). Instead, `embed_batch()`
processes chunks in configurable batches:

```python
# sentence-transformers: single model.encode() call for entire batch
embeddings = model.encode(texts, convert_to_numpy=True, batch_size=128)

# OpenAI: single API call supports up to 2048 inputs
response = await client.embeddings.create(input=texts, model=model)

# Ollama: batched via concurrent requests (configurable concurrency)
```

**Batch size tuning:**

| Provider | Default batch | Limit | Notes |
|----------|--------------|-------|-------|
| sentence-transformers | 128 | Memory-bound | Larger batch = more VRAM/RAM |
| OpenAI | 2048 | API limit | Single request, billed per token |
| Ollama | 32 | Server-bound | Concurrent HTTP requests |

For a 2,847-chunk JSON array with sentence-transformers at batch_size=128,
that's 23 forward passes — typically 3-8 seconds on CPU, <1 second on GPU.

#### 12.4.5 Failure Handling and Retry

Background indexing failures must not affect the critical path or lose the
full artifact (which is already safely stored in Phase 1).

```
Failure Scenario             │ Behavior
─────────────────────────────│────────────────────────────────────────
Embedding provider unavail.  │ index_status="failed", FTS still works
Model OOM (local)            │ Log error, set "failed", no retry
API rate limit (OpenAI)      │ Exponential backoff, 3 retries
Partial batch failure        │ Store successful chunks, re-queue failed
Backend write failure        │ Retry once, then mark "failed"
Process killed mid-index     │ On restart, find "indexing" artifacts
                             │ and re-queue them (idempotent)
```

**Idempotent re-indexing:** If chunks already exist for an artifact, `store_chunks`
replaces them (DELETE + INSERT in a transaction). This makes it safe to re-index
on startup without duplicating chunks.

---

### 12.5 Storage Schema: Chunks Table

Chunks are stored in a dedicated table linked to the parent artifact.

#### 12.5.1 PostgreSQL Schema (with pgvector)

```sql
-- Requires: CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE artifact_chunks (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    artifact_id   UUID NOT NULL REFERENCES artifacts(id) ON DELETE CASCADE,
    chunk_index   INTEGER NOT NULL,
    content       TEXT NOT NULL,         -- raw chunk (returned to LLM)
    embedding_text TEXT,                 -- flattened text used for embedding
    embedding     vector(384),           -- pgvector column (dimension from config)
    metadata      JSONB DEFAULT '{}',
    created_at    TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for search performance
CREATE INDEX idx_chunks_artifact    ON artifact_chunks(artifact_id);
CREATE INDEX idx_chunks_artifact_ix ON artifact_chunks(artifact_id, chunk_index);

-- pgvector index for approximate nearest neighbor search
-- IVFFlat: good for <1M vectors, fast to build
CREATE INDEX idx_chunks_embedding ON artifact_chunks
    USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);
-- For >1M vectors, switch to HNSW:
-- CREATE INDEX idx_chunks_embedding ON artifact_chunks
--     USING hnsw (embedding vector_cosine_ops)
--     WITH (m = 16, ef_construction = 64);

-- Full-text search on chunk content
ALTER TABLE artifact_chunks ADD COLUMN content_tsv tsvector
    GENERATED ALWAYS AS (to_tsvector('english', content)) STORED;
CREATE INDEX idx_chunks_fts ON artifact_chunks USING GIN(content_tsv);

-- Index status on parent artifact
ALTER TABLE artifacts ADD COLUMN index_status TEXT DEFAULT 'pending';
-- Values: 'pending', 'indexing', 'ready', 'failed', 'skipped'
ALTER TABLE artifacts ADD COLUMN chunk_count INTEGER DEFAULT 0;
```

**CASCADE delete:** When an artifact is deleted (TTL expiry, invalidation,
session cleanup), all its chunks are automatically deleted. No orphaned chunks.

#### 12.5.2 SQLite Schema (with FTS5)

```sql
-- Chunks table
CREATE TABLE IF NOT EXISTS artifact_chunks (
    id            TEXT PRIMARY KEY,
    artifact_id   TEXT NOT NULL REFERENCES artifacts(id) ON DELETE CASCADE,
    chunk_index   INTEGER NOT NULL,
    content       TEXT NOT NULL,
    embedding_text TEXT,
    embedding     BLOB,                  -- serialized float array (no pgvector)
    metadata      TEXT DEFAULT '{}',     -- JSON string
    created_at    TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_chunks_artifact
    ON artifact_chunks(artifact_id);
CREATE INDEX IF NOT EXISTS idx_chunks_artifact_ix
    ON artifact_chunks(artifact_id, chunk_index);

-- FTS5 for full-text search on chunks
CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
    id,
    content,
    content='artifact_chunks',
    content_rowid='rowid'
);

-- Triggers to keep FTS synchronized
CREATE TRIGGER IF NOT EXISTS chunks_ai AFTER INSERT ON artifact_chunks BEGIN
    INSERT INTO chunks_fts(rowid, id, content)
    VALUES (new.rowid, new.id, new.content);
END;

CREATE TRIGGER IF NOT EXISTS chunks_ad AFTER DELETE ON artifact_chunks BEGIN
    INSERT INTO chunks_fts(chunks_fts, rowid, id, content)
    VALUES ('delete', old.rowid, old.id, old.content);
END;

CREATE TRIGGER IF NOT EXISTS chunks_au AFTER UPDATE ON artifact_chunks BEGIN
    INSERT INTO chunks_fts(chunks_fts, rowid, id, content)
    VALUES ('delete', old.rowid, old.id, old.content);
    INSERT INTO chunks_fts(rowid, id, content)
    VALUES (new.rowid, new.id, new.content);
END;
```

**SQLite vector search:** SQLite has no native vector type. Two options:

| Option | Approach | Trade-off |
|--------|----------|-----------|
| **sqlite-vec** | SQLite extension, stores vectors as BLOB, provides `vec_distance_cosine()` | Requires loading an extension; fast, lightweight |
| **In-process FAISS/hnswlib** | Vectors stored in BLOB column, loaded into an in-memory index at query time | No extension needed; higher memory usage, cold-start cost |

Recommended: **sqlite-vec** for production SQLite deployments, **in-process
brute-force cosine** for development/testing with small datasets (<10K chunks).

#### 12.5.3 In-Memory Backend (testing)

For `MemoryBackend`, chunks are stored in a `dict[str, list[ChunkRecord]]`
keyed by `artifact_id`. Vector search uses brute-force cosine similarity
over Python lists. This is intentionally simple — it's for unit tests and
development only.

---

### 12.6 Hybrid Search Engine

The search engine combines full-text search (keyword matching) and semantic
search (vector similarity) using Reciprocal Rank Fusion (RRF) to produce a
single ranked result set.

#### 12.6.1 Why Hybrid?

Neither FTS nor semantic search alone is sufficient:

| Query | FTS result | Semantic result | Best approach |
|-------|-----------|----------------|---------------|
| `"Enterprise"` | Exact match on keyword | May match "business", "corporate" too | FTS wins (exact term) |
| `"big customers"` | Misses — word "big" not in data | Matches "Enterprise", "whales" | Semantic wins |
| `"Enterprise customers in APAC"` | Partial match on "Enterprise" | Captures intent of compound query | Hybrid wins |

FTS is precise but brittle (exact keywords only). Semantic search captures
meaning but can be noisy. Combining them gives the best of both.

#### 12.6.2 Search Flow

```python
class HybridSearchEngine:

    def search(
        self,
        artifact_id: str,
        query: str,
        limit: int = 10,
        fts_weight: float = 0.4,
        semantic_weight: float = 0.6,
        metadata_filter: dict | None = None,
    ) -> list[ChunkResult]:

        # 1. Check if artifact is indexed
        status = self._backend.get_index_status(artifact_id)

        if status in ("ready",):
            # Full hybrid search
            fts_results = self._fts_search(artifact_id, query, limit=limit * 3)
            vec_results = self._vector_search(artifact_id, query, limit=limit * 3)
            merged = self._rrf_merge(fts_results, vec_results, fts_weight, semantic_weight)
        else:
            # Graceful degradation: FTS only
            merged = self._fts_search(artifact_id, query, limit=limit * 3)

        # 2. Apply metadata filters
        if metadata_filter:
            merged = [r for r in merged if self._matches_filter(r, metadata_filter)]

        # 3. Return top-K
        return merged[:limit]
```

#### 12.6.3 Reciprocal Rank Fusion (RRF)

RRF is a simple, parameter-light algorithm for combining ranked lists. It
outperforms linear score combination because it's rank-based (insensitive to
the different score scales of FTS vs. cosine similarity).

```
Formula:  RRF_score(chunk) = Σ  weight_i / (k + rank_i(chunk))

Where:
  k = 60  (smoothing constant — standard value from Cormack et al. 2009)
  rank_i  = rank of chunk in result set i (1-indexed; ∞ if absent)
  weight_i = relative weight of result set i
```

**Example:**

| Chunk | FTS rank | Semantic rank | RRF score (k=60, w=[0.4, 0.6]) |
|-------|---------|--------------|-------------------------------|
| chunk_42 | 1 | 3 | 0.4/(60+1) + 0.6/(60+3) = 0.00656 + 0.00952 = **0.01608** |
| chunk_17 | 3 | 1 | 0.4/(60+3) + 0.6/(60+1) = 0.00635 + 0.00984 = **0.01619** |
| chunk_99 | 2 | ∞ | 0.4/(60+2) + 0 = **0.00645** |
| chunk_55 | ∞ | 2 | 0 + 0.6/(60+2) = **0.00968** |

Result ordering: chunk_17, chunk_42, chunk_55, chunk_99

Chunks that appear in **both** result sets get boosted. Chunks in only one
set are still included but ranked lower.

#### 12.6.4 PostgreSQL Hybrid Query

A single SQL query performs both FTS and vector search, then merges:

```sql
WITH fts_matches AS (
    SELECT id, chunk_index, content, embedding_text, metadata,
           ts_rank(content_tsv, plainto_tsquery('english', $2)) AS fts_score,
           ROW_NUMBER() OVER (ORDER BY ts_rank(content_tsv,
               plainto_tsquery('english', $2)) DESC) AS fts_rank
    FROM artifact_chunks
    WHERE artifact_id = $1
      AND content_tsv @@ plainto_tsquery('english', $2)
),
vec_matches AS (
    SELECT id, chunk_index, content, embedding_text, metadata,
           1 - (embedding <=> $3::vector) AS vec_score,
           ROW_NUMBER() OVER (ORDER BY embedding <=> $3::vector) AS vec_rank
    FROM artifact_chunks
    WHERE artifact_id = $1
    ORDER BY embedding <=> $3::vector
    LIMIT $5
),
merged AS (
    SELECT
        COALESCE(f.id, v.id) AS id,
        COALESCE(f.chunk_index, v.chunk_index) AS chunk_index,
        COALESCE(f.content, v.content) AS content,
        COALESCE(f.metadata, v.metadata) AS metadata,
        -- RRF scoring
        COALESCE($6::float / (60 + f.fts_rank), 0) +
        COALESCE($7::float / (60 + v.vec_rank), 0) AS rrf_score
    FROM fts_matches f
    FULL OUTER JOIN vec_matches v ON f.id = v.id
)
SELECT id, chunk_index, content, metadata, rrf_score
FROM merged
ORDER BY rrf_score DESC
LIMIT $4;

-- Parameters:
-- $1: artifact_id (UUID)
-- $2: query text (for FTS)
-- $3: query embedding vector (for vector search)
-- $4: limit
-- $5: vector candidate limit (limit × 3)
-- $6: fts_weight (default 0.4)
-- $7: semantic_weight (default 0.6)
```

**Performance note:** The `<=>` operator uses the IVFFlat or HNSW index for
approximate nearest neighbor search. With 2,847 chunks, this is sub-millisecond.
The FTS GIN index handles keyword matching. The `FULL OUTER JOIN` + RRF scoring
happens on a small candidate set (limit × 3 from each side).

#### 12.6.5 SQLite Hybrid Query

SQLite requires two separate queries (FTS5 and brute-force vector), merged
in Python:

```python
# FTS query
fts_results = conn.execute("""
    SELECT c.id, c.chunk_index, c.content, c.metadata, c.embedding
    FROM artifact_chunks c
    JOIN chunks_fts fts ON c.id = fts.id
    WHERE c.artifact_id = ?
      AND chunks_fts MATCH ?
    ORDER BY rank
    LIMIT ?
""", (artifact_id, query_text, limit * 3)).fetchall()

# Vector query (brute-force or sqlite-vec)
# Option A: sqlite-vec extension
vec_results = conn.execute("""
    SELECT id, chunk_index, content, metadata,
           vec_distance_cosine(embedding, ?) AS distance
    FROM artifact_chunks
    WHERE artifact_id = ?
    ORDER BY distance ASC
    LIMIT ?
""", (query_embedding_blob, artifact_id, limit * 3)).fetchall()

# Option B: brute-force in Python (no extension required)
all_chunks = conn.execute(
    "SELECT id, chunk_index, content, embedding FROM artifact_chunks WHERE artifact_id = ?",
    (artifact_id,)
).fetchall()
vec_results = cosine_rank(all_chunks, query_embedding, limit * 3)

# Merge via RRF in Python
merged = rrf_merge(fts_results, vec_results, fts_weight=0.4, semantic_weight=0.6)
```

---

### 12.7 LLM-Facing Tools for Search

#### 12.7.1 stash_search Tool

New advisory tool that exposes hybrid search to the LLM:

```python
class SearchInput(BaseModel):
    query: str = Field(..., description="Natural language search query")
    reference: str = Field(
        ...,
        description="taskstash:// reference to search within"
    )
    limit: int = Field(default=10, description="Maximum chunks to return")

class StashSearchTool(BaseTool):
    name = "stash_search"
    description = (
        "Search within a stored artifact for specific content. "
        "Returns the most relevant chunks matching your query. "
        "Use this instead of stash_fetch when you need specific "
        "rows or sections, not the entire dataset."
    )
    args_schema = SearchInput
```

**Example interaction:**

```
LLM receives summary:
  "[JSON Array: 2,847 items] Columns: id, name, plan, status, created_at.
   Reference: taskstash://auto/a1b2c3d4"

User: "How many Enterprise customers are in APAC?"

LLM calls: stash_search(
    query="Enterprise plan APAC",
    reference="taskstash://auto/a1b2c3d4",
    limit=20
)

Returns (~800 tokens instead of ~35,500):
  "Found 17 matching chunks (of 2,847 total):
   1. {"id": 42, "name": "Alice Chen", "plan": "Enterprise", "region": "APAC", ...}
   2. {"id": 156, "name": "Tanaka Corp", "plan": "Enterprise", "region": "APAC", ...}
   ...
   17. {"id": 2801, "name": "Singh Ltd", "plan": "Enterprise", "region": "APAC", ...}"

LLM: "There are 17 Enterprise customers in the APAC region."
```

The LLM answered the question using **800 tokens** instead of fetching all
35,500. That's a 97.7% reduction on top of the initial summary savings.

#### 12.7.2 stash_search vs. stash_fetch Decision

The summary message should guide the LLM on when to use each tool:

```
[JSON Array: 2,847 items, 142,350 chars]
Columns: id, name, plan, status, created_at, region
Sample (3 of 2,847 items):
  {"id": 1, "name": "Alice Chen", "plan": "Enterprise", ...}
  {"id": 2, "name": "Bob Park", "plan": "Starter", ...}
  {"id": 3, "name": "Carlos Ruiz", "plan": "Pro", ...}
Reference: taskstash://auto/a1b2c3d4

  To find specific items: stash_search(query="...", reference="taskstash://auto/a1b2c3d4")
  To retrieve all items:  stash_fetch(reference="taskstash://auto/a1b2c3d4")
```

---

### 12.8 Configuration

```yaml
# .taskstash.yaml

embeddings:
  provider: sentence-transformers       # or: openai, ollama, nim, none
  model: all-MiniLM-L6-v2              # default for sentence-transformers
  # api_key: ...                        # for openai/nim (or use env var)
  # base_url: ...                       # for ollama/nim

chunking:
  json_strategy: per_row               # per_row | fixed_size
  sql_strategy: per_row                # per_row | fixed_size
  text_strategy: recursive             # recursive | paragraph | sentence
  text_overlap_pct: 0.12               # 12% overlap for text chunks
  max_chunk_size: auto                 # "auto" = derived from embedding model

indexing:
  enabled: true                        # false = skip embedding, FTS only
  background_workers: 2                # ThreadPoolExecutor max_workers
  batch_size: 128                      # chunks per embed_batch() call
  retry_attempts: 3                    # retries on transient failures
  retry_backoff: 2.0                   # exponential backoff multiplier

search:
  default_limit: 10                    # chunks returned per search
  fts_weight: 0.4                      # weight for FTS results in RRF
  semantic_weight: 0.6                 # weight for vector results in RRF
  rrf_k: 60                            # RRF smoothing constant
```

**No-config default:** When `embeddings.provider` is `"none"` (the default),
the system still chunks content for FTS-based search. Semantic search is
simply unavailable. This ensures the chunking + search pipeline adds value
even without embedding infrastructure.

---

### 12.9 Data Flow Summary

```
  ┌─────────────────────────────────────────────────────────────────────┐
  │                                                                     │
  │  STORE: Tool output intercepted by middleware                       │
  │                                                                     │
  │    142,350 chars ──┬──► artifacts table (1 row, full content)       │
  │                    │    index_status = "pending"                     │
  │                    │                                                 │
  │                    └──► ChunkIndexer.submit() ──► background thread  │
  │                              │                                      │
  │                              ├──► chunk (2,847 rows)                │
  │                              ├──► flatten ("Name: Alice, Plan:...")  │
  │                              ├──► embed_batch (384-dim vectors)      │
  │                              ├──► store_chunks (2,847 rows + vecs)  │
  │                              └──► index_status = "ready"            │
  │                                                                     │
  │  SEARCH: LLM calls stash_search("Enterprise APAC", ref)            │
  │                                                                     │
  │    ┌─► FTS: chunks_fts MATCH 'Enterprise APAC' → ranked set A      │
  │    ├─► VEC: embedding <=> query_vec → ranked set B                  │
  │    ├─► RRF merge(A, B) → combined ranking                          │
  │    └─► Return top 10 chunks (~800 tokens)                           │
  │                                                                     │
  │  FETCH: LLM calls stash_fetch(ref) — unchanged, full artifact      │
  │                                                                     │
  │  DELETE: Artifact deleted → CASCADE deletes all chunks              │
  │                                                                     │
  └─────────────────────────────────────────────────────────────────────┘
```

---

### 12.1 Pre-Fetch Mode

**Files:** `core/config.py` (PrefetchConfig), `core/stash.py` (prefetch method), `langchain/content_aware.py` (_try_prefetch)

Pre-fetch eliminates the second round-trip (`stash_search`) by including relevant chunks inline with the interception summary.

**Flow (when enabled):**

```
Tool output → intercept → store → submit for indexing → wait (best-effort)
                                                        → search using user query
                                                        → append top chunks to summary
```

**Configuration:**

```python
PrefetchConfig(
    enabled=False,    # opt-in, off by default
    limit=5,          # max chunks to include
    timeout_ms=2000,  # max wait for indexing before falling back
)
```

**Query source** is integration-specific:
- **LangChain middleware:** `middleware.user_query = "..."` (set via callback or manually)
- **MCP server:** `taskstash_store(content, namespace, query="...")`
- **LangChain toolkit:** `StashStoreTool.invoke({"content": ..., "query": "..."})`

**Graceful degradation** — pre-fetch returns no chunks (falls back to summary-only) when:
- `enabled=False` or no `user_query` set
- Indexing doesn't complete within `timeout_ms`
- No chunks match the query
- No indexer/search engine configured

The `stash_search` hint remains in the output even when pre-fetch succeeds, so the LLM can still do follow-up searches if the pre-fetched chunks aren't sufficient.

---

## 13. PII Detection & Content Safety

**File:** `src/yonk_taskstash/pii/`

Two providers for PII detection:

### Regex Provider (Built-in)

Basic pattern matching for common PII types:
- Email addresses
- Phone numbers (US format)
- Social Security Numbers
- Credit card numbers
- IP addresses

### Presidio Provider (Optional)

Microsoft Presidio integration for production-grade NER-based PII detection:
- Requires `spacy` + language model
- Higher accuracy, lower false positive rate
- Supports custom recognizers
- Setup: `yonk-taskstash-setup-presidio` CLI command

### PII Actions

| Action | Behavior |
|--------|----------|
| `redact` | Replace PII with `[REDACTED]` |
| `mask` | Replace with `****` partial mask |
| `block` | Raise error, prevent storage |
| `warn` | Log warning, store unchanged |
| `allow` | No action, store as-is |

### Integration Points

PII detection can be triggered at two levels:
1. **StashStore component / store operation** -- detect/redact before storage
2. **StashInvisible component** -- PII presence as an interception trigger (content with PII gets intercepted even if small)

---

## 14. Cache Invalidation & Lifecycle Management

### Lifecycle Strategies

| Strategy | Stored By | Cleaned Up By | Use Case |
|----------|-----------|---------------|----------|
| `SESSION` | `Session.store()` (default) | `session.close()` / context exit | Ephemeral conversation data |
| `TTL` | Explicit `lifecycle=TTL` | Lazy check on `get()` / `query()` | Temporary cache entries |
| `MANUAL` | `TaskStash.store()` (default) | Explicit `delete()` or `invalidate_*()` | Long-lived reference data |

### Lazy Cleanup

The system uses lazy cleanup -- expired artifacts remain in storage until accessed:

```python
def get(self, reference):
    artifact = self._session.get(reference)
    if artifact and artifact.is_expired:
        self._session.delete(reference)  # Lazy cleanup
        return None
    return artifact
```

**Trade-off:** Simple (no background threads), but disk space isn't reclaimed until expired artifacts are accessed. For production, consider adding a periodic `cleanup_expired()` call via cron or application timer.

### Bulk Invalidation

```python
stash.invalidate_namespace("api_results")        # Delete all in namespace
stash.invalidate_by_metadata({"tool": "search"})  # Delete by metadata match
stash.invalidate_older_than(3600)                  # Delete older than 1 hour
stash.refresh_ttl(reference, ttl_seconds=7200)     # Extend TTL

middleware.invalidate_all()         # Delete all content this middleware stored
middleware.invalidate_namespace()   # Delete entire middleware namespace
```

---

## 15. Benchmark & Validation Framework

The project includes an extensive benchmarking suite that validates the core thesis. Engineers should run these to understand performance characteristics before production deployment.

### Running Benchmarks

```bash
# Full comprehensive benchmark (all dimensions)
yonk-taskstash-benchmark --comprehensive

# Full comprehensive with HTML report
yonk-taskstash-benchmark --comprehensive --output report.html

# Deep workload analysis (24 patterns, sweeps)
yonk-taskstash-benchmark --deep

# Deep with HTML report
yonk-taskstash-benchmark --deep --output report.html
```

### What the Benchmarks Measure

**Comprehensive benchmark** covers 5 dimensions:
1. **Overhead analysis** -- Breakeven point by content type (text ~10KB, JSON ~9.9KB, SQL ~5KB)
2. **RAG integration** -- Whether TaskStash helps or hurts alongside RAG (75% of configs benefit)
3. **Workload patterns** -- 16 realistic agent scenarios with honest fetch-probability accounting
4. **Cross-session analysis** -- Token savings over 1-20 sessions (plateaus at ~70%)
5. **Quality assessment** -- Whether summaries preserve enough info for agent tasks

**Deep benchmark** adds:
- 25 workload patterns (6 core + 9 architectural + 10 data access)
- Data size sweeps (50 to 5,000 rows)
- Fetch probability sweeps (0% to 100%)
- Cross-session sweeps (1 to 20 sessions)
- Search pipeline benchmark (chunking + indexing + FTS/hybrid search)
- Quality comparison: 32 scenarios (JSON, SQL, text) across 3 modes (no-taskstash / FTS / hybrid)

### Key Findings

| Metric | Value |
|--------|-------|
| Scenarios where TaskStash helps | 84% (21 of 25) |
| Scenarios where TaskStash hurts | 16% (4 of 25) |
| Average token savings (honest) | 76.7% |
| Quality: FTS search correct | 28/32 scenarios |
| Quality: Hybrid search correct | 23/32 scenarios |
| Worst anti-pattern | 100% fetch probability (always needs full data) |
| Best pattern | Metadata-only queries (99.9% savings) |
| Cross-session plateau | ~70% savings after 3-5 sessions |

**Text document scenarios** (7 of 32 quality scenarios) test real-world content: API documentation, CRM sales notes, meeting transcripts, incident post-mortems, and product requirements docs. Hybrid search outperforms FTS on semantic text queries (e.g., `doc_topic_overview` 3/3 vs FTS 2/3, `requirements_overview` 3/3 vs FTS 1/3).

**When NOT to use TaskStash:**
- Aggregation queries where complete results are required
- Data transformation tasks (agent processes every row)
- Any workflow with 100% fetch probability

---

## 16. Known Limitations & POC Debt

### Security

| Issue | Severity | Description |
|-------|----------|-------------|
| No reference authentication | High | Anyone with a `taskstash://` URI and backend access can retrieve content |
| Session scoping is logical, not cryptographic | High | Application-level enforcement, not database RLS |
| PII regex is basic | Medium | Simple patterns; production should use Presidio or custom NER |
| No rate limiting on MCP server | Medium | Unbounded tool calls possible |

### Scalability

| Issue | Severity | Description |
|-------|----------|-------------|
| MemoryBackend is not thread-safe | High | No locking on the internal dict |
| No connection pool tuning for PostgreSQL | Medium | Hardcoded min=2, max=10 |
| SQLite fresh connection per operation | Medium | Works for WAL mode but inefficient |
| No content size limits | Medium | Can store arbitrarily large content |
| Lazy cleanup only | Low | No background reaper for expired TTL artifacts |

### Code Quality

| Issue | Severity | Description |
|-------|----------|-------------|
| Custom `BaseTool` instead of LangChain's | Medium | Works but breaks LangChain's type system and tooling |
| Langflow parser compatibility | Low | Components use try/except stubs; validate with latest Langflow releases |
| MCP server global singleton | Medium | All sessions share one stash instance |
| `TaskStash.production()` is a placeholder | Low | Returns MemoryBackend |
| Inconsistent async/sync in PostgresBackend | Low | Async core with sync wrappers |

### Testing

| Issue | Severity | Description |
|-------|----------|-------------|
| No integration tests against real PostgreSQL | High | Only memory and SQLite tested in CI |
| No concurrency tests | High | Thread-safety untested |
| No latency benchmarks in CI | Medium | NFR-1 (< 50ms overhead) not validated continuously |
| Langflow tests use stubs only | Medium | Not tested against actual Langflow runtime |

---

## 17. Ideas for Fixing or Overcoming Known Limitations

This section provides concrete implementation ideas for each limitation identified above. These are not prescriptive -- they are starting points for the production engineering team to evaluate, spike, and refine.

### Security Fixes

#### S1. No Reference Authentication

**Problem:** `taskstash://namespace/uuid` references are plain URIs. Anyone with the string and backend access can retrieve content.

**Approach A: HMAC-Signed References (Recommended)**

Embed an HMAC signature in the reference that binds it to a session, user, and expiration:

```
taskstash://namespace/uuid?sig=HMAC_SHA256&exp=1706745600&sid=sess_abc123
```

Implementation:
- On `store()`, compute `sig = HMAC-SHA256(secret_key, f"{artifact_id}:{session_id}:{expires_at}")`
- On `get()`, validate the signature before returning content
- Signature verification is O(1) and adds negligible latency
- The secret key is configured per-deployment (environment variable or config)
- References become tamper-proof and time-bounded

**Approach B: Opaque Tokens**

Replace the predictable `taskstash://namespace/uuid` format with a cryptographically random token:

```
taskstash://tok_a8f3e2b1c4d5e6f7a8b9c0d1e2f3a4b5
```

- Store a mapping from token to artifact ID in the backend
- Tokens are unguessable (128-bit random)
- Trade-off: requires an extra lookup table and breaks the human-readable namespace/id convention

**Approach C: Session-Scoped Tokens (Simplest)**

Keep the current format but enforce that references are only valid within the session that created them:

- `get()` already checks `session_id` -- make this check non-bypassable
- Middleware-generated references inherit the middleware's session
- Cross-session sharing requires explicit `share(reference, target_session_id)` call

**Recommendation:** Start with Approach A (HMAC). It's the best balance of security, performance, and backward compatibility. The reference format stays human-readable for debugging.

---

#### S2. Session Scoping Is Logical, Not Cryptographic

**Problem:** Session isolation is enforced by `if artifact.session_id != self._session_id: return None` in Python code. A malicious or buggy caller can bypass this.

**Approach A: PostgreSQL Row-Level Security (Production)**

```sql
-- Enable RLS
ALTER TABLE artifacts ENABLE ROW LEVEL SECURITY;

-- Policy: users can only see their own session's artifacts
CREATE POLICY session_isolation ON artifacts
    USING (session_id = current_setting('app.session_id'));

-- Set session context per connection
SET app.session_id = 'sess_abc123';
```

This makes isolation a database-level guarantee. Even if the application code has a bug, PostgreSQL enforces the boundary.

**Approach B: Separate Schemas per Tenant (Strict Isolation)**

For multi-tenant deployments with strict compliance requirements:

- Each tenant gets their own PostgreSQL schema
- Connection strings are tenant-specific
- No possibility of cross-tenant data access at any layer

**Approach C: Encryption at Rest per Session**

Encrypt artifact content with a session-derived key:

- `content = AES-GCM(session_key, plaintext)`
- Even if someone bypasses session checks, they get ciphertext
- Session keys derived from a master key + session ID via HKDF
- Trade-off: adds encryption overhead and complicates search/FTS

**Recommendation:** Approach A (RLS) for most deployments. Add Approach C for high-sensitivity data (medical, financial).

---

#### S3. PII Regex Is Basic

**Problem:** Simple patterns catch `XXX-XX-XXXX` but miss context-dependent PII (names, addresses, medical terms).

**Approach A: Presidio with Custom Recognizers (Recommended)**

The Presidio integration already exists. Harden it:

1. Add custom recognizers for domain-specific PII (employee IDs, internal account numbers)
2. Train or fine-tune the spaCy NER model on your data
3. Add a PII benchmark suite with known-good test cases and regression detection
4. Tune `confidence_threshold` per entity type (emails need 0.7, SSNs need 0.95)

**Approach B: Layered Detection**

Run regex as a fast first pass, then Presidio as a slower but more accurate second pass:

```python
# Fast: regex catches obvious patterns (< 1ms)
regex_matches = regex_detector.scan(content)

# Slow: Presidio catches context-dependent PII (10-50ms)
if needs_deep_scan(content):
    presidio_matches = presidio_detector.analyze(content)

# Union of both
all_matches = merge_matches(regex_matches, presidio_matches)
```

**Approach C: External PII Service**

For enterprises with existing DLP (Data Loss Prevention) infrastructure:

- Route content through the existing DLP API before storage
- TaskStash becomes a consumer of the DLP service, not a reimplementation
- Add a `PII_SERVICE_URL` config option for HTTP-based detection

**Recommendation:** Approach B (layered) for performance-sensitive paths, with Approach C as an option for enterprises with existing DLP.

---

#### S4. No Rate Limiting on MCP Server

**Problem:** Unbounded tool calls can exhaust storage or compute resources.

**Approach A: Token Bucket per Session**

```python
class RateLimiter:
    def __init__(self, max_calls_per_minute: int = 60, max_store_bytes_per_hour: int = 100_000_000):
        self._call_counts: dict[str, deque] = defaultdict(deque)
        self._store_bytes: dict[str, deque] = defaultdict(deque)
```

- Track calls per session per minute
- Track bytes stored per session per hour
- Return `429 Too Many Requests` equivalent in MCP error response

**Approach B: Global Circuit Breaker**

If total storage exceeds a threshold, temporarily disable `taskstash_store`:

```python
if backend.total_size_bytes() > MAX_STORAGE_BYTES:
    return {"error": "Storage quota exceeded. Clean up old artifacts."}
```

**Recommendation:** Implement both. Token bucket for per-session fairness, circuit breaker for global protection.

---

### Scalability Fixes

#### SC1. MemoryBackend Is Not Thread-Safe

**Problem:** Multiple threads writing to the same `dict` without locks causes data corruption.

**Approach A: Document as Test-Only (Simplest)**

Add a clear warning:

```python
class MemoryBackend(StorageBackend):
    """In-memory storage for TESTING ONLY. Not thread-safe."""
```

Remove it from the `production()` factory path. Production must use SQLite or PostgreSQL.

**Approach B: Add threading.Lock**

```python
class MemoryBackend(StorageBackend):
    def __init__(self):
        self._artifacts: dict[str, Artifact] = {}
        self._lock = threading.Lock()

    def store(self, artifact: Artifact) -> None:
        with self._lock:
            self._artifacts[str(artifact.id)] = artifact
```

Simple but limits throughput to one operation at a time.

**Approach C: Use concurrent.futures or asyncio-native dict**

For async contexts, use `asyncio.Lock` or a `dict` guarded by an async lock.

**Recommendation:** Approach A. The MemoryBackend exists for tests. Don't over-engineer it -- just make sure production code paths can't accidentally use it.

---

#### SC2. No Connection Pool Tuning for PostgreSQL

**Problem:** Hardcoded `min_pool_size=2, max_pool_size=10` doesn't fit all deployments.

**Fix:** Expose pool settings in configuration:

```yaml
storage:
  backend: postgres
  postgres:
    host: localhost
    port: 5432
    database: taskstash
    pool:
      min_size: 5
      max_size: 50
      max_idle_time: 300
      command_timeout: 30
```

Map these to `asyncpg.create_pool()` parameters. Add health check queries to detect stale connections.

---

#### SC3. SQLite Fresh Connection per Operation

**Problem:** Creating and closing a connection for every `store()`/`get()` call is inefficient.

**Approach A: Connection Pool (e.g., `sqlite3` with check_same_thread=False)**

```python
class SQLiteBackend(StorageBackend):
    def __init__(self, path: str, pool_size: int = 5):
        self._pool = queue.Queue(maxsize=pool_size)
        for _ in range(pool_size):
            conn = sqlite3.connect(path, check_same_thread=False)
            conn.execute("PRAGMA journal_mode=WAL")
            self._pool.put(conn)
```

**Approach B: Single Persistent Connection with WAL**

SQLite in WAL mode supports concurrent readers with a single writer. Use one persistent connection with a write lock:

```python
class SQLiteBackend(StorageBackend):
    def __init__(self, path: str):
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._write_lock = threading.Lock()
```

**Recommendation:** Approach B for simplicity. WAL mode handles the common case (many reads, few writes) well. Only move to a connection pool if write contention becomes measurable.

---

#### SC4. No Content Size Limits

**Problem:** Storing a 1GB artifact would exhaust memory and storage.

**Fix:** Add configurable limits at the `TaskStash.store()` level:

```python
class TaskStash:
    MAX_CONTENT_SIZE = 10 * 1024 * 1024  # 10MB default

    def store(self, content: str, ...):
        if len(content.encode('utf-8')) > self.MAX_CONTENT_SIZE:
            raise ContentTooLargeError(
                f"Content size {len(content)} exceeds limit {self.MAX_CONTENT_SIZE}"
            )
```

Make the limit configurable in `.taskstash.yaml`:

```yaml
limits:
  max_content_size: 10485760     # 10MB
  max_artifacts_per_session: 1000
  max_total_storage: 1073741824  # 1GB
```

For content that genuinely needs to be larger, add a chunked storage option that splits content into linked artifacts.

---

#### SC5. Lazy Cleanup Only

**Problem:** Expired TTL artifacts accumulate in storage until someone reads them.

**Approach A: Background Asyncio Task**

```python
class TaskStash:
    async def _reaper_loop(self, interval_seconds: int = 300):
        while True:
            await asyncio.sleep(interval_seconds)
            count = self._backend.cleanup_expired()
            if count > 0:
                logger.info(f"Reaped {count} expired artifacts")
```

Start the reaper when the TaskStash instance is created with `reaper_enabled=True`.

**Approach B: External Cron/Scheduler**

For deployments that don't run a long-lived Python process:

```bash
# crontab entry: clean up every 5 minutes
*/5 * * * * python -c "from yonk_taskstash import TaskStash; TaskStash(backend=...).cleanup_expired()"
```

**Approach C: Piggyback on Store Operations**

Run cleanup probabilistically on store operations:

```python
def store(self, content, ...):
    # 1% chance of cleanup on each store
    if random.random() < 0.01:
        self._backend.cleanup_expired()
    # ... normal store logic
```

This is how Redis handles TTL expiration and works well at scale.

**Recommendation:** Approach A for long-lived services, Approach C as a fallback for all deployments.

---

### Code Quality Fixes

#### CQ1. Custom BaseTool Instead of LangChain's

**Problem:** The POC defines its own `BaseTool` class instead of extending `langchain_core.tools.BaseTool`. This breaks LangChain's type system, agent introspection, and any tooling that expects standard `BaseTool` instances.

**Fix:** Rewrite tools to extend `langchain_core.tools.BaseTool`:

```python
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field

class StoreInput(BaseModel):
    content: str = Field(description="Content to store")
    namespace: str = Field(description="Namespace for organizing")
    metadata: dict = Field(default={}, description="Optional metadata")

class StashStoreTool(BaseTool):
    name: str = "stash_store"
    description: str = "Store content in TaskStash off-prompt memory."
    args_schema: type[BaseModel] = StoreInput

    stash: TaskStash  # Injected dependency

    def _run(self, content: str, namespace: str, metadata: dict = {}) -> str:
        ref = self.stash.store(content=content, namespace=namespace, metadata=metadata)
        return f"Stored. Reference: {ref}"

    async def _arun(self, **kwargs) -> str:
        return self._run(**kwargs)
```

This gives you: proper type introspection, compatibility with `create_tool_calling_agent()`, structured output parsing, and correct behavior with LangChain's tool execution framework.

**Effort estimate:** Medium. Each of the 7 tools needs to be rewritten, plus test updates.

---

#### CQ2. Langflow Component Parser Compatibility

**Status:** Resolved. The dual `components/` and `components_langflow/` hierarchy has been consolidated into a single `components/` directory. Components use try/except import stubs that work both with and without Langflow installed. Validate against new Langflow releases if the parser changes.

**Recommendation:** Approach A first (fix imports). If Langflow's parser is truly intractable, Approach B (automated generation) prevents the two hierarchies from drifting.

---

#### CQ3. MCP Server Global Singleton

**Problem:** All MCP sessions share one `TaskStash` instance. Session isolation doesn't exist at the MCP layer.

**Fix:** Create a session-aware stash factory:

```python
_sessions: dict[str, TaskStash] = {}

def get_stash_for_session(session_id: str) -> TaskStash:
    if session_id not in _sessions:
        config = load_config()
        backend = create_backend(config)
        _sessions[session_id] = TaskStash(backend=backend)
    return _sessions[session_id]
```

The MCP protocol can carry session context via:
- The `meta` field in MCP tool call requests
- A `session_id` parameter added to each tool schema
- Environment variables set by the MCP client

**For Claude Desktop:** Single user, so the global singleton is actually fine. Document this explicitly.

**For multi-user MCP servers (e.g., shared server):** Require session_id in every tool call and route to per-session stash instances.

---

#### CQ4. `TaskStash.production()` Is a Placeholder

**Problem:** The factory method meant for production use returns a `MemoryBackend`.

**Fix:** Implement it properly:

```python
@classmethod
def production(cls, config_path: str | None = None, **overrides) -> "TaskStash":
    config = load_config(config_path)
    # Apply any runtime overrides
    for key, value in overrides.items():
        setattr(config.storage, key, value)

    backend = create_backend_from_config(config)
    instance = cls(backend=backend)

    # Optionally start background reaper
    if config.storage.backend != "memory":
        instance._start_reaper(interval=config.get("reaper_interval", 300))

    return instance
```

This should read `.taskstash.yaml`, create the appropriate backend, configure embedding providers, and optionally start the TTL reaper.

---

#### CQ5. Inconsistent Async/Sync in PostgresBackend

**Problem:** The PostgresBackend is async internally (`asyncpg`) but wraps everything in sync methods using `asyncio.get_event_loop().run_until_complete()`.

**Approach A: Dual Interface (Recommended)**

Provide both sync and async methods:

```python
class PostgresBackend(StorageBackend):
    async def astore(self, artifact: Artifact) -> None:
        async with self._pool.acquire() as conn:
            await conn.execute(...)

    def store(self, artifact: Artifact) -> None:
        # Sync wrapper for non-async contexts
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # Inside an existing async context (e.g., LangChain async agent)
            raise RuntimeError("Use astore() in async contexts")
        loop.run_until_complete(self.astore(artifact))
```

**Approach B: Go Full Async**

Make `StorageBackend` abstract methods async and update all callers:

```python
class StorageBackend(ABC):
    @abstractmethod
    async def store(self, artifact: Artifact) -> None: ...
```

This is a bigger change but is cleaner and avoids the sync/async impedance mismatch.

**Recommendation:** Approach A for backward compatibility. Flag Approach B as a future major version change.

---

### Testing Fixes

#### T1. No Integration Tests Against Real PostgreSQL

**Problem:** PostgresBackend is tested only against MemoryBackend behavior assumptions.

**Fix:** Use `testcontainers` in CI:

```python
import pytest
from testcontainers.postgres import PostgresContainer

@pytest.fixture(scope="session")
def postgres_backend():
    with PostgresContainer("pgvector/pgvector:pg17") as pg:
        backend = PostgresBackend(connection_string=pg.get_connection_url())
        yield backend
```

Add a CI job that spins up PostgreSQL with pgvector in a Docker container and runs the full backend test suite against it. Mark these tests with `@pytest.mark.integration` so they can be skipped in fast local runs.

---

#### T2. No Concurrency Tests

**Problem:** Thread-safety and race conditions are untested.

**Fix:** Add concurrent test scenarios:

```python
import concurrent.futures

def test_concurrent_stores(backend):
    """Multiple threads storing simultaneously should not lose data."""
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = [
            executor.submit(backend.store, create_artifact(f"content-{i}"))
            for i in range(100)
        ]
        concurrent.futures.wait(futures)

    # All 100 artifacts should exist
    assert len(backend.list_by_session("default")) == 100

def test_concurrent_read_write(backend):
    """Reads during writes should not raise or return corrupted data."""
    # ... writer thread stores, reader threads query simultaneously
```

---

#### T3. No Latency Benchmarks in CI

**Problem:** NFR-1 (< 50ms overhead for < 100KB) is not continuously validated.

**Fix:** Use `pytest-benchmark`:

```python
def test_interception_latency(benchmark):
    middleware = ContentAwareMiddleware(threshold=5000)
    content = "A" * 50_000  # 50KB

    result = benchmark(middleware._maybe_intercept, content, "test_tool")

    # Assert p95 latency < 50ms
    assert benchmark.stats.stats.median < 0.050
```

Run in CI with `--benchmark-json=benchmarks.json` and track regressions across builds.

---

#### T4. Langflow Tests Use Stubs Only

**Problem:** Tests validate the component logic but not the actual Langflow runtime integration.

**Approach A: Docker-Based Integration Tests**

```python
@pytest.fixture(scope="session")
def langflow_server():
    """Start Langflow with TaskStash components mounted."""
    container = DockerContainer("langflowai/langflow:latest")
    container.with_volume_mapping(
        str(COMPONENTS_DIR), "/app/langflow/components/taskstash"
    )
    container.with_exposed_ports(7860)
    container.start()
    yield f"http://localhost:{container.get_exposed_port(7860)}"
    container.stop()

def test_store_component_in_langflow(langflow_server):
    """Test that StashStore component loads and executes in real Langflow."""
    # Use Langflow's API to create a flow, run it, and validate output
    response = requests.post(f"{langflow_server}/api/v1/run/...", json={...})
    assert response.status_code == 200
```

**Approach B: Component Serialization Tests**

Test that components serialize correctly for Langflow's component registry:

```python
def test_component_serialization():
    """Verify components have valid Langflow metadata."""
    from yonk_taskstash.langflow.components.stash_store import StashStore
    component = StashStore()
    assert component.display_name
    assert component.description
    assert len(component.inputs) > 0
    assert len(component.outputs) > 0
```

**Recommendation:** Start with Approach B (cheap, fast, catches most issues). Add Approach A as a nightly or weekly CI job.

---

### Summary: Priority Matrix

| Fix | Effort | Impact | Priority |
|-----|--------|--------|----------|
| S1. HMAC-signed references | Medium | High (security) | **P0** |
| S2. PostgreSQL RLS | Medium | High (security) | **P0** |
| S3. Layered PII detection | Medium | High (compliance) | **P0** |
| S4. Rate limiting | Low | Medium (availability) | **P1** |
| SC1. Document MemoryBackend as test-only | Low | Medium (clarity) | **P0** |
| SC2. Configurable PostgreSQL pool | Low | Medium (operations) | **P1** |
| SC3. SQLite persistent connection | Low | Low (performance) | **P2** |
| SC4. Content size limits | Low | Medium (stability) | **P0** |
| SC5. Background TTL reaper | Medium | Medium (operations) | **P1** |
| CQ1. LangChain native BaseTool | Medium | High (compatibility) | **P0** |
| CQ2. Langflow component consolidation | Medium | Medium (maintenance) | **P1** |
| CQ3. MCP session-aware stash | Medium | Medium (multi-user) | **P1** |
| CQ4. Implement production() factory | Low | Medium (usability) | **P0** |
| CQ5. Async/sync consistency | High | Low (correctness) | **P2** |
| T1. PostgreSQL integration tests | Medium | High (confidence) | **P0** |
| T2. Concurrency tests | Medium | High (reliability) | **P0** |
| T3. Latency benchmarks in CI | Low | Medium (regression) | **P1** |
| T4. Langflow runtime tests | High | Medium (integration) | **P2** |

---

## 18. Production Readiness Checklist

Use this as a tracking checklist when taking the POC to production:

### Phase 1: Harden Core (Must-Have)

- [ ] Add reference authentication (HMAC signature or session-scoped tokens)
- [ ] Enforce content size limits (configurable, default 10MB)
- [ ] Add concurrency controls to MemoryBackend (or document it as test-only)
- [ ] Replace `TaskStash.production()` placeholder with real implementation
- [ ] Add background TTL reaper (configurable interval)
- [ ] Structured error responses for all LLM-facing tools
- [ ] Integration tests against PostgreSQL in CI
- [ ] Concurrency tests (multiple sessions, concurrent reads/writes)
- [ ] Resolve all `TODO` / `FIXME` / `placeholder` comments

### Phase 2: Clean Up Adapters

- [ ] LangChain tools: extend `langchain_core.tools.BaseTool`
- [ ] Langflow components: consolidate to single hierarchy
- [ ] MCP server: session-aware stash (not global singleton)
- [ ] MCP server: add rate limiting
- [ ] Remove or document all stub/mock code paths

### Phase 3: Observability

- [ ] Prometheus metrics: interception rate, storage size, latency p50/p95/p99
- [ ] OpenTelemetry tracing: spans for store/fetch/query/intercept
- [ ] Structured logging with correlation IDs
- [ ] Audit trail for compliance (who stored what, who fetched what, when)

### Phase 4: Scale & Security

- [ ] PostgreSQL connection pool tuning (configurable min/max)
- [ ] Database migration strategy (Alembic)
- [ ] Content compression for storage
- [ ] Streaming fetch for large content
- [ ] Row-level security in PostgreSQL for multi-tenancy
- [ ] Security audit of PII detection coverage

---

## 19. Glossary

| Term | Definition |
|------|-----------|
| **Advisory Integration** | An integration where the LLM *chooses* whether to use TaskStash (MCP tools, LangChain toolkit). No guarantee of interception. |
| **Artifact** | The fundamental unit of storage: content + metadata + lifecycle information |
| **Content-Aware** | Middleware that detects JSON/SQL structures and generates schema-preserving summaries |
| **Fetch Probability** | The likelihood that an agent will need full content after seeing a summary. Determines whether TaskStash saves or wastes tokens for a given workload |
| **HMAC-Signed Reference** | A reference URI with a cryptographic signature that binds it to a session, user, and expiration time, preventing unauthorized access |
| **Interception** | The act of capturing tool output, storing it, and replacing it with a summary + reference |
| **Invisible Mode** | Automatic interception where the agent isn't explicitly aware of TaskStash -- it just sees summaries |
| **Lazy Cleanup** | Expired artifacts are deleted when accessed, not preemptively |
| **Lifecycle** | Strategy for artifact retention: SESSION (auto-clean on close), TTL (time-based), MANUAL (explicit delete) |
| **MCP** | Model Context Protocol -- Anthropic's standard for connecting tools to LLM clients |
| **Namespace** | A logical grouping for artifacts (e.g., "documents", "api_results", "cache") |
| **Off-Prompt** | Data that is stored outside the LLM's context window but accessible on-demand via tools |
| **Reference** | A URI in the format `taskstash://namespace/uuid` that uniquely identifies an artifact |
| **Row-Level Security (RLS)** | A PostgreSQL feature that enforces access control at the database row level, making session isolation a database guarantee rather than an application-level check |
| **Session** | A scoped context for artifact operations; provides logical isolation between users/conversations |
| **Structural Integration** | An integration where interception is *guaranteed* by architecture (LangChain middleware, Langflow components). The LLM cannot bypass it. |
| **Structured Bypass** | Allowing small structured data (JSON/SQL) through even when above the main threshold, because complete small datasets are more useful than their summaries |
| **TaskStash** | The main facade class; entry point for all storage operations |
| **Threshold** | The content size (in characters) above which middleware intercepts and stores content |
| **Toolkit** | A LangChain-compatible collection of TaskStash tools that agents can invoke |
| **TTL Reaper** | A background process that periodically cleans up expired artifacts, replacing the default lazy cleanup strategy |

---

*This document was generated from analysis of the codebase at commit `7e49124` on the `main` branch.*
