import { execFileSync } from 'node:child_process';
import { rmSync } from 'node:fs';
import { resolve } from 'node:path';
import { STATE_FILE, WAV_DIR } from './helpers.js';

export default function globalSetup() {
  rmSync(STATE_FILE, { force: true });
  const python = process.env.E2E_PYTHON || '.venv/bin/python';
  const args = ['scripts/make_e2e_wavs.py', '--out', WAV_DIR];
  if (process.env.E2E_TURN_LEAD) args.push('--turn-lead', process.env.E2E_TURN_LEAD);
  if (process.env.E2E_CAL_LEAD) args.push('--cal-lead', process.env.E2E_CAL_LEAD);
  execFileSync(python, args, {
    cwd: resolve(import.meta.dirname, '../../backend'),
    stdio: 'inherit',
  });
}
