// Optional spoken instructions via the Web Speech API. Always paired with on-screen text.
export function speak(text, { enabled, rate = 0.9 } = {}) {
  if (!enabled || typeof window === 'undefined' || !window.speechSynthesis) return;
  try {
    window.speechSynthesis.cancel();
    const u = new SpeechSynthesisUtterance(text);
    u.rate = rate;
    window.speechSynthesis.speak(u);
  } catch {
    /* speech is a nice-to-have; never block the class */
  }
}
