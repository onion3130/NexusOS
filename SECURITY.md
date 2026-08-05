# Security policy

NexusOS is a local-first project intended to run privately on a Raspberry Pi or another self-hosted system. Security issues are taken seriously.

## Supported versions

The `v1.5.x` release line is supported for the private, local-first deployment described in the documentation. The `main` branch remains the actively maintained development line. Do not expose NexusOS directly to the public internet without the documented hardened proxy, TLS, and access controls.

## Reporting a vulnerability

Please do **not** open a public issue for a suspected vulnerability.

Use GitHub's private vulnerability reporting feature for this repository when available. If it is unavailable, contact the maintainers privately through GitHub with:

- A clear description of the issue and its impact
- Reproduction steps or a minimal proof of concept
- Affected commit, component, or configuration
- Any suggested mitigation

Please allow maintainers reasonable time to investigate before public disclosure. Do not include real credentials, private data, or production secrets in a report.

## Security guidance

See the detailed [NexusOS security baseline](docs/SECURITY.md) for authentication, ownership, CSRF, assistant actions, deployment boundaries, secrets, and Raspberry Pi operational guidance.
