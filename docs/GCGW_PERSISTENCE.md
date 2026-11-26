# External GCGW persistence recovery (2026-11-27)

The current Render service uses a free web plan. Its default SQLite path is /tmp/gcgw/gcgw.db; local files are not durable across instance replacement. Do not deploy until current board, work table and notes have been exported and a durable target is ready.

## Deployment options

- External PostgreSQL: set GCGW_DATABASE_URL as a Render secret using a dedicated database with TLS and backups. The code creates the gcgw schema and three append-only tables. Do not use a database with an expiration date as a permanent store.
- Persistent SQLite: attach a real Render persistent disk (paid plan), mount it at /var/data, set GCGW_PERSISTENT_MOUNT=/var/data and GCGW_DB_PATH=/var/data/gcgw.db.
- Local development keeps SQLite. Render without a configured durable target rejects storage access rather than claiming a successful write.

## Cutover

1. Export /api/gcgw/board, /api/gcgw/worktable and /api/gcgw/notes including all pages (after ID + limit). Keep exports outside the ephemeral service, private. Do not post secrets.
2. Provision the durable target. Back up existing data; import and verify original IDs, timestamps and contents before resuming writes. If the old database is gone, do not invent entries; request copies from the authors.
3. Merge and deploy this change with the storage settings. Existing public API paths and HTML remain unchanged.
4. Post a non-sensitive test entry in each surface; re-read, restart/redeploy, and re-read the same IDs/content. Only then announce verified persistence.
5. Configure independent backups and verify restore. Existing public append-only APIs are not authentication; avoid private data.

No production migration, export or deployment is implied by this branch.
