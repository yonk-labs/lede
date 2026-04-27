## TL;DR

Pre-public-flip secret scan: **CLEAN** for credentials. No API keys, private keys, or hardcoded secrets in tracked files or git history. Two non-credential info-leaks fixed this round (LAN IP defaults in `benchmarks/quality_eval_llm.py` + `extractive-performance.md`); `.gitignore` hardened to cover per-developer Claude Code config (`.claude/`).

## Verdict

**SAFE TO FLIP PUBLIC** for credential exposure. Findings below are info-disclosure (now fixed) plus advisory items.

## Methodology

- Mode A scan against the working tree + git history (`git log --all`).
- Pattern catalog: AWS / GitHub / OpenAI / Anthropic / Stripe / GCP / Slack / generic Bearer / private keys / connection strings.
- PII: SSN-like, credit-card-like, real emails.
- File-type sweep: `.env`, `.pem`, `.key`, `credentials*`, `*.p12`, `*.pfx`, `*.jks`, `*.tfstate`, `*.tfvars`.
- `.gitignore` audit + history scan for previously-committed-then-removed sensitive files.

## Findings

### CRITICAL / HIGH — credentials
**None.** No API keys, tokens, or private keys found in tracked files or git history.

### MEDIUM — info disclosure (fixed this round)

| ID | File | Issue | Fix |
|---|---|---|---|
| SS-1 | `benchmarks/quality_eval_llm.py` lines 13/17/48 | `BASE_URL` default was `http://192.168.1.193:8000/v1` — author's home-LAN vLLM IP baked into a public-facing default | Replaced with `http://localhost:8000/v1`; module docstring rewritten to describe the env-var override path generically |
| SS-2 | `extractive-performance.md` lines 5–6 | Original benchmark notes (Apr 19, pre-skimr) listed the source LLM as `http://192.168.1.193:8006` and the database as `192.168.1.206:5432, sales_demo_app` | Replaced with `(NIM, locally hosted)` and `Postgres (sales_demo_app, redacted)` |

### MEDIUM — repo hygiene (fixed this round)

| ID | Issue | Fix |
|---|---|---|
| SS-3 | `.claude/` directory is per-developer Claude Code config; can contain machine-local paths and personal allowlists. Was not gitignored, though no settings file had been tracked in this repo (`git ls-files .claude/` empty; `git log -- .claude/` empty). | Added `.claude/` to `.gitignore` with allowlist for shareable subdirs (`!.claude/agents/`, `!.claude/commands/`). Defensive — prevents future accidental commits. |

### LOW — advisory (no action recommended)

| ID | Item | Disposition |
|---|---|---|
| SS-4 | `matt@theyonk.com` appears in `skill-output/research-base/RB-{Identity,Community}.md` and `skill-output/aat/AAT-Scout-Findings.md` as the maintainer's contact email | Intentional — this is the public-facing maintainer email and is also visible via `git log` author lines. Treat as published, not leaked. |

## .gitignore audit

| Pattern | Coverage |
|---|---|
| `.env` / `.env.*` (with `!.env.example` allowlist) | ✓ |
| `.openai` / `.openai.*` (and `.anthropic` variants) | ✓ |
| `*.pem` / `*.key` / `*.p12` / `*.pfx` / `*.jks` | ✓ |
| `id_rsa` / `id_ed25519` | ✓ |
| `credentials*.json` / `secrets*.json` | ✓ |
| `*.tfstate*` / `*.tfvars` (with `!*.tfvars.example`) | ✓ |
| `.venv/` / `__pycache__/` / `dist/` / `build/` | ✓ |
| `.claude/` (added this round) | ✓ |

## History audit

- `git log --all --pretty=format: --name-only -- .openai` → **never committed**
- `git log --all -- .claude/` → **never committed**
- `git log --all --diff-filter=A --name-only` filtered for `.env|.pem|.key|credentials|.p12|.pfx|.tfstate` → **no matches**

No secrets were ever in history; no rotation or `git-filter-repo` action required before flipping public.

## Pre-flip checklist (run before clicking "make public")

- [x] Working tree contains no API keys / tokens / private keys
- [x] Git history contains no API keys / tokens / private keys
- [x] No internal IP addresses in committed source files
- [x] `.gitignore` covers all known credential file patterns
- [x] `.claude/` (per-developer agent config) gitignored
- [x] Tests still green after edits (181 Python passing)
- [ ] Commit the cleanup + push (next step)
- [ ] Verify CI green on the cleanup commit before flipping the visibility switch
