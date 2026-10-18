# MySQL Release Pipeline

Versioned Flyway migrations for a MySQL 8.0 database, validated by an automated release pipeline.

```bash
docker compose up -d --wait
scripts/flyway.sh migrate
```
