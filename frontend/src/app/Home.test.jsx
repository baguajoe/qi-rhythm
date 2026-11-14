import { render, screen } from '@testing-library/react';
import Home from './Home.jsx';

test('renders the app name', () => {
  render(<Home />);
  expect(screen.getByRole('heading', { name: 'Qi Rhythm' })).toBeInTheDocument();
});
