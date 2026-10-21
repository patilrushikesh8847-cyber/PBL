# Security and privacy status

## Implemented in the local prototype

- Passwords are stored as scrypt hashes, not plaintext.
- API authorization derives the account from a random bearer token; interview lookups include the authenticated owner.
- SQL statements use bound parameters. Pydantic enforces field and answer length bounds.
- Dynamic browser text is HTML-escaped before insertion.
- Account deletion cascades to local sessions, answers, and active tokens.
- `.env`, local databases, and private runtime data paths are ignored by Git.
- The interface discloses that answer text is saved locally and that feedback is heuristic, not AI.

## Not implemented / not reviewed

This prototype lacks managed authentication, email verification/recovery, rate limiting, CSP and other security headers, production CORS/TLS configuration, structured redacted logs, request-size limits at a reverse proxy, a formal retention schedule, a privacy policy/terms, dependency/security scanning, penetration testing, backups, and legal review. Browser bearer-token storage is not approved as a production session design.

There is no AI provider, microphone, file upload, video, user-code execution, or external URL fetch. Do not add these features without their required threat model, consent, isolation, and tests. Do not deploy publicly or enter real secrets/sensitive personal answers.
