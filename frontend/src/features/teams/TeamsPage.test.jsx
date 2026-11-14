import { screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import TeamsPage from './TeamsPage.jsx';
import { ME, mockFetch, renderApp } from '../../test/utils.jsx';

const team = {
  id: 7,
  name: 'Sunflowers',
  color: '#b35900',
  mascot_icon: 'sun',
  is_active: true,
  participants: [],
};

test('creates a team with the chosen colour', async () => {
  let teams = [];
  const calls = mockFetch({
    'GET /api/auth/me': ME,
    'GET /api/teams': () => ({ teams }),
    'POST /api/teams': (req) => {
      teams = [{ ...team, ...req.body, id: 8 }];
      return { team: teams[0] };
    },
  });
  renderApp(<TeamsPage />);
  expect(await screen.findByText(/No teams yet/)).toBeInTheDocument();
  const form = screen.getByRole('form', { name: 'Make a new team' });
  await userEvent.type(within(form).getByLabelText('Team name'), 'Blue Jays');
  await userEvent.click(within(form).getByLabelText('Teal'));
  await userEvent.click(within(form).getByRole('button', { name: 'Add team' }));
  expect(await screen.findByRole('heading', { name: /Blue Jays/ })).toBeInTheDocument();
  const post = calls.find((c) => c.key === 'POST /api/teams');
  expect(post.body).toMatchObject({ name: 'Blue Jays', color: '#00695c' });
});

test('adds a nickname to a team', async () => {
  mockFetch({
    'GET /api/auth/me': ME,
    'GET /api/teams': { teams: [team] },
    'POST /api/teams/7/participants': {
      team: { ...team, participants: [{ id: 1, alias: 'Rosie' }] },
    },
  });
  renderApp(<TeamsPage />);
  const nick = await screen.findByLabelText(/Add a nickname/);
  await userEvent.type(nick, 'Rosie');
  await userEvent.click(screen.getByRole('button', { name: 'Add' }));
  expect(await screen.findByRole('button', { name: 'Remove Rosie' })).toBeInTheDocument();
});
