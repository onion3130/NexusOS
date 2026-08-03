# Security policy

NexusOS is a local-first project intended to run privately on a Raspberry Pi or another self-hosted system. Security issues are taken seriously.

## Supported versions

The repository is pre-release. The `main` branch is the actively maintained development line. There are currently no published release versions with separate security support windows.

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
