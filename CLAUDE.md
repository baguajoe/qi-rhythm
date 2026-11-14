# Qi Rhythm — CLAUDE.md

Instructor-led music, rhythm, memory, and team-competition web app for older adults in
senior centers and assisted-living facilities. Built by **Eye Forge Studios** with
**Qi Code Academy, Inc.** as community programming partner.

One instructor runs the app on a laptop/tablet connected to a TV. Participants play real
percussion; a microphone records the team, the backend detects strikes, compares them to a
reference rhythm, and updates a big-screen scoreboard. Participants never need devices.

**This is a recreational / wellness engagement platform — NOT a medical or dementia-treatment
app. Make no therapeutic or diagnostic claims in UI, copy, or code comments.**

## Stack
- Frontend: React 18 + Vite 6, vite-plugin-pwa, React Router 6, Tone.js 15, socket.io-client.
  Styling: **CSS Modules** + `src/styles/global.css` tokens (no Tailwind).
- Backend: Python 3.11+ (dev venv uses 3.13), Flask app factory + blueprints, Flask-SQLAlchemy,
  Flask-Migrate, Flask-JWT-Extended, Flask-SocketIO, Flask-Cors.
- DB: PostgreSQL 16 (Docker Compose in dev).
- Audio analysis: NumPy, SciPy, librosa, soundfile.
- Storage: Cloudflare R2 via boto3; local filesystem in dev.
- Tests: pytest; Vitest + React Testing Library.

## Commands
```bash
# Database (from repo root)
docker compose up -d db                 # postgres on :5432, creates qi_rhythm + qi_rhythm_test

# Backend (from backend/)
python3.13 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
.venv/bin/flask --app wsgi db upgrade   # migrate
.venv/bin/flask --app wsgi seed         # seed rhythm library (slice 3+)
.venv/bin/python wsgi.py                # dev server on :5000 (Socket.IO enabled)
.venv/bin/pytest -q                     # tests
.venv/bin/ruff check . && .venv/bin/black --check .   # lint
.venv/bin/python -m app.audio.cli score --pattern x.json --bpm 90 --wav take.wav  # (slice 2+)

# Production server locally (from backend/)
SOCKETIO_ASYNC_MODE=gevent PORT=8001 .venv/bin/gunicorn -c gunicorn.conf.py wsgi:app
.venv/bin/flask --app wsgi purge-recordings [--all]   # retention purge (daily cron in prod)

# Everything (from repo root): starts Postgres, runs pytest + Vitest + Playwright, stops Postgres
make test-all            # or: cd frontend && npm run test:all
make lint

# Frontend (from frontend/)
npm install
npm run dev        # :5173
npm test           # vitest
npm run lint       # eslint (incl. jsx-a11y strict)
npm run format     # prettier
npm run build
```

## Audio engine (backend/app/audio) — core IP, keep heavily tested
- `patterns.py` beat-relative pattern parsing. `synth.py` synthetic takes (jitter, misses, extras,
  offset, latency, tempo scale/drift, noise, rumble, count-in bleed).
- `onset.py`: 22.05 kHz mono → 70 Hz high-pass → librosa spectral flux (hop 128) → peak-pick →
  backtrack → sample-level attack refinement (~1 ms accuracy) → gates: noise floor + 9 dB,
  decay/ring masking (≤150 ms after a ≥9 dB louder strike), 30 dB below typical strike.
  Confidence = SNR ramp (6→24 dB) × near-threshold penalty.
- `align.py`: expected times = countin_start_s + (count_in + beat)·spb + latency. Onsets before
  pattern start − ½ beat (count-in bleed) or after end + ½ beat are ignored. Grid fit: tempo scale
  0.80–1.25 (biased to 1.0) + clamped median offset (±200 ms), then Hungarian matching.
