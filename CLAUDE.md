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
2. [ ] Audio engine in isolation (synth, onset, align, scoring, CLI) + pytest suite
3. [ ] Models, migrations, seed data
4. [ ] Auth + teams
5. [ ] Rhythm library + Tone.js player + beat visualizer
6. [ ] Calibration wizard
7. [ ] Rhythm Recall round, full loop
8. [ ] Display View + Socket.IO + display-token pairing + reconnection
9. [ ] Session scoreboard + saved Activities
10. [ ] Accessibility pass (axe-core)
11. [ ] Deployment configs (Railway, Vercel) — do not deploy

Later phases (extension points only): Phase 2 game modes & brackets; Phase 3–4 testing tooling and
event/demo mode (May 2027 Senior Community Wellness Day); Phase 5 remote tournaments, Beat Builder,
Rhythm & Movement, Sound Relaxation, ML percussion classification, subscriptions.

## Open TODOs / stubs
_(none yet)_

## Review flags before launch
- Genre `cultural_notes` must be reviewed by a knowledgeable musician.
