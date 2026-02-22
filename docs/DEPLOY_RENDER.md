# Deploy CRMS to Render

## Option A: Blueprint (Render Postgres)

1. Push your repo to GitHub.
2. Go to [render.com](https://render.com) → **New** → **Blueprint**.
3. Connect your GitHub repo.
4. Render will detect `render.yaml` and create:
   - A **Web Service** (CRMS API)
   - A **Postgres** database
5. Deploy. The API will run migrations and seed on first start.
6. Your API URL: `https://crms-xxxx.onrender.com`
7. **API Key**: `sk_demo_crms_12345` (from seed)

---

## Option B: Manual (Use Supabase)

If you already have Supabase:

1. **New** → **Web Service**
2. Connect your GitHub repo.
3. **Build Command**: `pip install -r requirements.txt`
4. **Start Command**: `alembic upgrade head && uvicorn crms.main:app --host 0.0.0.0 --port $PORT`
5. **Environment Variables**:
   - `DATABASE_URL` = your Supabase connection string (use `postgresql+asyncpg://...` or `postgresql://...` — both work)
   - `API_KEY_HASH_SALT` = any random string (or leave default)
6. Deploy.
7. Run seed via **Shell** (in Render dashboard): `python scripts/seed.py`

---

## Free Tier Rules & Limits

| Limit | Value |
|-------|-------|
| **Instance hours** | 750/month (resets each month) |
| **Spins down** | After 15 min inactivity; first request after ~30–60 sec |
| **Postgres** (Render) | 1 GB, **expires 90 days** after creation |
| **Filesystem** | Ephemeral (lost on redeploy/restart) |
| **Use case** | Testing, hobby, demos — not production |

**Recommendation:** For a demo that lasts longer than 90 days, use **Option B (Supabase)** for the database. Supabase free tier does not expire.

---

## Test Your Deployment

```bash
curl https://YOUR-APP.onrender.com/health
curl -X POST https://YOUR-APP.onrender.com/v1/evaluations \
  -H "Authorization: Bearer sk_demo_crms_12345" \
  -H "Content-Type: application/json" \
  -d '{"effective_at":"2026-02-20T00:00:00Z","transaction":{"jurisdiction":"US-CA","tax_type":"SALES","amount":100,"product":{"category":"SAAS"},"buyer":{"type":"CONSUMER"}}}'
```
