// Team colours chosen to give >= 4.5:1 contrast with white text (WCAG AA).
export const TEAM_COLORS = [
  { hex: '#1f4e99', name: 'Blue' },
  { hex: '#b35900', name: 'Orange' },
  { hex: '#2e6b30', name: 'Green' },
  { hex: '#6a1b9a', name: 'Purple' },
  { hex: '#b71c1c', name: 'Red' },
  { hex: '#00695c', name: 'Teal' },
  { hex: '#ad1457', name: 'Pink' },
  { hex: '#4e342e', name: 'Brown' },
];

export const MASCOT_ICONS = {
  sun: { emoji: '☀️', label: 'Sun' },
  bird: { emoji: '🐦', label: 'Bird' },
  star: { emoji: '⭐', label: 'Star' },
  flower: { emoji: '🌻', label: 'Flower' },
  drum: { emoji: '🥁', label: 'Drum' },
  music: { emoji: '🎵', label: 'Music note' },
  tree: { emoji: '🌳', label: 'Tree' },
  wave: { emoji: '🌊', label: 'Wave' },
  heart: { emoji: '💛', label: 'Heart' },
  moon: { emoji: '🌙', label: 'Moon' },
};

export function colorName(hex) {
  return TEAM_COLORS.find((c) => c.hex === hex?.toLowerCase())?.name || 'Custom colour';
}
