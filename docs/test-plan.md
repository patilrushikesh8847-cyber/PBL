# Test plan

## Automated checks currently available

Run from the repository root after installing `requirements.txt` and the test packages:

```powershell
python -m pip install pytest httpx
python -m pytest -q
```

The tests use a temporary SQLite database and mock provider responses. They cover account creation, duplicate registration, login/logout, unauthenticated access, profile update/deletion, account-owned record deletion, interview creation, answer persistence, completion feedback, incomplete completion rejection, question filters/bounds, question ID uniqueness for ten-question sessions, schema/rubric validation, AI result persistence and idempotent retrieval, and preservation of saved answers after provider failure.

Latest pre-provider full test run: **7 tests passed**. Current post-provider run: **11 tests passed**. Provider tests are mocked and do not verify live Anthropic credentials, availability, or answer quality. A browser smoke run completed account creation and a five-question demo session through the saved result screen after the provider UI changes.

Validate inline browser JavaScript syntax with Node:

```powershell
$content = Get-Content -LiteralPath '.\Fontend.html' -Raw
$match = [regex]::Match($content, '(?s)<script>(.*?)</script>')
$match.Groups[1].Value | node --check -
```

## Manual checks still required

- Complete registration, login, profile onboarding, a full interview, result, logout, and later login in a clean browser profile.
- Reload an in-progress interview and verify saved answers resume correctly.
- Test desktop, tablet, mobile, browser zoom, keyboard-only navigation, contrast, and screen-reader announcements.
- Exercise network/server errors during save and completion.
- Test all owner/non-owner read, update, and delete combinations.
- Test clean setup and database upgrades against fresh and existing databases.
- With authorized server credentials, verify one live Anthropic question-generation and evaluation round trip; never use real credentials in automated tests or chat.
- Before production: CI, frontend build/E2E, security/dependency checks, backup/restore, staging deployment, and provider failure tests.

No production or AI acceptance criterion should be inferred from passing this local test suite.
