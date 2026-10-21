# Project plan and current phase

## Existing state

The repository began with a requirements text file and a static HTML export. The current working tree preserves that export as `Fontend.original.html` and serves the standalone replacement `Fontend.html` from a FastAPI/SQLite local MVP.

## Phases

| Phase | Scope | Current state |
|---|---|---|
| 0 — Audit and plan | Inspect source and requirements; preserve original; map gaps | Done for this local iteration; see `REQUIREMENTS_TRACEABILITY.md` |
| 1 — Foundation | Local app, configuration example, API docs, health, tests | Implemented locally; no CI/build/deployment setup |
| 2 — Database/auth | Persistent users/sessions, authentication, ownership | Partial: local SQLite/custom auth only; no managed auth, PostgreSQL, or migrations |
| 3 — UI/dashboard/profile | Landing, dashboard, profile, settings, states | Partial: local responsive screens; onboarding and full accessibility verification remain |
| 4 — Question bank/setup | Curated content and validated setup | Partial: original in-source questions; basic filters; no database-managed bank |
| 5 — Text interview | One question at a time, persist answers, resume, complete | Implemented locally; browser end-to-end and recovery checks remain |
| 6 — AI integration | Provider, schemas, rubric, timeout/retry/rate limits | Partially implemented: Anthropic adapter, structured question/evaluation output, rubric normalization, bounded retries/timeouts, and mocked failure/success tests; no live credentials, provider-neutral adapter, usage budget, or production rate limits |
| 7 — Results/history | Saved result, detail, history, filtering, deletion | Partial: heuristic result and bounded local history; no analytical trends |
| 8 — Security/privacy | Managed auth, hardening, legal/privacy review | Not complete; do not deploy publicly |
| 9 — P1 | Voice, resume, reports, analytics, bookmarks, plans | Not started; wait for P0 approval/stability |
| 10 — P2 | Coding sandbox and advanced practice | Not started |
| 11 — Deployment | Production domains, secrets, backups, monitoring, staging | Blocked on operator/provider setup |
| 12 — Handover | Full acceptance, release checklist and evidence | Partial; matrix reports remaining work |

## Work remaining before calling P0 ready

1. Choose a managed auth/database architecture and implement versioned migrations.
2. Verify one live server-side Anthropic question/evaluation flow with authorized credentials; add a provider-neutral abstraction and production rate limits/usage budgets before claiming the AI P0 complete.
3. Complete onboarding and verify session restoration in a browser after reload/login.
4. Add frontend component/E2E tests, cross-user update/delete authorization tests, and mobile/accessibility checks.
5. Add privacy/terms/contact content, retention policy, secure deployment configuration, backups, and staging verification.

P1 must not begin until P0 acceptance is reviewed and the user confirms the next phase. Do not enable code execution without an independently verified isolated sandbox.