- `scoring.py`: F1 pattern, preset timing ramp, tempo (overall IOI ratio + steadiness),
  completion; timing/tempo/completion × evidence factor min(1, matched/⌈expected/2⌉).
  needs_review when confidence < 0.5, no hits, or detected/expected outside 0.5–2.0.
  `mode` param selects weights (MODE_WEIGHTS) so Phase 2 modes reuse the engine.
- Call `scoring.warmup()` at worker start (numba JIT); warm analysis of 15 s clip ≈ 0.1 s.
- Design choice: a team playing the right pattern uniformly fast/slow is matched via the tempo
  fit and penalised only in tempo_consistency (e.g. 10% fast → tempo ≈ 70, total ≈ 95).

## Round flow
Dashboard → `POST /api/sessions/<id>/rounds` → `PATCH /api/rounds/<id> {status: playing_reference}`
→ Tone.js plays reference → `PATCH {status: recording}` → recorder starts, count-in clicks, team plays,
1 bar slack → `POST /api/rounds/<id>/recording` (WAV + `countin_start_s` = count-in click 1 time −
first recorded sample time, both on the shared AudioContext clock) → backend stores (R2/local),
analyses via the round's GameMode, saves Score, recomputes Team.total_points, broadcasts
`round:scored` + `scoreboard:updated`. Overrides keep the machine score (`Score.override_values`).
Retention: run `flask --app wsgi purge-recordings` daily (cron); `--all` deletes everything.
No speech is spoken while recording (it would be heard as hits).

## Display View & sockets
- Dashboard "Get a TV code" → `POST /api/sessions/<id>/display-code` (6 chars, 15 min) →
  TV opens `/display/<id>?code=…` → `POST /api/display/pair` → display JWT (`kind=display`,
  12 h, bound to one session; cannot call instructor endpoints).
- Socket clients connect with `auth.token`, then `join_session`; the server replies with a full
  `session:state` snapshot (DB + in-memory live phase) on every (re)connect.
- Only instructor sockets may send `control:*` events (focus, reference, beat, countin, recording,
  level, idle); the server relays them to the room. REST lifecycle changes broadcast
  `round:started|reference_playing|countin|analyzing|scored|overridden|stopped`, `scoreboard:updated`,
  `session:settings|ended`.
- Live state is in process memory: run ONE gevent worker (see Procfile).

## End-to-end tests (frontend/e2e, Playwright, Chromium only)
- `npx playwright test` (Postgres must be running) starts its own servers: backend = gunicorn+gevent
  on :5001 against a throwaway `qi_rhythm_e2e` DB (reset + migrated + seeded on every run by
  `backend/scripts/e2e_prepare_db.py`, which refuses DB names without "e2e"); frontend = production
  build served by `vite preview` on :5174.
- The "microphone" is a WAV: Chromium flags `--use-fake-device-for-media-stream
  --use-file-for-fake-audio-capture=<wav>%noloop`. Chromium restarts the file at 0 every time the
  page opens the mic (verified), so `backend/scripts/make_e2e_wavs.py` (uses synth.py + the seeded
  Son Clave 3-2 at 90 bpm) places hits relative to mic-open: count-in ≈ 0.30 s in for team turns,
  tap-test clicks ≈ 0.27 s in for calibration. Calibration taps use the short shaker voice so the
  wizard's noise step (which hears the same file) still measures a quiet room.
- Specs run in file order with 1 worker and share state via `e2e/.state.json`:
  01 register/login/room setup/teams → 02 perfect take + live TV + axe → 03 two missed hits →
  04 silence review prompt + override + TV drop/resync → 05 repeated reconnect stress (own org).
- Score thresholds are NOT widened: perfect take must be >= 95 (observed 100 on every run; browser
  timing offsets were 40–90 ms and are absorbed by offset correction). If a slow CI runner ever
  makes this flaky, set `E2E_PERFECT_MIN` (test-only) rather than changing the engine.
