import { useEffect } from 'react';

/** Sets a descriptive page title (announced by screen readers on navigation). */
export function useDocumentTitle(title) {
  useEffect(() => {
    document.title = title ? `${title} – Qi Rhythm` : 'Qi Rhythm';
  }, [title]);
}
