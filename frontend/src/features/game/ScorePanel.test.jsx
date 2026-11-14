import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import ScorePanel from './ScorePanel.jsx';

const machine = {
  pattern_accuracy: 62,
  timing_accuracy: 70,
  tempo_consistency: 80,
  completion: 100,
  total: 72,
};
const alignment = {
  expected: [0, 1, 2].map((i) => ({ index: i, beat: i, voice: 'low', time_s: 3 + i * 0.6 })),
  detected_s: [3.0, 3.61, 3.9],
  matched: [
    { expected_index: 0, detected_index: 0, expected_s: 3, detected_s: 3.0, error_ms: 0 },
    { expected_index: 1, detected_index: 1, expected_s: 3.6, detected_s: 3.61, error_ms: 10 },
  ],
  missed: [2],
  extras: [2],
  global_offset_ms: 0,
  window_s: [2.5, 5],
};
const score = {
  id: 4,
  machine,
  effective: machine,
  confidence: 0.3,
  needs_review: true,
  review_reasons: ['The recording was noisy or quiet, so hits were hard to hear.'],
  confirmed: false,
  is_override: false,
  alignment,
};
const round = { id: 1, team: { name: 'Blue Jays', color: '#1f4e99' } };

test('shows breakdown, review prompt, confidence and timeline summary', () => {
  render(<ScorePanel round={round} score={score} onConfirm={vi.fn()} onOverride={vi.fn()} />);
  expect(screen.getByRole('heading', { name: 'Blue Jays: 72 points' })).toBeInTheDocument();
  expect(screen.getByText('Audio was unclear — confirm or adjust this score.')).toBeInTheDocument();
  expect(screen.getByText(/Unclear recording \(30% sure\)/)).toBeInTheDocument();
  expect(
    screen.getByRole('img', { name: /2 of 3 hits matched, 1 missed, 1 extra/ }),
  ).toBeInTheDocument();
  expect(screen.getByRole('img', { name: '3 out of 5 stars' })).toBeInTheDocument();
  expect(document.body.textContent).not.toMatch(/fail/i);
});

test('adjust sends only changed values plus reason', async () => {
  const onOverride = vi.fn(async () => {});
  render(<ScorePanel round={round} score={score} onConfirm={vi.fn()} onOverride={onOverride} />);
  await userEvent.click(screen.getByRole('button', { name: 'Adjust score' }));
  const field = screen.getByLabelText('Right hits');
  await userEvent.clear(field);
  await userEvent.type(field, '90');
  await userEvent.type(screen.getByLabelText('Reason (optional)'), 'Mic missed the shakers');
  await userEvent.click(screen.getByRole('button', { name: 'Save score' }));
  expect(onOverride).toHaveBeenCalledWith({
    pattern_accuracy: 90,
    reason: 'Mic missed the shakers',
  });
});

test('confirm button', async () => {
  const onConfirm = vi.fn();
  render(<ScorePanel round={round} score={score} onConfirm={onConfirm} onOverride={vi.fn()} />);
  await userEvent.click(screen.getByRole('button', { name: /Confirm score/ }));
  expect(onConfirm).toHaveBeenCalled();
});

test('override shows original machine total', () => {
  const eff = { ...machine, pattern_accuracy: 90, total: 83 };
  render(
    <ScorePanel
      round={round}
      score={{
        ...score,
        effective: eff,
        is_override: true,
        confirmed: true,
        override_reason: 'Heard them',
      }}
      onConfirm={vi.fn()}
      onOverride={vi.fn()}
    />,
  );
  expect(screen.getByText(/computer total was 72/)).toBeInTheDocument();
  expect(screen.getByText('(was 62)')).toBeInTheDocument();
  expect(screen.queryByText(/Audio was unclear/)).not.toBeInTheDocument();
});
