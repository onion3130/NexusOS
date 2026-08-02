# NexusOS security baseline

**Status:** Phase 0/Phase 1 design; implementation controls must be verified as each milestone lands.

## Public GitHub safety

- `.env`, `.env.*`, databases, runtime data, logs, builds, dependency folders, and editor settings are ignored.
- `.env.example` contains placeholders only and is the only environment file intended for Git.
- Secret scans run before commits and in CI once CI exists.
- Git history must be reviewed before publishing; removing a secret from the working tree does not remove it from history.
- If a real credential is exposed, revoke/rotate it immediately and investigate the full history.

## Runtime boundaries

- The browser never receives provider keys, database credentials, Docker socket access, or host paths.
- The API is the authorization boundary; frontend visibility is not authorization.
- Host actions use typed allowlists and audited adapters, never arbitrary shell text.
- Plugins run out of process with least privilege and receive no Docker socket or unrestricted filesystem.
- External integrations are outbound-only and optional; provider failures degrade without taking down core services.

## Authentication and data

- Passwords use Argon2id or an equally reviewed password hashing library.
- Sessions are server-tracked; tokens are short-lived, rotated, revocable, and never stored in logs.
- Cookie-authenticated mutations require CSRF protection and strict origin/CORS controls.
- Production cookies are Secure and HttpOnly; development insecure-cookie mode is local-only.
- Sensitive integration credentials are encrypted or held by a secret manager; they are not ordinary settings or API responses.
- Logs are structured, bounded, redacted, and retained for a documented period.

## Deployment

- Pi services use ARM64-reviewed images, private networks, non-root users, read-only filesystems where practical, and resource limits.
- Only the reverse proxy publishes a host port in normal deployment.
- The external SSD is primary runtime storage, not the only backup.
- Backups are encrypted, rotated, and periodically restored in a drill.
- Administrative services are LAN-private by default; remote access requires an explicitly approved VPN/tunnel design.

## Change checklist

Before merging a feature:

1. Identify new secrets/configuration and add placeholders only to `.env.example`.
2. Confirm no credential-shaped literals, private keys, or personal data are present.
3. Add authentication/authorization and audit requirements to the API contract.
4. Define failure, timeout, retry, and redaction behavior.
5. Run tests, Compose validation, secret scanning, and `git diff --check`.
6. Review the complete diff and staged file list before committing.
