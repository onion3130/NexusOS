# Raspberry Pi systemd skeleton

The systemd unit is intentionally deferred until the application images and SSD mount policy exist. The eventual unit must:

- start after Docker and the external SSD mount are ready;
- use an absolute repository path and a dedicated service account;
- run `docker compose up -d` and stop with `docker compose down`;
- restart on failure without masking healthcheck failures;
- expose no credentials in unit arguments or logs;
- have a documented upgrade, rollback, and recovery procedure.

Do not install a unit generated from this document until the deployment milestone has supplied real images, mount UUIDs, resource limits, and a tested backup/restore procedure.
