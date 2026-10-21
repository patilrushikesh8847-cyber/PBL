# Deployment status

There is no supported production deployment configuration yet. Run the application locally using the commands in `README.md`. The local bearer-token authentication and SQLite configuration must not be exposed to the public internet. The Anthropic integration has mocked test coverage only and has not been verified against a live provider.

Before deployment, implement and verify managed authentication, PostgreSQL and versioned migrations, secret management, production cookie/token strategy, CORS allowlist, HTTPS, security headers, request and provider-usage rate limits, privacy and retention policy, backup/restore, health monitoring, deployment rollback, and staging E2E/security tests. Configure provider credentials only on the server, and complete human privacy/legal and operational reviews.

No real provider account, deployment platform, production domain, credentials, or billing configuration has been supplied. Production launch is therefore blocked.
