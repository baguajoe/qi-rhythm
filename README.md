# Qi Rhythm

Instructor-led rhythm, memory, and team games for senior centers and assisted-living
communities. One laptop + a TV + real hand percussion; no participant devices needed.

Developed by Eye Forge Studios with Qi Code Academy, Inc. as community programming partner.

See [CLAUDE.md](CLAUDE.md) for setup commands, architecture, and roadmap.

## Quick start
```bash
cp .env.example .env
docker compose up -d db
cd backend && python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt && .venv/bin/pytest -q
cd ../frontend && npm install && npm test && npm run dev
```
