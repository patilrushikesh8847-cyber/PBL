# Local MVP architecture

The app is intentionally a same-origin local prototype:

1. The browser loads `Fontend.html` from FastAPI `GET /`.
2. Browser interactions call versioned `/api/v1/...` JSON routes.
3. FastAPI/Pydantic validate request data and resolve bearer-token identity.
4. `app/main.py` uses parameterized SQLite statements and foreign keys for accounts, auth tokens, interview sessions, and answers.
5. Curated question content is held in the API module. If `AI_PROVIDER=anthropic`, `app/services/anthropic_ai.py` makes bounded server-side requests for original questions and structured practice evaluation; otherwise, the app uses its explicitly labeled rule-based demo. AI questions fall back to curated questions on provider/configuration failure. Evaluation failures return an error and leave saved answers in progress for retry.

Anthropic output is validated with Pydantic schemas. Evaluation requires the published five-dimension rubric for the selected category; the app recalculates answer and overall scores as arithmetic means, and saves the result with provider/model/rubric metadata. Provider keys are read only from server environment/configuration and are never sent to the browser. Mocked automated tests cover the integration paths; live provider response quality has not been verified without an operator key.

SQLite is created under `data/` by default (ignored by Git); `INTERVIEW_COACH_DB` can change its path. Tests override the path with a temporary database.

This is not the final architecture in the specification: only Anthropic is supported (there is no provider-neutral abstraction), the browser app and API are still single-file implementations, SQLite schema creation runs at startup, and the local token scheme is not a managed production identity provider. Usage budgets and production rate limits are also absent. Do not expose the development service to the public internet.
