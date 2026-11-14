import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import ShowOnTv from './ShowOnTv.jsx';
import { mockFetch } from '../../test/utils.jsx';

test('gets a code and opens the TV window', async () => {
  mockFetch({
    'POST /api/sessions/42/display-code': { code: 'ABC234', path: '/display/42?code=ABC234' },
  });
  const open = vi.spyOn(window, 'open').mockImplementation(() => null);
  render(<ShowOnTv sessionId={42} socketStatus="connected" />);
  await userEvent.click(screen.getByRole('button', { name: 'Get a TV code' }));
  expect(await screen.findByText('ABC234')).toBeInTheDocument();
  await userEvent.click(screen.getByRole('button', { name: /Open TV screen/ }));
  expect(open).toHaveBeenCalledWith('/display/42?code=ABC234', 'qi-display', 'noopener');
  expect(screen.getByRole('status')).toHaveTextContent('connected');
});
