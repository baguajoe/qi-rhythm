import axe from 'axe-core';

/**
 * Run axe-core against a rendered container. Colour contrast is checked separately in
 * tokens.a11y.test.js because jsdom cannot compute rendered colours.
 */
export async function axeViolations(container, { isolated = false } = {}) {
  const results = await axe.run(container, {
    rules: {
      'color-contrast': { enabled: false },
      region: { enabled: !isolated },
    },
    resultTypes: ['violations'],
  });
  return results.violations.map(
    (v) => `${v.id}: ${v.help} -> ${v.nodes.map((n) => n.target.join(' ')).join(', ')}`,
  );
}
