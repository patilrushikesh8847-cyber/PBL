# Deployment status

The repository includes a **temporary public-demo-only** Render Blueprint in `render.yaml`. Use the [Render deployment instructions in the README](../README.md#public-demo-on-render) to create a free demo service. Its SQLite database is stored under `/tmp` and can be erased on restart/redeploy. It runs rule-based feedback and does not need provider credentials.

Before deployment, implement and verify managed authentication, PostgreSQL and versioned migrations, secret management, production cookie/token strategy, CORS allowlist, HTTPS, security headers, request and provider-usage rate limits, privacy and retention policy, backup/restore, health monitoring, deployment rollback, and staging E2E/security tests. Configure provider credentials only on the server, and complete human privacy/legal and operational reviews.

The Render account/service has not been connected from this workspace, so a public app URL is not created automatically. Render will provide the URL after you apply the Blueprint and the service deploys. Production launch remains blocked pending the controls above.
