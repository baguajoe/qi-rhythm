import { expect, test } from '@playwright/test';
import {
  MISSED_GAP_MIN,
  TEAM_B,
  latestRound,
  login,
  micArgs,
  pickRhythmAndTeam,
  readState,
  resumeClass,
  runTurn,
  saveState,
} from './helpers.js';

test.use({ launchOptions: micArgs('missed.wav') });

test('a take with 2 missed hits scores lower', async ({ page }) => {
  await login(page);
  await resumeClass(page);
  await pickRhythmAndTeam(page, TEAM_B);
  const total = await runTurn(page, TEAM_B);
  const round = await latestRound(page);
  const al = round.score.alignment;
  test.info().annotations.push({
    type: 'score',
    description: `missed total=${total} matched=${al.matched.length} missed=${al.missed.length} offset=${al.global_offset_ms}ms`,
  });
  expect(al.missed).toHaveLength(2);
  expect(round.score.machine.pattern_accuracy).toBeLessThan(85);
  expect(total).toBeLessThanOrEqual(readState().perfectTotal - MISSED_GAP_MIN);
  saveState({ missedTotal: total });
});
