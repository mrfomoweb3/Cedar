# Security Policy

## Supported versions

The `main` branch and the live deployment at https://trycedar.xyz.

## Reporting a vulnerability

Please **do not** open a public issue for security-sensitive reports.

- Use GitHub's [private vulnerability reporting](https://github.com/mrfomoweb3/Cedar/security/advisories/new), or
- DM [@trycedar](https://x.com/trycedar) on X.

You'll get an acknowledgment within 72 hours. Please include reproduction steps and impact.

## Scope notes

- The deployed VaultRouter contract is **owner-gated**; only the agent key can call state-changing entrypoints. Testnet only — no real funds.
- The API's write endpoints support an optional admin token (`CEDAR_ADMIN_TOKEN`); the public demo deliberately leaves them open with a mock data source.
- Server responses redact key material defensively (`redact_secrets`); report any bypass you find.
