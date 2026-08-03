# Imperium — Deployment (managed backing services)

The backend reads every connection string from environment variables (see
`backend/imperium/config.py`), so "going to production" means pointing those vars at
**managed, always-on, secured instances** instead of local dev containers. No code
changes are required beyond what is already shipped.

| Store | Local dev | Production (managed) | Code change? |
|-------|-----------|----------------------|--------------|
| Postgres | `podman`/`docker` container | Supabase / RDS / Cloud SQL / Neon | none |
| Qdrant | container (`--network=host` on rootless podman) | **Qdrant Cloud** | API key (shipped) |
| Neo4j | `neo4j:5-community` container | **Neo4j AuraDB** | none |
| Redis | `redis:7-alpine` container | **Upstash / Redis Cloud / ElastiCache** | none |

Secrets live only in the environment (`.env` locally — git-ignored — or the host's secret
store in prod). **Never commit real credentials.**

---

## 1. Qdrant → Qdrant Cloud

1. Sign up at **cloud.qdrant.io** and **create a cluster** (free tier = 1GB); pick a
   region near the backend.
2. Copy the cluster **Endpoint URL**.
3. **API Keys → Create API key**, copy it (shown once).
4. Set:
   ```bash
   QDRANT_URL=https://<cluster>.aws.cloud.qdrant.io
   QDRANT_API_KEY=<key>
   QDRANT_COLLECTION=imperium_rkb
   ```
The `imperium_rkb` collection auto-creates on first upsert. The client passes the API
key automatically (`rkb/embeddings.py`); an empty key = local instance with no auth.

## 2. Neo4j → Neo4j AuraDB

1. Sign up at **console.neo4j.io** and **create an AuraDB Free instance**.
2. **Save the generated password immediately** (shown only once; also downloadable as a
   `.txt`).
3. Copy the **Connection URI** (`neo4j+s://<id>.databases.neo4j.io` — `+s` = TLS).
4. Set:
   ```bash
   NEO4J_URI=neo4j+s://<id>.databases.neo4j.io
   NEO4J_USER=neo4j          # AuraDB default; use the value from the credentials file
   NEO4J_PASSWORD=<password>
   ```
Wait until the instance status is **Running**. The driver already supports `neo4j+s://`.

## 3. Redis → Upstash

1. Sign up at **console.upstash.com** → **Create Database → Redis**, region near backend,
   TLS enabled (default).
2. From **Connect**, copy the `rediss://…` URL (password embedded, port 6379).
3. Set:
   ```bash
   REDIS_URL=rediss://default:<password>@<host>.upstash.io:6379
   ```
`redis.from_url()` handles `rediss://` TLS with no code change. Redis is cache-only here,
so it is the least critical store.

---

## Postgres (relational RKB store)

The relational store is **Postgres** via SQLAlchemy + Alembic. Use a managed Postgres
(**Supabase**, RDS, Cloud SQL, Neon):

```bash
POSTGRES_DSN=postgresql+psycopg://<user>:<pass>@<host>:5432/<db>
```

Run the schema migration as a release/startup step:

```bash
cd backend && alembic upgrade head
```

> ⚠️ **Firebase note:** Firebase/Firestore is a NoSQL document store and is **not**
> Postgres-compatible — it cannot back `POSTGRES_DSN`. Firebase is fine for
> auth/hosting/frontend, but the relational RKB store needs actual Postgres (Supabase
> gives managed Postgres *plus* Firebase-style auth/realtime).

---

## Production hardening checklist

- **Secrets:** no default passwords / `changeme` keys. Inject from a vault (AWS Secrets
  Manager, Doppler, k8s Secrets), not committed files.
- **TLS everywhere:** `rediss://`, `neo4j+s://`, `https://` Qdrant.
- **Private networking:** databases reachable only by the backend; only the FastAPI app
  (behind a TLS reverse proxy / load balancer) is public.
- **Backups:** managed services handle Postgres/Neo4j snapshots; verify retention.
- **Migrations:** `alembic upgrade head` in the deploy pipeline.
- **Durable runs:** run/analysis state is currently in-process; for multi-instance
  deploys move to the Postgres-checkpointer path so state survives restarts and
  load-balancing.

## Verify a deployment

```bash
curl -s https://<backend-host>/health/services | python -m json.tool
# expect all four: {"postgres":"ok","qdrant":"ok","neo4j":"ok","redis":"ok"}
```
