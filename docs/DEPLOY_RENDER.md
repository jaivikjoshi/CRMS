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

## Free Tier Notes

- **Spins down** after ~15 min of no traffic. First request after that may take 30–60 seconds.
- **Postgres** (Render): 1 GB, 90-day limit on free tier.
- **Supabase**: Free tier is more generous for long-term use.

---

## Test Your Deployment

```bash
curl https://YOUR-APP.onrender.com/health
curl -X POST https://YOUR-APP.onrender.com/v1/evaluations \
  -H "Authorization: Bearer sk_demo_crms_12345" \
  -H "Content-Type: application/json" \
  -d '{"effective_at":"2026-02-20T00:00:00Z","transaction":{"jurisdiction":"US-CA","tax_type":"SALES","amount":100,"product":{"category":"SAAS"},"buyer":{"type":"CONSUMER"}}}'
```
