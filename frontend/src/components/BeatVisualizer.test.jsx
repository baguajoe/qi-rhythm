import { render } from '@testing-library/react';
import BeatVisualizer from './BeatVisualizer.jsx';

const pattern = {
  length_beats: 4,
  events: [
    { beat: 0, voice: 'low' },
    { beat: 1, voice: 'clap' },
    { beat: 2, voice: 'shaker' },
  ],
};

test('marks played and current hits without un-lighting earlier ones', () => {
  const { container, getByRole } = render(<BeatVisualizer pattern={pattern} playedThrough={1} />);
  const hits = container.querySelectorAll('[title]');
  expect(hits).toHaveLength(3);
  expect(hits[0].className).toMatch(/played/);
  expect(hits[1].className).toMatch(/current/);
  expect(hits[2].className).toMatch(/waiting/);
  expect(hits[1].style.left).toBe('25%');
  expect(getByRole('img')).toHaveAccessibleName('Rhythm pattern with 3 hits over 4 beats');
});
