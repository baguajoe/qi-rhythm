import { act, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import DisplayPage, { DisplayScreen } from './DisplayPage.jsx';
import { initialDisplayState } from './displayReducer.js';
import { mockFetch } from '../../test/utils.jsx';

let handlers = null;
const disconnect = vi.fn();
vi.mock('../../lib/socket.js', () => ({
  connectSession: vi.fn((opts) => {
    handlers = opts;
    return { disconnect };
  }),
}));

function renderDisplay(path) {
  return render(
    <MemoryRouter
      initialEntries={[path]}
      future={{ v7_startTransition: true, v7_relativeSplatPath: true }}
    >
      <Routes>
        <Route path="/display/:sessionId" element={<DisplayPage />} />
      </Routes>
    </MemoryRouter>,
  );
}

const team = { id: 1, name: 'Blue Jays', color: '#1f4e99', mascot_icon: 'bird' };

test('auto-pairs with ?code and renders live phases', async () => {
  mockFetch({ 'POST /api/display/pair': { display_token: 'disp-tok', session_id: 42 } });
  renderDisplay('/display/42?code=ABC234');
  await vi.waitFor(() => expect(handlers).not.toBeNull());
  expect(handlers.token).toBe('disp-tok');
  expect(handlers.sessionId).toBe(42);
  expect(localStorage.getItem('qi.display.42')).toBe('disp-tok');

  act(() => {
    handlers.onStatus('connected');
    handlers.onEvent('session:state', {
      live: { phase: 'idle', focus: { team, rhythm: { title: 'Son Clave 3-2' } } },
      settings: {},
      scoreboard: { teams: [] },
    });
  });
  expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent('Blue Jays');
  expect(screen.getByText('Rhythm: Son Clave 3-2')).toBeInTheDocument();

  act(() => handlers.onEvent('round:countin', { count: 3 }));
  expect(screen.getByText('3', { selector: 'p' })).toBeInTheDocument();
  act(() => handlers.onEvent('round:recording', {}));
  expect(screen.getByText('Your turn!')).toBeInTheDocument();
  expect(screen.getByRole('meter', { name: 'Drum sound' })).toBeInTheDocument();

  act(() => handlers.onStatus('reconnecting'));
  expect(screen.getByRole('status')).toHaveTextContent('Reconnecting…');
});

test('asks for a code when no token, and pairs', async () => {
  mockFetch({ 'POST /api/display/pair': { display_token: 'tok2', session_id: 7 } });
  handlers = null;
  renderDisplay('/display/7');
  await userEvent.type(screen.getByLabelText(/Enter the code/), 'xyz789');
  await userEvent.click(screen.getByRole('button', { name: 'Connect' }));
  await vi.waitFor(() => expect(handlers?.token).toBe('tok2'));
});

test('denied token returns to pairing form', async () => {
  localStorage.setItem('qi.display.5', 'old');
  renderDisplay('/display/5');
  await vi.waitFor(() => expect(handlers?.token).toBe('old'));
  act(() => handlers.onStatus('denied'));
  expect(await screen.findByRole('alert')).toHaveTextContent('needs a new code');
  expect(localStorage.getItem('qi.display.5')).toBeNull();
});

test('scored screen is encouraging and cooperative mode hides ranking', () => {
  const state = {
    ...initialDisplayState,
    status: 'connected',
    phase: 'scored',
    round: { id: 2, team, score: { effective: { total: 20 } } },
    scoreboard: { cooperative: true, group_points: 140, teams: [{ team, points: 20 }] },
  };
  render(<DisplayScreen state={state} />);
  expect(screen.getByRole('img', { name: '1 out of 5 stars' })).toBeInTheDocument();
  expect(screen.getByText('20 points')).toBeInTheDocument();
  expect(screen.getByText('Together: 140 points')).toBeInTheDocument();
  expect(screen.queryByText('Scoreboard')).not.toBeInTheDocument();
  expect(document.body.textContent).not.toMatch(/fail|lose/i);
});

test('leaderboard ranks teams when competitive', () => {
  const state = {
    ...initialDisplayState,
    status: 'connected',
    phase: 'idle',
    scoreboard: {
      cooperative: false,
      teams: [
        { team, points: 180 },
        { team: { id: 2, name: 'Sunflowers', color: '#b35900' }, points: 150 },
      ],
    },
  };
  render(<DisplayScreen state={state} />);
  const items = screen.getAllByRole('listitem');
  expect(items[0]).toHaveTextContent('Blue Jays180');
  expect(items[1]).toHaveTextContent('Sunflowers150');
});
