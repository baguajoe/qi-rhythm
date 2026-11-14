import '@testing-library/jest-dom/vitest';

afterEach(() => {
  localStorage.clear();
  vi.restoreAllMocks();
});

// jsdom has no canvas; axe-core probes it for icon ligatures. Return null quietly.
HTMLCanvasElement.prototype.getContext = () => null;
