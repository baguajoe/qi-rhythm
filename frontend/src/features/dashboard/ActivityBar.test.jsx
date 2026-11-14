import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import ActivityBar from './ActivityBar.jsx';
import { mockFetch } from '../../test/utils.jsx';

const rhythms = [
  { id: 1, title: 'Son Clave 3-2' },
  { id: 2, title: 'Boom-Bap Basic' },
];

test('steps through a saved activity', async () => {
  mockFetch({
    'GET /api/activities': { activities: [{ id: 5, name: 'Tuesday set', rhythm_ids: [1, 2] }] },
  });
  const onSelect = vi.fn();
  render(
    <ActivityBar sessionId={3} rhythms={rhythms} roundsPlayed={0} onSelectRhythm={onSelect} />,
  );
  await userEvent.selectOptions(await screen.findByLabelText('Saved activity'), '5');
  await userEvent.click(screen.getByRole('button', { name: 'Use activity' }));
  expect(onSelect).toHaveBeenLastCalledWith(rhythms[0]);
  expect(screen.getByText(/rhythm 1 of 2/)).toBeInTheDocument();
  await userEvent.click(screen.getByRole('button', { name: /Next rhythm/ }));
  expect(onSelect).toHaveBeenLastCalledWith(rhythms[1]);
  expect(screen.getByRole('button', { name: /Next rhythm/ })).toBeDisabled();
});

test("saves today's rhythms", async () => {
  const calls = mockFetch({
    'GET /api/activities': { activities: [] },
    'POST /api/activities': { activity: { id: 9 } },
  });
  render(<ActivityBar sessionId={3} rhythms={rhythms} roundsPlayed={2} onSelectRhythm={vi.fn()} />);
  await userEvent.type(screen.getByLabelText(/Save today's rhythms/), 'Warm-up');
  await userEvent.click(screen.getByRole('button', { name: 'Save' }));
  expect(await screen.findByText('Saved “Warm-up”.')).toBeInTheDocument();
  expect(calls.find((c) => c.key === 'POST /api/activities').body).toEqual({
    name: 'Warm-up',
    from_session_id: 3,
  });
});
