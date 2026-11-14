import { defineConfig } from '@playwright/test';

// End-to-end suite: real backend (gunicorn + gevent, like production) on a dedicated e2e database,
// production build of the frontend, Chromium with a WAV file as the "microphone".
export const API_PORT = Number(process.env.E2E_API_PORT || 5001);
export const WEB_PORT = Number(process.env.E2E_WEB_PORT || 5174);
const PYTHON = process.env.E2E_PYTHON || '.venv/bin/python';
const DATABASE_URL =
  process.env.E2E_DATABASE_URL || 'postgresql+psycopg://qi:qi@localhost:5432/qi_rhythm_e2e';

export default defineConfig({
  testDir: './e2e',
  globalSetup: './e2e/global-setup.js',
  fullyParallel: false,
  workers: 1, // specs share one class session and run in file order
  timeout: 180_000,
  expect: { timeout: 15_000 },
  retries: process.env.CI ? 1 : 0,
  reporter: [['list'], ['html', { outputFolder: 'playwright-report', open: 'never' }]],
  outputDir: 'test-results',
  use: {
    baseURL: `http://localhost:${WEB_PORT}`,
    browserName: 'chromium',
    headless: true,
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
    trace: 'retain-on-failure',
    permissions: ['microphone'],
  },
  webServer: [
    {
      cwd: '../backend',
      command: `${PYTHON} scripts/e2e_prepare_db.py && ${PYTHON} -m gunicorn -c gunicorn.conf.py wsgi:app`,
      url: `http://localhost:${API_PORT}/health`,
      timeout: 120_000,
      reuseExistingServer: false,
      stdout: 'pipe',
      env: {
        ...process.env,
        DATABASE_URL,
        PORT: String(API_PORT),
        SOCKETIO_ASYNC_MODE: 'gevent',
        CORS_ORIGINS: `http://localhost:${WEB_PORT}`,
        STORAGE_BACKEND: 'local',
        LOCAL_STORAGE_DIR: 'instance/e2e-recordings',
        JWT_SECRET_KEY: 'e2e-only-jwt-secret-key-not-for-production',
        SECRET_KEY: 'e2e-only-secret',
        AUDIO_WARMUP: '1',
      },
    },
    {
      command: `npx vite build --outDir dist-e2e --emptyOutDir && npx vite preview --outDir dist-e2e --port ${WEB_PORT} --strictPort`,
      url: `http://localhost:${WEB_PORT}`,
      timeout: 120_000,
      reuseExistingServer: false,
      env: { ...process.env, VITE_API_URL: `http://localhost:${API_PORT}` },
    },
  ],
});
