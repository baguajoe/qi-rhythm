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
9. [ ] Session scoreboard + saved Activities
10. [ ] Accessibility pass (axe-core)
11. [ ] Deployment configs (Railway, Vercel) — do not deploy

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

## Review flags before launch
- Genre `cultural_notes` must be reviewed by a knowledgeable musician.