- `E2E_TURN_LEAD` / `E2E_CAL_LEAD` tweak WAV timing if a Chromium update changes mic-open timing.
- CI: `.github/workflows/ci.yml` (Postgres service container, uploads `playwright-report` always and
  `test-results` screenshots/videos/traces on failure).

## Conventions
- Conventional commits (`feat:`, `fix:`, `test:`, `chore:`); commit + push after each slice.
- Stubs are marked `# TODO(phase-N):` (or `// TODO(phase-N):`) and listed below.
- Secrets only in `.env` (gitignored); keep `.env.example` current.
- Participants: alias only. Never add fields holding participant PII.
- UI copy: plain language, encouraging, never shaming (no red "FAIL").
- Accessibility: base font 20px, Display headlines >= 48px, tap targets >= 56px,
  every audio cue has a visual cue, no flashing > 3/s, honour prefers-reduced-motion.
- Ask the project owner before adding paid services, heavy dependencies, or new personal data.

## Roadmap (Phase 1 slices)
1. [x] Scaffold
2. [x] Audio engine in isolation (synth, onset, align, scoring, CLI) + pytest suite
3. [x] Models, migrations, seed data (`flask --app wsgi seed --demo` → demo@example.com / rhythm-demo-123, dev only)
4. [x] Auth + teams
5. [x] Rhythm library + Tone.js player + beat visualizer
6. [x] Calibration wizard (calibration audio is analysed in memory, never stored)
7. [x] Rhythm Recall round, full loop
8. [x] Display View + Socket.IO + display-token pairing + reconnection (measured: 0.5 s resync after a dropped connection)
9. [x] Session scoreboard + saved Activities
10. [x] Accessibility pass: axe-core runs in Vitest over every page and Display phase
    (`src/test/pages.a11y.test.jsx`); token contrast tests enforce AA (normal) / AAA (high contrast)
    (`src/test/tokens.a11y.test.js`). Lighthouse needs Chrome (not in this Codespace) — run locally:
    `npm run build && npx vite preview --port 4173` then
    `npx lighthouse http://localhost:4173/login --only-categories=accessibility`.
11. [x] Deployment configs (Railway, Vercel) — see docs/DEPLOYMENT.md. Not deployed.

Later phases (extension points only): Phase 2 game modes & brackets; Phase 3–4 testing tooling and
event/demo mode (May 2027 Senior Community Wellness Day); Phase 5 remote tournaments, Beat Builder,
Rhythm & Movement, Sound Relaxation, ML percussion classification, subscriptions.

## Open TODOs / stubs
- `sockets/state.py` — TODO(phase-5): Redis-backed live state + Socket.IO message queue for multi-worker.
- `ShowOnTv.jsx` — TODO(phase-3): QR code for the pairing link (needs a small QR library; ask first).
- `frontend/src/lib/uploadQueue.js` — TODO(phase-3): persist pending takes in IndexedDB (currently
  retried in memory with backoff through network blips; lost on page reload).
- `frontend/src/audio/instruments.js` VOICE_SAMPLE_URLS — TODO(phase-2): swap synthesized kit for original Cubase-recorded one-shots on R2.
- `scoring.MODE_WEIGHTS` — TODO(phase-2): weights for Finish the Beat, Music Memory, Call-and-Response.
- `games/base.py` GameModeKey — TODO(phase-2)/(phase-5): new modes implement `GameMode`
  (setup/reference/capture/analyze/score) and call `register()`; scoring takes `mode`.

## Review flags before launch
- Genre `cultural_notes` (backend/app/seed/library.py) must be reviewed by a knowledgeable musician.
- Run Lighthouse accessibility on /login, / and /display/:id; target >= 95 (Playwright's Chromium is
  now installed: `npx lighthouse … --chrome-flags=--headless` with CHROME_PATH pointing at it).
- Field-test scoring with real hand drums/shakers in a real room; synthetic tests can't capture
  every room (reverb, crowd noise, Bluetooth speaker latency).
