// Positive, never-shaming result language shared by the dashboard and Display View.

export function starsFor(total) {
  if (total >= 90) return 5;
  if (total >= 75) return 4;
  if (total >= 55) return 3;
  if (total >= 30) return 2;
  return 1; // everyone who plays earns a star
}

const MESSAGES = {
  5: ['Fantastic rhythm!', 'Right in the groove!', 'Wonderful playing!'],
  4: ['Great teamwork!', 'Sounding great!', 'Lovely rhythm!'],
  3: ['Nice work, everyone!', 'Good job together!', 'You found the beat!'],
  2: ['Good effort! Let’s try it again.', 'Nice try! Listen once more and go again.'],
  1: ['Thanks for playing! Let’s listen again together.', 'Every try helps. Let’s play it again!'],
};

export function messageFor(total, seed = 0) {
  const list = MESSAGES[starsFor(total)];
  return list[Math.abs(Math.floor(seed)) % list.length];
}

export const CATEGORY_LABELS = {
  pattern_accuracy: 'Right hits',
  timing_accuracy: 'On the beat',
  tempo_consistency: 'Steady speed',
  completion: 'Played it all',
};

export function confidenceLevel(confidence) {
  if (confidence >= 0.75) return { key: 'high', label: 'Clear recording' };
  if (confidence >= 0.5) return { key: 'medium', label: 'Mostly clear recording' };
  return { key: 'low', label: 'Unclear recording' };
}
