# Troubleshooting

- **`python` is not found:** install Python 3.11+ and use the `py` launcher, or call `.\.venv\Scripts\python.exe` directly.
- **Port 8000 is busy:** stop the process that owns it or start Uvicorn on another port, e.g. `python -m uvicorn app.main:app --port 8001`; browse to that port.
- **Cannot sign in after restarting:** the browser token expires after seven days or is revoked on logout. Sign in again. The local SQLite database must still exist.
- **Database not ready:** check the `INTERVIEW_COACH_DB` path is writable and inspect the local server output. `/ready` intentionally returns a service-unavailable response when SQLite cannot be opened.
- **Question or answer request is rejected:** verify category/difficulty values and the documented length limits; FastAPI details are available at `/docs`.
- **Tests cannot import `pytest`/`httpx`:** install the test-only packages with `python -m pip install pytest httpx`.
- **Anthropic is not configured:** `AI_PROVIDER=anthropic` requires a valid server-side `ANTHROPIC_API_KEY` and enabled `ANTHROPIC_MODEL`. Keep them in ignored `.env` or the deployment secret store; never enter the key in the browser or commit it.
- **Questions appear curated while Anthropic is selected:** question-generation or configuration errors use a disclosed curated-question fallback. Check the server configuration and logs, then start a new interview after the provider is available.
- **Cannot complete an Anthropic evaluation:** the API reports the provider/schema error and preserves answers in the in-progress session so completion can be retried. The rule-based demo is available only when `AI_PROVIDER=rule_based_demo`; it is not AI feedback.
- **Anthropic test results:** integration tests mock provider responses and need no API key. They verify application behavior, not live model availability or factual quality.
