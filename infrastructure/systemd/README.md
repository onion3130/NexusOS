# Raspberry Pi systemd deployment

`nexus.service` is the opt-in production startup unit for the hardened Compose overlay. Install it only after the repository is placed at `/opt/nexusos`, a dedicated `nexus` service account exists, and the SSD is mounted at `/var/lib/nexus/data`.

## Install

```sh
sudo install -d -o nexus -g nexus /opt/nexusos
sudo install -o root -g root -m 0644 infrastructure/systemd/nexus.service /etc/systemd/system/nexus.service
sudo systemctl daemon-reload
sudo systemctl enable --now nexus.service
sudo systemctl status nexus.service
```

The unit waits for Docker and uses `RequiresMountsFor=/var/lib/nexus/data`. Add the `nexus` service account to the host's `docker` group (or use an equivalent rootless Docker socket) before enabling the unit; this is an intentional host-level privilege boundary. The unit runs `docker compose up` in the foreground with `Restart=on-failure` and `RestartSec=15`; each container also keeps Compose's `restart: unless-stopped` policy, and the proxy healthcheck reports service health. Credentials remain in `/opt/nexusos/.env`, never in unit arguments or logs.

## Upgrade and rollback

1. Create and verify a local backup, and confirm the latest encrypted artifact is replicated if configured.
2. Stop the unit with `sudo systemctl stop nexus.service`.
3. Keep the previous Git revision available; update the checkout and run explicit migrations with the API image.
4. Start the unit and verify proxy, API readiness, worker health, and the Maintenance status panel.
5. Roll back the checkout and database through the confirmation-gated in-app restore action or the documented operator procedure if readiness or migration validation fails.

Restore is a confirmation-gated Maintenance action (risk `high`) that runs only in the worker after explicit user confirmation: it creates a verified safety backup of the current database, stages the chosen verified backup (local or decrypted encrypted off-host artifact when the replication key is configured), re-verifies SHA-256 and `PRAGMA integrity_check`, swaps it in atomically, and requires an API/worker restart. The assistant cannot trigger restore. For offline recovery without the API, preserve the existing database, verify the encrypted artifact with the configured key, restore through an operator-controlled procedure, run `PRAGMA integrity_check`, then apply migrations deliberately.

Backup retention (confirmed `maintenance.retention_cleanup`, `medium`) prunes verified backups beyond `BACKUP_RETENTION_COUNT` / `BACKUP_RETENTION_DAYS` with last-backup protection, deleting only digest-matched local artifacts and, when configured, encrypted off-host artifacts. To rotate the encryption key, set `BACKUP_REPLICATION_KEY_PREVIOUS` to the old `BACKUP_ENCRYPTION_KEY` in `/opt/nexusos/.env`, run the confirmed `maintenance.rotate_encryption_key` action (`high`), verify the artifacts, then remove the previous key from the environment and restart the stack.
