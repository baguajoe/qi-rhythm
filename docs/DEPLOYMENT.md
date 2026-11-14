# Deploying Qi Rhythm (configs only — not yet deployed)

## Backend → Railway

1. Create a Railway project with a **PostgreSQL** plugin and a service from this repo with
   **root directory `backend/`**. Railway reads `backend/railway.json`:
   - pre-deploy: `flask --app wsgi db upgrade` and `flask --app wsgi seed` (idempotent)
   - start: `gunicorn -c gunicorn.conf.py wsgi:app` — **one** gevent-websocket worker
     (Socket.IO + in-memory live display state require a single worker; see CLAUDE.md)
   - health check: `GET /health`
   - Python version from `backend/.python-version` (3.13)
2. Add a second Railway service (same repo/root) as a **cron job**, schedule `0 4 * * *`, command
   `flask --app wsgi purge-recordings` — deletes recordings past each organization's retention.
3. Set the environment variables below.

| Variable | Required | Example / notes |
| --- | --- | --- |
| `DATABASE_URL` | yes | Provided by the Railway Postgres plugin (`postgresql://…` is normalised to psycopg3) |
| `SECRET_KEY` | yes | Long random string |
| `JWT_SECRET_KEY` | yes | Long random string (≥ 32 bytes) |
| `CORS_ORIGINS` | yes | `https://qi-rhythm.vercel.app` (comma-separated list) |
| `SOCKETIO_ASYNC_MODE` | yes | `gevent` |
| `STORAGE_BACKEND` | yes | `r2` |
| `R2_ACCOUNT_ID` | yes (r2) | Cloudflare account id |
| `R2_ACCESS_KEY_ID` / `R2_SECRET_ACCESS_KEY` | yes (r2) | R2 API token with read/write on the bucket |
| `R2_BUCKET` | yes (r2) | `qi-rhythm-recordings` (keep the bucket **private**) |
| `RECORDING_RETENTION_DAYS` | no | Default for new organizations: `7` |
| `JWT_ACCESS_HOURS` | no | Instructor sign-in length, default `12` |
| `DISPLAY_TOKEN_MINUTES` | no | TV pairing code lifetime, default `15` |
| `AUDIO_WARMUP` | no | `1` pre-compiles the audio engine at worker start |
| `LOG_LEVEL` | no | `info` |

Do **not** set `DEMO_EMAIL`/`DEMO_PASSWORD` or run `seed --demo` in production.

Storage layout in the bucket: `recordings/…` (team takes, deleted by the retention purge) and
`backing/org-<id>/rhythm-<id>/…` (backing-track loops uploaded on the Backing music page; never
purged, deleted only when an admin deletes or replaces a loop). Loops are streamed to the class
page through the API (`GET /api/backing-tracks/<id>/audio`), so the bucket stays private. Uploads
are capped at 25 MB (`MAX_CONTENT_LENGTH`); a 16-bit or 24-bit loop of a few bars fits easily.

## Frontend → Vercel

1. Import the repo with **root directory `frontend/`** (framework: Vite). `frontend/vercel.json`
   adds SPA rewrites (so `/display/:id` works on refresh) and headers
   (`Permissions-Policy: microphone=(self)`).
2. Environment variable: `VITE_API_URL=https://<your-railway-backend>.up.railway.app`.
3. Add the Vercel URL to the backend's `CORS_ORIGINS`.

## Checks after deploying

- `GET /health` returns `{"status": "ok"}`.
- Sign in, run Room setup, start a class, open the TV screen in a second window, run one turn.
- Microphone access requires HTTPS (Vercel provides it).
