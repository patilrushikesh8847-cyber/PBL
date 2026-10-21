# Interview Coach

A runnable local MVP built from the supplied requirements. The repository includes a responsive browser frontend, a FastAPI backend, SQLite persistence, local registration/sign-in, private interview sessions, curated questions, an optional server-side Anthropic integration, and an explicitly labeled rule-based demo mode.

> **Important:** This is a local-development starter, not a production-ready service. The Anthropic integration has mocked test coverage but has not been verified with live credentials. Local custom authentication is not a managed identity provider; email verification and password reset are not implemented. Feedback is practice-only, may be inaccurate, and must never be used for hiring decisions. Do not use real credentials or enter sensitive personal data.

## Project structure

```text
.
├── AI_Interview_Coach_Complete_Requirements.txt
├── Fontend.html                 # Responsive app frontend served by FastAPI
├── Fontend.original.html        # Preserved original static HTML export
├── app/
│   ├── __init__.py
│   ├── main.py                  # API routes, SQLite persistence, local auth
│   └── services/
│       └── anthropic_ai.py      # Server-side AI question and evaluation adapter
├── data/                        # Created at runtime; ignored by Git
├── tests/
│   └── test_main.py
├── docs/
│   ├── architecture.md
│   ├── deployment.md
│   ├── security-and-privacy.md
│   ├── test-plan.md
│   └── troubleshooting.md
├── PROJECT_PLAN.md
├── REQUIREMENTS_TRACEABILITY.md
├── .env.example
├── .gitignore
└── requirements.txt
```

## Run locally on Windows

Open PowerShell in this directory:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --reload
```

Open <http://127.0.0.1:8000>. API documentation is available at <http://127.0.0.1:8000/docs>. SQLite data is stored at `data/interview_coach.db` by default. Set `INTERVIEW_COACH_DB` to change the database path.

For the no-key local demo, leave `AI_PROVIDER` unset (it defaults to `rule_based_demo`). To use Anthropic, copy `.env.example` to `.env`, set a valid server-side `ANTHROPIC_API_KEY` and enabled `ANTHROPIC_MODEL`, then run the app. Never put provider keys in frontend code or commit `.env`. If question generation is unavailable, the app identifies its curated-question fallback; evaluation errors preserve saved answers so the user can retry.

## Public demo on Render

This repository includes a Render Blueprint for a temporary, rule-based demo. [Deploy it to Render](https://render.com/deploy?repo=https%3A%2F%2Fgithub.com%2Fpatilrushikesh8847-cyber%2FPBL), connect your GitHub account, review the Blueprint, and select **Apply**. Render will provide the public URL after the service finishes deploying.

**Demo-only warning:** the Blueprint uses the free web-service plan and stores SQLite data under `/tmp`. Data may be erased whenever the service restarts or redeploys. The app also uses local demo authentication and has no production-grade rate limiting. Do not enter real passwords, personal information, or confidential interview answers. Do not enable Anthropic or add API keys to this public demo. Production deployment requires a persistent/managed database, managed authentication, and security hardening.

If PowerShell blocks virtual-environment activation, run the interpreter and Uvicorn directly:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

## Tests

Install the test dependencies, then run:

```powershell
python -m pip install pytest httpx
python -m pytest
```

## Implemented in this local MVP

- Registration, sign-in, sign-out, profile editing/deletion, password hashing, expiring bearer sessions.
- Curated behavioral and technical question bank, category/difficulty setup, and bounded interview length.
- Question search plus category, difficulty, and skill filters; history filters and session deletion.
- Text answers saved to SQLite, with session completion checks.
- Optional Anthropic-generated questions and schema-validated practice evaluation; demo mode is labeled rule-based and is not AI.
- Rubric feedback and dashboard/history derived from persisted sessions.
- Ownership checks for protected interview records, bounded query results, health/readiness endpoints, and input validation.
- Responsive layout, keyboard focus visibility, reduced-motion support, and accessible form/status labels.

## Remaining production/P0 gaps

The live Anthropic service cannot be verified without operator-provided credentials. Password reset/email verification, managed authentication, PostgreSQL migrations, provider usage budgets/rate limits, production deployment, progress charts, voice, resume upload, report export, and advanced P1/P2 features are not complete. Before deployment, add managed authentication, production-grade secrets/configuration, HTTPS/security headers, rate limiting/usage controls, versioned migrations/backups, privacy/retention policy, and deployment/security tests. Keep provider credentials server-side and validate structured output.

See [REQUIREMENTS_TRACEABILITY.md](./REQUIREMENTS_TRACEABILITY.md) for the requirement-by-requirement status and evidence, [PROJECT_PLAN.md](./PROJECT_PLAN.md) for phase status, and the [docs/](./docs/) directory for architecture, security/privacy, deployment blockers, and test guidance.
