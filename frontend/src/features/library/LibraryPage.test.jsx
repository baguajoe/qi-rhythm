import { screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import LibraryPage from './LibraryPage.jsx';
import { ME, mockFetch, renderApp } from '../../test/utils.jsx';

const play = vi.fn(() => Promise.resolve({ startedAt: 0 }));
vi.mock('../../audio/player.js', () => ({
  playPattern: (...a) => play(...a),
  stopPlayback: vi.fn(),
}));

const genres = [
  { slug: 'latin', name: 'Latin', cultural_notes: 'The clave is a two-bar key.' },
  { slug: 'hip-hop', name: 'Hip-Hop', cultural_notes: 'Bronx block parties.' },
];
const mk = (id, title, genre_slug, difficulty) => ({
  id,
  title,
  genre_slug,
  difficulty,
  bpm: 90,
  time_signature: '4/4',
  length_beats: 8,
  pattern: {
    count_in_beats: 4,
    events: [
      { beat: 0, voice: 'high' },
      { beat: 1.5, voice: 'high' },
    ],
  },
});
const rhythms = [
  mk(1, 'Son Clave 3-2', 'latin', 'beginner'),
  mk(2, 'Rumba Clave 3-2', 'latin', 'intermediate'),
  mk(3, 'Boom-Bap Basic', 'hip-hop', 'beginner'),
];

beforeEach(() =>
  mockFetch({
    'GET /api/auth/me': ME,
    'GET /api/genres': { genres },
    'GET /api/rhythms': { rhythms },
  }),
);

test('filters by style and difficulty', async () => {
  renderApp(<LibraryPage />);
  await screen.findByText('Son Clave 3-2');
  await userEvent.selectOptions(screen.getByLabelText('Music style'), 'latin');
  expect(screen.queryByText('Boom-Bap Basic')).not.toBeInTheDocument();
  await userEvent.selectOptions(screen.getByLabelText('Difficulty'), 'beginner');
  expect(screen.getByRole('status')).toHaveTextContent('1 rhythm');
});

test('selecting a rhythm shows cultural notes and plays at chosen tempo', async () => {
  renderApp(<LibraryPage />);
  await userEvent.click(await screen.findByRole('button', { name: /Son Clave 3-2/ }));
  const preview = screen.getByRole('region', { name: 'Son Clave 3-2' });
  expect(within(preview).getByText('The clave is a two-bar key.')).toBeInTheDocument();
  await userEvent.click(within(preview).getByRole('button', { name: /Play the pattern/ }));
  expect(play).toHaveBeenCalledWith(
    rhythms[0].pattern,
    90,
    expect.objectContaining({ lengthBeats: 8, volume: 0.8 }),
  );
});
